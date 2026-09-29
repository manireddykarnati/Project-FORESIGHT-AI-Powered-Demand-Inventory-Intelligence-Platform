"""End-to-end pipeline: data -> features -> models -> backtest -> forecast -> inventory recommendations.
Run:  python run_pipeline.py
"""
import json, numpy as np, pandas as pd
from src.features import load_sales, build_training_frame, FEATURES
from src.forecast import train_lgbm, backtest, recursive_forecast, wape, mae, rmse, bias
from src.inventory import simulate_inventory, compute_recommendations

TEST_DAYS, HORIZON, HIST_DAYS_SHOWN = 90, 30, 120
df = load_sales("data/sales_daily.csv")
skus = sorted(df["SKU"].unique())
sku_codes = np.arange(len(skus))
piv = lambda c: df.pivot(index="SKU", columns="Date", values=c).loc[skus]
U, P = piv("Units_Sold").values.astype(float), piv("Promotion").values.astype(float)
dates = pd.DatetimeIndex(piv("Units_Sold").columns)
price = df.groupby("SKU")["Price"].last().loc[skus].values
T = U.shape[1]

# ---- 1. train on everything before the test window, backtest 30 days at a time ------
cut = dates[T - TEST_DAYS]
feat = build_training_frame(df)
model_bt = train_lgbm(feat[feat["Date"] < cut])
actual, preds = backtest(model_bt, U, P, price, dates, sku_codes, TEST_DAYS, HORIZON)

rows = []
for name, p in preds.items():
    rows.append(dict(model=name, MAE=mae(actual, p), RMSE=rmse(actual, p), WAPE_pct=wape(actual, p), Bias_pct=bias(actual, p)))
metrics = pd.DataFrame(rows).round(3)
best_naive = metrics.loc[metrics.model == "Naive (last week)", "WAPE_pct"].iloc[0]
lgb_w = metrics.loc[metrics.model == "LightGBM", "WAPE_pct"].iloc[0]
print(metrics.to_string(index=False))
print(f"LightGBM improves WAPE vs naive by {(best_naive - lgb_w) / best_naive * 100:.1f}%")
metrics.to_csv("outputs/model_metrics.csv", index=False)

# per-SKU accuracy + error std (used for safety stock)
lg = preds["LightGBM"]
err_std = (actual - lg).std(axis=1, ddof=1)
sku_acc = pd.DataFrame({"sku": skus, "wape_pct": [wape(actual[i], lg[i]) for i in range(len(skus))],
                        "demand_std": err_std}).round(3)

# ---- 2. final model on ALL data, 30-day forward forecast ------------------------------
model = train_lgbm(feat)
fut_start = dates[-1] + pd.Timedelta(days=1)
promo_plan = np.zeros((len(skus), HORIZON))          # assumption: no promotions planned
fut = recursive_forecast(model, U, fut_start, promo_plan, price, sku_codes)
fut_dates = pd.date_range(fut_start, periods=HORIZON)

imp = pd.DataFrame({"feature": FEATURES, "importance": model.booster_.feature_importance("gain")})
imp["importance"] = (imp["importance"] / imp["importance"].sum() * 100).round(2)
imp.sort_values("importance", ascending=False).to_csv("outputs/feature_importance.csv", index=False)

# ---- 3. forecasts.csv for the dashboard --------------------------------------------------
Z95 = 1.6449
parts = []
for i, s in enumerate(skus):
    h = slice(T - TEST_DAYS - (HIST_DAYS_SHOWN - TEST_DAYS), T - TEST_DAYS)
    parts.append(pd.DataFrame({"date": dates[h], "sku": s, "actual": U[i, h], "forecast": np.nan, "type": "history"}))
    parts.append(pd.DataFrame({"date": dates[T - TEST_DAYS:], "sku": s, "actual": actual[i], "forecast": lg[i], "type": "backtest"}))
    parts.append(pd.DataFrame({"date": fut_dates, "sku": s, "actual": np.nan, "forecast": fut[i], "type": "future"}))
fc = pd.concat(parts, ignore_index=True)
fc["lower"] = (fc["forecast"] - Z95 * err_std[fc["sku"].map({s: i for i, s in enumerate(skus)}).values]).clip(lower=0)
fc["upper"] = fc["forecast"] + Z95 * err_std[fc["sku"].map({s: i for i, s in enumerate(skus)}).values]
fc.assign(date=fc['date'].dt.strftime('%Y-%m-%d')).round(2).to_csv("outputs/forecasts.csv", index=False)

# ---- 4. inventory recommendations ---------------------------------------------------------
summary = pd.DataFrame({
    "sku": skus,
    "price": price,
    "avg_daily_demand_hist": U[:, -28:].mean(axis=1),
    "avg_daily_demand": fut.mean(axis=1),
    "forecast_30d_units": fut.sum(axis=1),
    "hist_revenue": df.groupby("SKU")["Revenue"].sum().loc[skus].values,
}).merge(sku_acc, on="sku")
summary = simulate_inventory(summary, seed=42)
# ABC class by revenue share
summary = summary.sort_values("hist_revenue", ascending=False)
cum = summary["hist_revenue"].cumsum() / summary["hist_revenue"].sum()
summary["abc_class"] = np.where(cum <= 0.8, "A", np.where(cum <= 0.95, "B", "C"))
summary = summary.sort_values("sku").reset_index(drop=True)
summary.to_csv("outputs/sku_inputs.csv", index=False)      # dashboard recomputes with a service-level slider
rec = compute_recommendations(summary, 0.95)
rec.round(2).to_csv("outputs/recommendations.csv", index=False)

print(rec["flag"].value_counts().to_string())
print("Excess inventory value:", int(rec.excess_inventory_value.sum()),
      "| Lost-sales exposure:", int(rec.expected_lost_sales_value.sum()))
json.dump({"test_start": str(cut.date()), "test_end": str(dates[-1].date()), "forecast_start": str(fut_start.date()),
           "forecast_end": str(fut_dates[-1].date()), "wape_lightgbm": lgb_w, "wape_naive": best_naive}, open("outputs/run_info.json", "w"))
