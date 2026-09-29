"""Feature engineering shared by training (vectorised) and recursive forecasting."""
import numpy as np
import pandas as pd

FEATURES = [
    "sku_code", "dow", "month", "doy", "is_weekend", "promo", "price",
    "lag_7", "lag_14", "lag_28", "roll_mean_7", "roll_mean_28", "roll_std_28",
]


def load_sales(path):
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.sort_values(["SKU", "Date"]).reset_index(drop=True)
    df["sku_code"] = df["SKU"].astype("category").cat.codes
    return df


def build_training_frame(df):
    """Lags/rolling stats are shifted so day t only sees data up to t-7 (lags) or t-1 (rolling)."""
    d = df.copy()
    g = d.groupby("SKU")["Units_Sold"]
    d["lag_7"], d["lag_14"], d["lag_28"] = g.shift(7), g.shift(14), g.shift(28)
    s1 = g.shift(1)
    grp = s1.groupby(d["SKU"])
    d["roll_mean_7"] = grp.transform(lambda x: x.rolling(7).mean())
    d["roll_mean_28"] = grp.transform(lambda x: x.rolling(28).mean())
    d["roll_std_28"] = grp.transform(lambda x: x.rolling(28).std())
    d["dow"] = d["Date"].dt.dayofweek
    d["month"] = d["Date"].dt.month
    d["doy"] = d["Date"].dt.dayofyear
    d["is_weekend"] = (d["dow"] >= 5).astype(int)
    d["promo"] = d["Promotion"]
    d["price"] = d["Price"]
    return d


def step_features(hist, date, promo, price, sku_codes):
    """Features for ONE future day for all SKUs. hist: (n_sku, T) units up to the day before `date`."""
    dow = date.dayofweek
    return pd.DataFrame({
        "sku_code": sku_codes,
        "dow": dow, "month": date.month, "doy": date.dayofyear,
        "is_weekend": int(dow >= 5),
        "promo": promo, "price": price,
        "lag_7": hist[:, -7], "lag_14": hist[:, -14], "lag_28": hist[:, -28],
        "roll_mean_7": hist[:, -7:].mean(axis=1),
        "roll_mean_28": hist[:, -28:].mean(axis=1),
        "roll_std_28": hist[:, -28:].std(axis=1, ddof=1),
    })[FEATURES]
