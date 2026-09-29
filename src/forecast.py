"""Model training, honest multi-step backtesting and recursive forecasting."""
import numpy as np
import pandas as pd
import lightgbm as lgb
from .features import FEATURES, step_features

PARAMS = dict(objective="regression", n_estimators=600, learning_rate=0.03, num_leaves=31,
              min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
              random_state=42, verbose=-1)


def train_lgbm(train_df):
    tr = train_df.dropna(subset=FEATURES)
    model = lgb.LGBMRegressor(**PARAMS)
    model.fit(tr[FEATURES], tr["Units_Sold"], categorical_feature=["sku_code"])
    return model


def recursive_forecast(model, hist, start_date, promo_plan, price, sku_codes):
    """Forecast promo_plan.shape[1] days ahead, feeding predictions back in as history."""
    horizon = promo_plan.shape[1]
    h = hist.astype(float).copy()
    preds = np.zeros((h.shape[0], horizon))
    for k in range(horizon):
        date = start_date + pd.Timedelta(days=k)
        X = step_features(h, date, promo_plan[:, k], price, sku_codes)
        p = np.clip(model.predict(X), 0, None)
        preds[:, k] = p
        h = np.concatenate([h, p[:, None]], axis=1)
    return preds


def wape(y, p): return float(np.abs(y - p).sum() / y.sum() * 100)
def mae(y, p): return float(np.abs(y - p).mean())
def rmse(y, p): return float(np.sqrt(((y - p) ** 2).mean()))
def bias(y, p): return float((p - y).sum() / y.sum() * 100)


def backtest(model, U, P, price, dates, sku_codes, test_days=90, horizon=30):
    """Rolling-origin backtest: forecast `horizon` days at a time, starting from actual history.
    Mirrors how the model is used in production (30 days ahead, no peeking)."""
    T = U.shape[1]
    t0 = T - test_days
    lgbm = np.zeros((U.shape[0], test_days))
    naive = np.zeros_like(lgbm)   # same weekday, last observed week
    ma28 = np.zeros_like(lgbm)    # flat 28-day moving average
    for w in range(test_days // horizon):
        o = t0 + w * horizon
        hist = U[:, :o]
        sl = slice(w * horizon, (w + 1) * horizon)
        lgbm[:, sl] = recursive_forecast(model, hist, dates[o], P[:, o:o + horizon], price, sku_codes)
        for k in range(horizon):
            naive[:, w * horizon + k] = hist[:, -7:][:, k % 7]
        ma28[:, sl] = hist[:, -28:].mean(axis=1, keepdims=True)
    return U[:, t0:], {"Naive (last week)": naive, "Moving average (28d)": ma28, "LightGBM": lgbm}
