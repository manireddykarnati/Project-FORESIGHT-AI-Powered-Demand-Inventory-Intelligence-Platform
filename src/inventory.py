"""Inventory decisions use supplied snapshots; never simulate business inputs."""
import numpy as np
import pandas as pd

Z = {0.90: 1.2816, 0.95: 1.6449, 0.97: 1.8808, 0.99: 2.3263}
REVIEW_DAYS, OVERSTOCK_COVER = 7, 60


def compute_recommendations(inputs, service_level=.95):
    if service_level not in Z:
        raise ValueError(f'service_level must be one of {list(Z)}')
    required = ['sku', 'current_stock', 'on_order', 'lead_time_days', 'unit_cost', 'price',
                'demand_std', 'lead_time_demand', 'review_demand', 'demand_60d', 'avg_daily_demand']
    if set(required)-set(inputs):
        raise ValueError(f'Missing inventory inputs: {sorted(set(required)-set(inputs))}')
    r = inputs.copy()
    for c in required[1:]:
        v = pd.to_numeric(r[c], errors='coerce')
        if (~np.isfinite(v) | (v < 0)).any():
            raise ValueError(f'{c} must be finite and nonnegative')
        r[c] = v
    if r.sku.duplicated().any() or r.sku.isna().any():
        raise ValueError('Inventory SKUs must be unique and nonempty')
    if ((r.lead_time_days < 1) | (r.lead_time_days % 1 != 0)).any():
        raise ValueError('lead_time_days must be positive whole days')
    r['inventory_position'] = r.current_stock+r.on_order
    r['safety_stock'] = np.ceil(Z[service_level]*r.demand_std*np.sqrt(r.lead_time_days))
    r['reorder_point'] = np.ceil(r.lead_time_demand+r.safety_stock)
    r['days_of_cover'] = r.current_stock.div(r.avg_daily_demand.replace(0, np.nan))
    # Brief section 8.1: stockout uses position, overstock uses physical on-hand.
    r['stockout_gap'] = (r.reorder_point-r.inventory_position).clip(lower=0)
    r['immediate_shortfall_units'] = (r.lead_time_demand-r.current_stock).clip(lower=0)
    r['excess_units'] = (r.current_stock-r.demand_60d).clip(lower=0)
    r['incoming_excess_units'] = (r.inventory_position-r.demand_60d).clip(lower=0)
    r['receipt_timing_warning'] = (r.immediate_shortfall_units > 0) & (r.on_order > 0)
    high_short, high_excess = r.stockout_gap > 0, r.excess_units > 0
    r['flag'] = np.select([high_short & high_excess, high_short, high_excess],
                          ['Watch / volatile', 'Reorder now', 'Markdown / clear'], default='Healthy')
    r['target_replenishment_qty'] = np.ceil((r.review_demand+r.safety_stock-r.inventory_position).clip(lower=0))
    r['recommended_order_qty'] = np.where(high_short & ~high_excess, r.target_replenishment_qty, 0)
    r['clearance_review_units'] = np.where(high_excess & ~high_short, np.floor(r.excess_units), 0)
    r['lead_time_revenue_exposure'] = (r.lead_time_demand-r.inventory_position).clip(lower=0)*r.price
    r['receipt_delay_revenue_exposure'] = r.immediate_shortfall_units*r.price
    r['excess_inventory_value'] = r.excess_units*r.unit_cost
    r['order_value'] = r.recommended_order_qty*r.unit_cost
    r['priority'] = np.select([high_short & (r.current_stock < r.lead_time_demand), high_short, high_excess],
                              ['Critical', 'High', 'Medium'], default='Low')
    r['action'] = [
        'Watch / volatile: verify receipts and demand before buying or clearing' if f == 'Watch / volatile' else
        (f'Order {int(q)} units now; verify receipt timing' if q > 0 else 'Expedite / verify existing on-order stock; no additional order') if f == 'Reorder now' else
        f'Review {int(c)} units for markdown / clearance; pause ordering' if f == 'Markdown / clear' else
        'No action; monitor weekly'
        for f, q, c in zip(r.flag, r.recommended_order_qty, r.clearance_review_units)]
    r.loc[r.receipt_timing_warning, 'action'] += '; verify / expedite on-order receipt timing'
    r['stockout_axis'] = r.stockout_gap / r.reorder_point.clip(lower=1)
    r['overstock_axis'] = r.excess_units / r.demand_60d.clip(lower=1)
    r['revenue_at_stake'] = r.lead_time_revenue_exposure + r.excess_units*r.price
    return r.sort_values(['priority', 'revenue_at_stake'], ascending=[True, False],
                         key=lambda x: x.map({'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}) if x.name == 'priority' else x)


def inventory_inputs(summary, future, master, snapshots, as_of):
    """Only snapshots exactly at the sales cutoff support current recommendations."""
    if snapshots is None or master is None:
        return pd.DataFrame(), ['Supplied inventory_snapshots and sku_master are required']
    available = snapshots[snapshots.Date <= as_of].sort_values('Date').groupby('SKU').tail(1)
    rows, blocked = [], []
    m = master.set_index('SKU')
    for row in summary.to_dict('records'):
        sku = row['sku']
        snap = available[available.SKU == sku]
        if snap.empty or snap.Date.iloc[0] != as_of:
            blocked.append(f'{sku}: missing snapshot at {as_of.date()}; stale snapshots are not rolled forward without receipt/movement data')
            continue
        s = snap.iloc[0]
        f = future[future.sku == sku].sort_values('date').forecast.to_numpy()
        L = int(s.Lead_Time_Days)
        if len(f) < max(60, L+REVIEW_DAYS):
            blocked.append(f'{sku}: forecast too short for lead time plus review')
            continue
        price = float(m.loc[sku, 'Selling_Price'])
        row.update(current_stock=float(s.On_Hand), on_order=float(s.On_Order), lead_time_days=L,
                   unit_cost=float(m.loc[sku, 'Cost_Price']), price=price,
                   lead_time_demand=float(f[:L].sum()), review_demand=float(f[:L+REVIEW_DAYS].sum()),
                   demand_60d=float(f[:60].sum()), snapshot_date=str(s.Date.date()))
        rows.append(row)
    return pd.DataFrame(rows), blocked


def snapshot_review(sales, master, snapshots, as_of=None):
    """Replay a decision at an actual snapshot, never roll stale stock forward.

    Safety-stock scale is the standard deviation of prior 56-day seasonal-naive
    daily residuals, a conservative origin-valid benchmark, not future model errors.
    LightGBM is fixed in this replay; no future backtest-based model selection.
    """
    from .forecast import predict_origin
    if snapshots is None or master is None:
        return pd.DataFrame(), pd.DataFrame(), ['Inventory snapshots and master required'], None
    eligible = snapshots[(snapshots.Date <= sales.Date.max()) & snapshots.SKU.isin(master.SKU) & snapshots.SKU.isin(sales.SKU)]
    if eligible.empty:
        return pd.DataFrame(), pd.DataFrame(), ['No in-scope snapshot before sales cutoff'], None
    cutoff = pd.Timestamp(as_of) if as_of is not None else eligible.Date.max()
    past = sales[sales.Date < cutoff].copy()
    at = eligible[eligible.Date == cutoff]
    if at.empty:
        return pd.DataFrame(), pd.DataFrame(), ['No snapshot at requested review date'], cutoff
    horizon = max(60, int(at.Lead_Time_Days.max())+REVIEW_DAYS)
    future, _ = predict_origin(past, cutoff, horizon, master)
    errors = past.sort_values(['SKU','Date']).copy()
    errors['residual'] = errors.Units_Sold-errors.groupby('SKU').Units_Sold.shift(7)
    errors = errors[errors.Date >= cutoff-pd.Timedelta(days=56)]
    sigma = errors.groupby('SKU').residual.std()
    summary = future.groupby('sku',as_index=False).agg(avg_daily_demand=('forecast','mean'))
    summary['demand_std'] = summary.sku.map(sigma)
    summary['inventory_model'] = 'LightGBM; sparse SKU fallback where flagged'
    summary['risk_forecast_origin'] = str(cutoff.date())
    summary['risk_error_basis'] = 'Prior 56 days seasonal-naive daily residual standard deviation'
    missing_error = summary.loc[summary.demand_std.isna(),'sku'].tolist()
    inputs, blocked = inventory_inputs(summary[summary.demand_std.notna()], future, master, eligible, cutoff)
    blocked += [f'{sku}: insufficient past errors for inventory safety stock' for sku in missing_error]
    return inputs, future, blocked, cutoff


def validate_snapshot_proxies(sales, master, snapshots):
    """Demand-coverage outcome proxies, not observed lost-sales or stockout precision."""
    if snapshots is None or master is None:
        return pd.DataFrame(), pd.DataFrame()
    candidates = sorted(snapshots.loc[(snapshots.Date < sales.Date.max()) & snapshots.SKU.isin(master.SKU),'Date'].unique())[-3:]
    rows = []
    for date in candidates:
        if (pd.Timestamp(date)-sales.Date.min()).days < 56:
            continue
        inputs, _, _, cutoff = snapshot_review(sales,master,snapshots,date)
        if inputs.empty:
            continue
        rec = compute_recommendations(inputs)
        for r in rec.itertuples():
            after = sales[(sales.SKU == r.sku) & (sales.Date >= cutoff)].sort_values('Date')
            L = int(r.lead_time_days)
            common = dict(snapshot_date=str(cutoff.date()), sku=r.sku, inventory_position=r.inventory_position,
                          on_hand=r.current_stock, forecast_origin=r.risk_forecast_origin)
            if len(after) >= L:
                actual = float(after.iloc[:L].Units_Sold.sum())
                rows.append(dict(**common,proxy='lead_time_sales_exceed_position',
                                 predicted=bool(r.stockout_gap > 0), observed_proxy=bool(actual > r.inventory_position),
                                 observed_units=actual, window_days=L))
            if len(after) >= 60:
                actual = float(after.iloc[:60].Units_Sold.sum())
                rows.append(dict(**common,proxy='on_hand_exceeds_next_60d_sales',
                                 predicted=bool(r.excess_units > 0), observed_proxy=bool(r.current_stock > actual),
                                 observed_units=actual,window_days=60))
    detail = pd.DataFrame(rows)
    scores = []
    if not detail.empty:
        for name,g in detail.groupby('proxy'):
            tp=int((g.predicted & g.observed_proxy).sum());fp=int((g.predicted & ~g.observed_proxy).sum())
            fn=int((~g.predicted & g.observed_proxy).sum());tn=int((~g.predicted & ~g.observed_proxy).sum())
            scores.append(dict(proxy=name,n=len(g),true_positive=tp,false_positive=fp,false_negative=fn,true_negative=tn,
                               proxy_precision=tp/(tp+fp) if tp+fp else np.nan,
                               proxy_recall=tp/(tp+fn) if tp+fn else np.nan))
    return detail,pd.DataFrame(scores)
