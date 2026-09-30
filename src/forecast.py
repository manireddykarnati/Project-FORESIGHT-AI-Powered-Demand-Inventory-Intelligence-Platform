"""Origin-isolated fitting, recursive forecasts and matching weekly evaluations."""
import numpy as np
import pandas as pd
import lightgbm as lgb
from .features import FEATURES, build_training_frame, step_features

MODEL = 'LightGBM'
HORIZON = 56


def train_model(sales, mapping):
    frame = sales.copy()
    frame['sku_code'] = frame.SKU.map(mapping)
    tr = build_training_frame(frame).dropna(subset=FEATURES)
    if len(tr) < 30:
        return None
    model = lgb.LGBMRegressor(objective="regression", n_estimators=600, learning_rate=.03,
                             num_leaves=31, min_child_samples=30, subsample=.8,
                             subsample_freq=1, colsample_bytree=.8, random_state=42,
                             verbose=-1, n_jobs=1)
    model.fit(tr[FEATURES], tr.Units_Sold, categorical_feature=["sku_code"])
    return model


def predict_origin(history, origin, horizon=HORIZON, master=None, promo_plan=None):
    """Never accepts future actuals/prices. Optional promotion plan is an explicit scenario."""
    origin = pd.Timestamp(origin)
    if horizon < 1 or horizon > 366:
        raise ValueError('horizon must be 1..366 days')
    past = history[history.Date < origin].sort_values(['SKU', 'Date']).copy()
    if past.empty:
        raise ValueError('No history before origin')
    skus = sorted(set(past.SKU) | (set(master.SKU) if master is not None else set()))
    mapping = {s: i for i, s in enumerate(skus)}
    model = train_model(past, mapping)
    dates = pd.date_range(origin, periods=horizon)
    cats = master.set_index('SKU').Category.to_dict() if master is not None else {}
    recent = past[past.Date >= origin-pd.Timedelta(days=28)]
    means = recent.groupby('SKU').Units_Sold.mean()
    histories, fallback_values, naive_values, moving_values, prices, sparse_flags, methods = [], [], [], [], [], [], []
    for sku in skus:
        g = past[past.SKU == sku]
        h = g.Units_Sold.to_numpy(float)
        sparse = len(h) < 56 or model is None
        peers = [s for s in means.index if cats.get(s) == cats.get(sku) and s != sku] if sku in cats else []
        fallback = float(means.loc[peers].mean()) if peers else (float(h[-28:].mean()) if len(h) else np.nan)
        if not len(h) and not peers:
            raise ValueError(f'{sku}: no history or category peers to support forecast')
        histories.append(h[-28:] if len(h) >= 28 else np.pad(h, (28-len(h),0), constant_values=fallback))
        fallback_values.append(fallback)
        naive_values.append(np.resize(h[-7:], horizon) if len(h) >= 7 else np.repeat(fallback, horizon))
        moving_values.append(float(h[-28:].mean()) if len(h) else fallback)
        prices.append(float(g.Price.iloc[-1]) if len(g) else 0.)
        sparse_flags.append(sparse)
        methods.append(('category mean fallback' if peers else 'own-history mean fallback') if sparse else MODEL)
    h = np.array(histories)
    fallback_values, sparse_flags = np.array(fallback_values), np.array(sparse_flags)
    naive_values = np.array(naive_values)
    rows = []
    for k, date in enumerate(dates):
        promo = np.array([0 if promo_plan is None else promo_plan.get((sku, date), 0) for sku in skus])
        if not np.isin(promo, [0,1]).all():
            raise ValueError('Promotion scenario flags must be 0 or 1')
        pred = fallback_values.copy()
        if (~sparse_flags).any():
            x = step_features(h, date, promo, np.array(prices), np.arange(len(skus)))
            pred[~sparse_flags] = np.maximum(0., model.predict(x.loc[~sparse_flags]))
        for i, sku in enumerate(skus):
            rows.append(dict(date=date, sku=sku, origin=origin, forecast=pred[i], baseline=naive_values[i,k],
                             moving_average=moving_values[i], low_confidence=bool(sparse_flags[i]), method=methods[i]))
        h = np.column_stack([h[:, 1:], pred])
    return pd.DataFrame(rows), dict(origin=str(origin.date()), train_max_date=str(past.Date.max().date()),
                                    train_rows=len(past), model_fitted=model is not None,
                                    price_policy='last price before origin', promotion_policy='no promotions unless explicit scenario')


def weekly(frame):
    """Nonoverlapping 7-day horizon blocks anchored on each origin, no partial calendar weeks."""
    d = frame.copy()
    d['week'] = ((d.date-d.origin).dt.days // 7 + 1).astype(int)
    nums = [c for c in ['actual', 'forecast', 'baseline', 'moving_average'] if c in d]
    w = d.groupby(['origin', 'sku', 'week'], as_index=False)[nums].sum(min_count=1)
    w['week_start'] = w.origin + pd.to_timedelta((w.week-1)*7, unit='D')
    w['week_end'] = w.week_start + pd.Timedelta(days=6)
    counts = d.groupby(['origin', 'sku', 'week']).size().to_numpy()
    w['days'] = counts
    return w


def metrics(frame, scale):
    rows = []
    for col, name in [('forecast', MODEL), ('baseline', 'Seasonal naive'), ('moving_average', 'Moving average (28d)')]:
        y, p = frame.actual.to_numpy(), frame[col].to_numpy()
        good = np.isfinite(y) & np.isfinite(p)
        y, p = y[good], p[good]
        den = y.sum()
        rows.append(dict(model=name, scale=scale, n=len(y), MAE=float(np.abs(y-p).mean()),
                         RMSE=float(np.sqrt(((y-p)**2).mean())),
                         WAPE_pct=float(abs(y-p).sum()/den*100) if den else np.nan,
                         Bias_pct=float((p-y).sum()/den*100) if den else np.nan,
                         MAPE_pct=float((abs(y[y != 0]-p[y != 0])/y[y != 0]).mean()*100) if (y != 0).any() else np.nan))
    return pd.DataFrame(rows)


def backtest(sales, horizon=HORIZON, folds=3, master=None):
    end = sales.Date.max() + pd.Timedelta(days=1)
    frames, audits = [], []
    for i in range(folds, 0, -1):
        origin = end-pd.Timedelta(days=i*horizon)
        if (origin-sales.Date.min()).days < 56:
            raise ValueError('Need at least 56 training days before all backtest folds')
        # No master-derived costs/categories from an undated current extract in model CV.
        f, audit = predict_origin(sales[sales.Date < origin], origin, horizon)
        actual = sales.rename(columns={'Date': 'date', 'SKU': 'sku', 'Units_Sold': 'actual'})
        f = f.merge(actual[['date', 'sku', 'actual']], on=['date', 'sku'], how='left', validate='one_to_one')
        frames.append(f)
        audits.append(audit)
    return pd.concat(frames, ignore_index=True), audits
