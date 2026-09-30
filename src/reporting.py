"""Reports are regenerated from this run's inputs and metrics."""
from pathlib import Path
import pandas as pd
import plotly.express as px


def write_reports(sales, master, audit, metrics, summary, rec, info, root, calendar=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    end = sales.Date.max()
    recent = sales[sales.Date > end-pd.Timedelta(days=28)]
    previous = sales[(sales.Date <= end-pd.Timedelta(days=28)) & (sales.Date > end-pd.Timedelta(days=56))]
    current_total, previous_total = recent.Units_Sold.sum(), previous.Units_Sold.sum()
    trend = (current_total/previous_total-1)*100 if previous_total else float('nan')
    movers = recent.groupby('SKU').agg(units_28d=('Units_Sold', 'sum'), revenue_28d=('Revenue', 'sum'))
    movers['previous_28d_units'] = previous.groupby('SKU').Units_Sold.sum()
    movers['unit_change'] = movers.units_28d-movers.previous_28d_units
    movers = movers.sort_values('units_28d', ascending=False)
    movers.to_csv(root/'top_movers.csv')
    stock_date = info.get('inventory_as_of')
    stock_end = pd.Timestamp(stock_date) if stock_date else end
    stock_recent = sales[(sales.Date < stock_end) & (sales.Date >= stock_end-pd.Timedelta(days=28))]
    stock_totals = stock_recent.groupby('SKU').Units_Sold.sum()
    zeros = summary[summary.sku.isin(stock_totals.index[stock_totals == 0])].copy()
    # A true dead-stock candidate must have stock, not merely zero observed sales.
    dead = zeros[zeros.current_stock > 0] if 'current_stock' in zeros else pd.DataFrame()
    dead.to_csv(root/'dead_stock_candidates.csv', index=False)
    daily = sales.groupby('Date', as_index=False).Units_Sold.sum()
    dow = sales.assign(weekday=sales.Date.dt.day_name()).groupby('weekday').Units_Sold.mean().reindex(
        ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']).reset_index()
    month = sales.assign(month=sales.Date.dt.month).groupby('month', as_index=False).Units_Sold.mean()
    weekend = sales.groupby(sales.Date.dt.dayofweek >= 5).Units_Sold.mean()
    weekend_lift = (weekend.get(True, float('nan'))/weekend.get(False, float('nan'))-1)*100
    promo = sales.groupby('Promotion').Units_Sold.mean()
    promo_lift = (promo.get(1, float('nan'))/promo.get(0, float('nan'))-1)*100
    calendar_text = 'No calendar event fields available for analysis.'
    if calendar is not None and {'is_holiday','promotion_event'} <= set(calendar):
        joined = sales.merge(calendar[['Date','is_holiday','promotion_event']], on='Date', validate='many_to_one')
        holiday = joined.groupby('is_holiday',as_index=False).agg(mean_units=('Units_Sold','mean'),sku_days=('Units_Sold','size'),calendar_days=('Date','nunique'))
        event = joined.groupby('promotion_event',as_index=False).agg(mean_units=('Units_Sold','mean'),sku_days=('Units_Sold','size'),calendar_days=('Date','nunique'))
        holiday.to_csv(root/'holiday_summary.csv',index=False)
        event.to_csv(root/'promotion_event_summary.csv',index=False)
        calendar_text = 'Holiday and named-event means are saved in holiday_summary.csv and promotion_event_summary.csv with sample counts. None is a literal no-event label, not an imputed missing value. These descriptive comparisons are not causal effects and are not used as future-known plans.'
    figures = [px.line(daily, x='Date', y='Units_Sold', title='Daily units sold: historical trend', labels={'Units_Sold':'Units sold'}),
               px.bar(dow, x='weekday', y='Units_Sold', title='Average units per SKU-day by weekday', labels={'Units_Sold':'Mean units / SKU-day'}),
               px.bar(month, x='month', y='Units_Sold', title='Seasonality: average units per SKU-day by month', labels={'Units_Sold':'Mean units / SKU-day'}),
               px.bar(movers.head(10).reset_index(), x='SKU', y='units_28d', title='Top ten movers: last 28 observed days', labels={'units_28d':'Units sold'})]
    (root/'eda_charts.html').write_text('<html><head><meta charset="utf-8"><title>FORESIGHT EDA</title></head><body>'+''.join(
        fig.to_html(full_html=False, include_plotlyjs=True if i == 0 else False) for i,fig in enumerate(figures))+'</body></html>')
    best = metrics[metrics.scale == 'weekly'].sort_values('WAPE_pct').iloc[0]
    model = metrics[(metrics.scale == 'weekly') & (metrics.model == 'LightGBM')].iloc[0]
    base = metrics[(metrics.scale == 'weekly') & (metrics.model == 'Seasonal naive')].iloc[0]
    proxy_text = ('No proxy windows could be evaluated.' if not info.get('risk_proxy_metrics') else '\n'.join(
        f"- {m['proxy']}: n={m['n']}, TP={m['true_positive']}, FP={m['false_positive']}, FN={m['false_negative']}, TN={m['true_negative']}; proxy precision={m['proxy_precision']}, recall={m['proxy_recall']}" for m in info['risk_proxy_metrics']))
    missing = ', '.join(audit['missing_extracts']) or 'None'
    quality = '\n'.join(f'- {k}: {len(v)} SKUs; full IDs in outputs/data_quality.json' if k == 'inventory_unmatched_skus' else f'- {k}: {v}' for k,v in audit.items())
    memo = f'''# Data-quality and EDA memo

As of {end.date()}; {len(sales):,} sales rows, {sales.SKU.nunique()} observed SKUs. Supplied extracts missing: {missing}.
Currency: {info.get('currency') or 'unconfirmed; revenue and costs retain source units'}.

## Treatment and quality findings

{quality}

Missing required values and invalid types fail validation rather than being guessed. Exact duplicates are removed after label normalization; conflicting business keys fail. SKU/date joins are validated. Inventory joins use backward snapshots, never future snapshots. Internal sales-date gaps are rejected rather than imputed as zero. Launch-date anomalies and negative margins are retained and disclosed for source-owner review; deleting these observations would silently alter history. A current, undated master is not used as a historical forecasting feature. Calendar descriptive fields are joined when supplied, but are not assumed known in advance for backtesting.

## Business insights and actions

1. Recent 28-day sales total {current_total:,.0f} units versus {previous_total:,.0f} in the preceding 28 days ({trend:+.1f}%). Review procurement targets weekly as the trend changes; do not extrapolate a two-period change as annual growth.
2. Weekend SKU-day demand is {weekend_lift:+.1f}% relative to weekdays. Schedule warehouse picking capacity and replenishment reviews ahead of weekends.
3. Promotion days show {promo_lift:+.1f}% average observed demand relative to non-promotion days. This is an association, not causal promotion lift; use an explicit promotion scenario and check margin before budgeting a campaign.
4. The highest recent-volume SKU is {movers.index[0]} with {movers.iloc[0].units_28d:,.0f} units in 28 days. Prioritise availability checks for the top movers in top_movers.csv. Category and launch-date mix can confound comparisons.
5. Seasonal monthly means peak in month {int(month.loc[month.Units_Sold.idxmax(), 'month'])} and are lowest in month {int(month.loc[month.Units_Sold.idxmin(), 'month'])}. Use this to time planning reviews; only two years of history support these patterns.

## Calendar context

{calendar_text}

## Slow movers and dead stock

{len(zeros)} observed SKUs have zero sales in the 28 days strictly before the stock review date {stock_date or 'unavailable'}. Zero sales alone do not establish dead stock. Snapshot-aligned dead-stock candidates: {len(dead) if info['inventory_skus'] else 'unavailable because current inventory is missing'}. Master-only new products are marked low-confidence and use category peers where available. No missing-day sales are fabricated. Dead stock means positive snapshot stock with zero observed sales in the preceding 28 days; it does not imply a confirmed clearance recovery. The 150 inventory-only SKUs, when present, are outside the sales/master scope and remain unscored, with raw records retained in outputs/inventory_unmatched.csv.

## Snapshot coverage and outcome checks

Stock review date: {stock_date}. This is a historical review, not current inventory at the later sales cutoff. Safety-stock scale uses prior 56-day seasonal-naive daily errors available before the snapshot. Provider Inventory_Value is retained but not used when it fails reconciliation with supplied master cost. See the audit counts above.

{proxy_text}

These are demand-coverage proxies from subsequent observed sales, not actual lost-sales/stockout precision. Monthly positive snapshots do not prove that stockouts never occurred between snapshots. Unknown receipts, transfers and censored sales limit interpretation. No positive proxy cases means recall is undefined, not perfect.

See [labelled charts](eda_charts.html), [top movers](top_movers.csv), and ../outputs/data_quality.json for the machine-readable audit.
'''
    (root/'DATA_QUALITY_EDA_MEMO.md').write_text(memo)
    unit = info.get('currency') or 'source currency units (not confirmed INR)'
    impact = ('No in-scope stock positions are available; financial exposure is not reportable.' if rec.empty else
              f"Historical snapshot review at {stock_date}: proposed order spend {rec.order_value.sum():,.2f}; "
              f"excess stock at supplied cost {rec.excess_inventory_value.sum():,.2f}; "
              f"lead-time revenue exposure net of on-order {rec.lead_time_revenue_exposure.sum():,.2f}. "
              f"All amounts are {unit}. On-hand-only revenue exposure if receipts are delayed: {rec.receipt_delay_revenue_exposure.sum():,.2f}; this overlaps the net exposure and must not be added to it.")
    if not info.get('currency'):
        impact += ' The brief asks for rupee impact (pages 5, 11-13), but does not explicitly state the CSV currency or an INR conversion. No currency conversion or INR assumption has been applied.'
    if rec.empty:
        actions = 'No supported SKU-specific snapshot decision is available.'
    else:
        actions = '| SKU | Priority | Order units | Clearance review units | Action |\n|---|---|---:|---:|---|\n'
        actions += '\n'.join(f'| {r.sku} | {r.priority} | {r.recommended_order_qty:.0f} | {r.clearance_review_units:.0f} | {r.action} |' for r in rec.head(10).itertuples())
    executive = f'''# FORESIGHT executive readout

## Financial decision

{impact} These quantities are scenario exposures, not achieved savings, expected losses, or additive benefits. Revenue at risk is not profit. Clearance proceeds require an approved discount and sell-through estimate; none is assumed.

## Historical snapshot actions — verify fresh stock before execution

{actions}

Full prioritised quantities, cost exposure and actions: outputs/recommendations.csv. {len(rec)} in-scope SKUs are scored; {info.get('inventory_unmatched_skus', 0)} inventory-only SKUs have no supplied sales/master match and are not assigned fabricated demand or cost. No purchase order or clearance execution is authorized or performed.

Operations can already prioritise demand reviews for {', '.join(movers.head(5).index)} based on recent unit volume. Finance should review {len(audit.get('negative_margin_skus', []))} SKUs with master cost above selling price. Resolve {audit.get('sales_before_launch_rows', 0)} sales rows dated before recorded product launch before relying on launch-based lifecycle analysis.

## Forecast evidence

Three sequential, non-overlapping 56-day folds retrain at every origin, each using only preceding observations. Weekly scores aggregate matching seven-day blocks anchored to each origin. LightGBM weekly WAPE is {model.WAPE_pct:.3f}%, versus {base.WAPE_pct:.3f}% for seasonal naive; weekly bias is {model.Bias_pct:+.3f}%. The lowest observed weekly WAPE belongs to {best.model} ({best.WAPE_pct:.3f}%). Selected forecast: {info['selected_model']}. This selection uses the backtest and is not an independent final holdout estimate. WAPE measures aggregate absolute error relative to units sold, not a probability of correctness. Daily scores and fold-level results are in outputs/model_metrics.csv and outputs/fold_metrics.csv.

## Practical use

Use the eight-week forecast for planning from {info['forecast_start']} through {info['forecast_end']}. These dates follow the historical extract cutoff; they are not current real-time predictions. The dashboard shows category/SKU filters, actual and baseline curves, local saved-forecast scoring, and risk only where supported. A supplemental 60-day (or longer lead-time) demand forecast feeds the inventory rule, without extending the eight-week reported evaluation horizon.

## Limitations and decisions outstanding

Missing extracts: {missing}. Historical stock review date: {stock_date}.

{proxy_text}

The checks above measure demand-coverage proxies, not actual stockout precision or achieved business benefit. Monthly snapshots, missing receipts and unobserved unmet demand prevent that stronger validation. On-order offsets inventory-position risk and new purchases per brief section 8.1. Immediate on-hand shortfalls remain a separate receipt-timing warning; receipt dates are unknown. Overstock uses physical on-hand above 60-day forecast demand, with incoming excess recorded separately. The high-both quadrant requires investigation before buying or clearing. Inventory safety stock assumes independent daily errors and stable lead times; its error scale is prior seasonal-naive residual variation known before the snapshot. Inventory replay uses fixed LightGBM rather than selecting a model using future outcomes. The displayed bands are approximate nominal 95% central normal error bands, estimated from previous backtest residuals for final forecasts only, without empirical calibration. Weekly variance includes within-week error correlation by estimating errors on weekly sums. Sparse/new SKU fallbacks carry a low-confidence flag and may lack a band if no validation history exists.

Future promotion plans are unavailable. Base forecasts assume no promotions, with last known price at each origin. An all-promotion sensitivity scenario illustrates model response; it is not a business plan or causal impact estimate. The supplied calendar is joined and profiled; its retrospective promotion-event labels are not assumed to be advance-known plans. No deployment, publishing, demo or submission work is included. Calibrated intervals and monitoring are optional stretch goals.
'''
    (root/'EXECUTIVE_READOUT.md').write_text(executive)
