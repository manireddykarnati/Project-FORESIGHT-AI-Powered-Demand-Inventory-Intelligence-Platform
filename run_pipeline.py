"""Validated local pipeline. Default requires all four supplied extracts."""
import os
os.environ.setdefault('OMP_NUM_THREADS', '1')
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import numpy as np
import pandas as pd
from src.data import ingest
from src.forecast import backtest, predict_origin, weekly, metrics, train_model, MODEL, HORIZON
from src.features import FEATURES
from src.inventory import snapshot_review, validate_snapshot_proxies, compute_recommendations
from src.reporting import write_reports

ROOT = Path(__file__).resolve().parent


def run(data_dir, output_dir, report_dir, allow_partial=False, currency=None):
    tables, ready, audit = ingest(data_dir, allow_partial)
    sales, master = tables['sales_daily'], tables.get('sku_master')
    if currency is not None and currency != 'INR':
        raise ValueError('Only confirmed INR is accepted; omit --currency when unknown')
    bt, folds = backtest(sales)
    wb = weekly(bt)
    scores = pd.concat([metrics(bt, 'daily'), metrics(wb, 'weekly')], ignore_index=True)
    selected = scores[scores.scale == 'weekly'].sort_values(['WAPE_pct', 'model']).iloc[0].model
    select_col = {MODEL:'forecast', 'Seasonal naive':'baseline', 'Moving average (28d)':'moving_average'}[selected]
    end = sales.Date.max()
    origin = end+pd.Timedelta(days=1)
    inv = tables.get('inventory_snapshots')
    horizon = max(60, int(inv.Lead_Time_Days.max())+7 if inv is not None else 60)
    future, final_audit = predict_origin(sales, origin, horizon, master)
    future['model_forecast'] = future.forecast
    future['forecast'] = future[select_col]
    bt['model_forecast'] = bt.forecast
    bt['forecast'] = bt[select_col]
    wb_selected = weekly(bt)
    # Fit uncertainty on validation residuals only for subsequent final forecasts.
    err = (bt.actual-bt.forecast).groupby(bt.sku).std()
    werr = (wb_selected.actual-wb_selected.forecast).groupby(wb_selected.sku).std()
    future['lower'] = (future.forecast-1.96*future.sku.map(err)).clip(lower=0)
    future['upper'] = future.forecast+1.96*future.sku.map(err)
    future['type'] = 'future'
    bt['type'] = 'backtest'
    bt['lower'], bt['upper'] = np.nan, np.nan
    fc = pd.concat([bt, future[future.date < origin+pd.Timedelta(days=HORIZON)]], ignore_index=True)
    wf = weekly(future[future.date < origin+pd.Timedelta(days=HORIZON)])
    wf['lower'] = (wf.forecast-1.96*wf.sku.map(werr)).clip(lower=0)
    wf['upper'] = wf.forecast+1.96*wf.sku.map(werr)
    summary = future.groupby('sku', as_index=False).agg(avg_daily_demand=('forecast','mean'), low_confidence=('low_confidence','max'), method=('method','first'))
    summary['demand_std'] = summary.sku.map(err)
    per_sku = bt.groupby('sku').apply(lambda g: float((g.actual-g.forecast).abs().sum()/g.actual.sum()*100) if g.actual.sum() else np.nan, include_groups=False)
    summary['wape_pct'] = summary.sku.map(per_sku)
    if selected != MODEL:
        summary.loc[~summary.low_confidence, 'method'] = selected
    summary['forecast_56d_units'] = summary.sku.map(wf.groupby('sku').forecast.sum())
    summary['category'] = summary.sku.map(master.set_index('SKU').Category) if master is not None else 'Category unavailable'
    summary['hist_revenue'] = summary.sku.map(sales.groupby('SKU').Revenue.sum()).fillna(0)
    summary['price'] = summary.sku.map(sales.groupby('SKU').Price.last())
    summary = summary.sort_values('hist_revenue', ascending=False)
    total = summary.hist_revenue.sum()
    before = (summary.hist_revenue.cumsum()-summary.hist_revenue)/total if total else pd.Series(1., index=summary.index)
    summary['abc_class'] = np.where(before < .8, 'A', np.where(before < .95, 'B', 'C'))
    inputs, risk_forecasts, blocked, risk_cutoff = snapshot_review(sales, master, inv)
    summary['inventory_available'] = summary.sku.isin(inputs.sku) if not inputs.empty else False
    if not inputs.empty:
        summary = summary.rename(columns={'avg_daily_demand':'forecast_avg_daily_demand', 'demand_std':'forecast_error_std'})
        summary = summary.drop(columns=['price'])
        extras = [c for c in inputs if c not in summary or c == 'sku']
        summary = summary.merge(inputs[extras], on='sku', how='left', validate='one_to_one')
    proxy_detail, proxy_metrics = validate_snapshot_proxies(sales, master, inv)
    rec = compute_recommendations(inputs) if not inputs.empty else pd.DataFrame(columns=['sku','flag','action','recommended_order_qty','order_value'])
    # Explicit all-promotion sensitivity; never treated as a known promotion plan.
    plan = {(s, d): 1 for s in summary.sku for d in pd.date_range(origin, periods=HORIZON)}
    scenario, _ = predict_origin(sales, origin, HORIZON, master, plan)
    scenario = scenario.rename(columns={'forecast':'all_promotion_model_forecast'})
    scenario = scenario.merge(future[['sku','date','model_forecast']], on=['sku','date'])
    info = dict(schema_version=2, as_of=str(end.date()), forecast_start=str(origin.date()),
                forecast_end=str((origin+pd.Timedelta(days=HORIZON-1)).date()), horizon_days=HORIZON,
                test_start=str(bt.date.min().date()), test_end=str(bt.date.max().date()),
                selected_model=selected, currency=currency, missing_extracts=audit['missing_extracts'],
                inventory_skus=len(rec), inventory_blockers=blocked,
                inventory_as_of=str(risk_cutoff.date()) if risk_cutoff is not None else None,
                inventory_scope='Historical snapshot review; not current stock',
                inventory_unmatched_skus=len(audit.get('inventory_unmatched_skus', [])),
                risk_proxy_metrics=proxy_metrics.astype(object).where(pd.notna(proxy_metrics), None).to_dict('records') if not proxy_metrics.empty else [],
                interval='Approximate nominal 95% central normal error band; not calibrated',
                source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(data_dir).glob('*.csv')},
                model_parameters='LightGBM 600 trees, learning_rate=.03, seed=42, n_jobs=1',
                validation_folds=folds, final_fit=final_audit)
    final_model = train_model(sales, {s:i for i,s in enumerate(sorted(summary.sku))})
    importance = pd.DataFrame({'feature':FEATURES, 'importance':final_model.booster_.feature_importance('gain')}) if final_model is not None else pd.DataFrame(columns=['feature','importance'])
    if not importance.empty and importance.importance.sum():
        importance['importance'] = importance.importance/importance.importance.sum()*100
    out = Path(output_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.foresight-', dir=out.parent))
    try:
        for name, frame in [('analysis_ready',ready),('forecasts',fc),('weekly_forecasts',wf),('backtest_predictions',bt),
                            ('weekly_backtest',wb_selected),('model_metrics',scores),('sku_inputs',summary),('recommendations',rec),
                            ('promotion_scenario',scenario),('feature_importance',importance),
                            ('inventory_forecasts',risk_forecasts),('risk_proxy_predictions',proxy_detail),('risk_proxy_metrics',proxy_metrics),
                            ('inventory_unmatched', inv[~inv.SKU.isin(master.SKU)] if inv is not None and master is not None else pd.DataFrame(columns=['SKU']))]:
            frame.to_csv(stage/f'{name}.csv', index=False)
        fm = pd.concat([metrics(g, scale).assign(origin=str(o.date())) for scale, f in [('daily',bt.assign(forecast=bt.model_forecast)),('weekly',wb)] for o,g in f.groupby('origin')])
        fm.to_csv(stage/'fold_metrics.csv', index=False)
        for name,obj in [('run_info',info),('data_quality',audit)]:
            (stage/f'{name}.json').write_text(json.dumps(obj, indent=2, allow_nan=False))
        write_reports(sales, master, audit, scores, summary, rec, info, report_dir, tables.get('calendar'))
        out.mkdir(parents=True, exist_ok=True)
        for p in stage.iterdir():
            p.replace(out/p.name)
    finally:
        shutil.rmtree(stage)
    print(scores.to_string(index=False))
    print(f'Selected: {selected}; supplied inventory decisions: {len(rec)}; missing: {audit["missing_extracts"]}')
    return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'outputs')
    parser.add_argument('--report-dir', type=Path, default=ROOT/'reports')
    parser.add_argument('--allow-partial', action='store_true', help='Explicitly allow missing extracts; unavailable risk stays blocked')
    parser.add_argument('--currency', choices=['INR'], help='Use only after source-owner confirmation')
    args = parser.parse_args()
    try:
        run(args.data_dir, args.output_dir, args.report_dir, args.allow_partial, args.currency)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'Pipeline input error: {exc}\n')
