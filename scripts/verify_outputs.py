"""Independently reconcile saved metrics, weekly totals, source hashes and notebooks."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

root=Path(__file__).resolve().parents[1]
out=root/'outputs'
info=json.loads((out/'run_info.json').read_text())
for name,digest in info['source_sha256'].items():
    assert hashlib.sha256((root/'data'/name).read_bytes()).hexdigest()==digest,name
bt=pd.read_csv(out/'backtest_predictions.csv',parse_dates=['date','origin'])
metrics=pd.read_csv(out/'model_metrics.csv')
for scale in ['daily','weekly']:
    data=bt.copy()
    if scale=='weekly':
        data['block']=((data.date-data.origin).dt.days//7).astype(int)
        data=data.groupby(['origin','sku','block'])[['actual','model_forecast','baseline','moving_average']].sum()
    for model,col in [('LightGBM','model_forecast'),('Seasonal naive','baseline'),('Moving average (28d)','moving_average')]:
        expected=abs(data.actual-data[col]).sum()/data.actual.sum()*100
        stored=metrics.loc[(metrics.scale==scale)&(metrics.model==model),'WAPE_pct'].iloc[0]
        assert np.isclose(expected,stored,rtol=0,atol=1e-10),(scale,model)
for fold in info['validation_folds']:
    assert pd.Timestamp(fold['train_max_date'])<pd.Timestamp(fold['origin'])
f=pd.read_csv(out/'forecasts.csv',parse_dates=['date','origin'])
f=f[f.type=='future']
w=pd.read_csv(out/'weekly_forecasts.csv')
assert w.days.eq(7).all() and w.groupby('sku').size().eq(8).all()
np.testing.assert_allclose(f.groupby('sku').forecast.sum().sort_index(),w.groupby('sku').forecast.sum().sort_index(),rtol=0,atol=1e-9)
assert f.lower.le(f.forecast).all() and f.upper.ge(f.forecast).all()
for name in ['FORESIGHT_notebook.ipynb','FORESIGHT_notebook_executed.ipynb']:
    nb=json.loads((root/'notebooks'/name).read_text())
    code=[c for c in nb['cells'] if c['cell_type']=='code']
    assert all(c['execution_count'] is not None for c in code)
    assert not [o for c in code for o in c['outputs'] if o['output_type']=='error']
    assert not any('pip install' in ''.join(c['source']) for c in code)
print(f'Verified six WAPE values, {len(f)} future daily rows, {len(w)} full weekly rows, source hashes, fold cutoffs and both executed notebooks.')

if info.get('inventory_as_of'):
    cutoff=pd.Timestamp(info['inventory_as_of'])
    rec=pd.read_csv(out/'recommendations.csv')
    risk=pd.read_csv(out/'inventory_forecasts.csv',parse_dates=['date','origin'])
    stock=pd.read_csv(root/'data/inventory_snapshots.csv',parse_dates=['Snapshot_Date'])
    master=pd.read_csv(root/'data/sku_master.csv').set_index('SKU')
    sales=pd.read_csv(root/'data/sales_daily.csv',parse_dates=['Date'])
    at=stock[stock.Snapshot_Date==cutoff].set_index('SKU')
    for r in rec.itertuples():
        assert r.current_stock==at.loc[r.sku,'Current_Stock']
        assert r.on_order==at.loc[r.sku,'On_Order']
        assert r.unit_cost==master.loc[r.sku,'Cost_Price']
        pred=risk[risk.sku==r.sku].sort_values('date')
        assert pred.origin.eq(cutoff).all() and pred.date.min()==cutoff
        L=int(r.lead_time_days)
        assert np.isclose(pred.head(L).forecast.sum(),r.lead_time_demand)
        assert np.isclose(pred.head(L+7).forecast.sum(),r.review_demand)
        assert np.isclose(r.recommended_order_qty*r.unit_cost,r.order_value)
        assert np.isclose(max(0,r.current_stock-pred.head(60).forecast.sum())*r.unit_cost,r.excess_inventory_value)
        assert np.isclose(max(0,r.lead_time_demand-r.current_stock-r.on_order)*r.price,r.lead_time_revenue_exposure)
        past=sales[(sales.SKU==r.sku)&(sales.Date<cutoff)].sort_values('Date').copy()
        past['error']=past.Units_Sold-past.Units_Sold.shift(7)
        sigma=past.loc[past.Date>=cutoff-pd.Timedelta(days=56),'error'].std()
        assert np.isclose(sigma,r.demand_std)
    detail=pd.read_csv(out/'risk_proxy_predictions.csv',parse_dates=['snapshot_date'])
    scored=pd.read_csv(out/'risk_proxy_metrics.csv').set_index('proxy')
    for row in detail.itertuples():
        actual=sales[(sales.SKU==row.sku)&(sales.Date>=row.snapshot_date)].sort_values('Date').head(row.window_days).Units_Sold.sum()
        assert np.isclose(actual,row.observed_units)
        expected=actual>row.inventory_position if row.proxy=='lead_time_sales_exceed_position' else row.on_hand>actual
        assert bool(row.observed_proxy)==bool(expected)
    for name,g in detail.groupby('proxy'):
        counts=[(g.predicted&g.observed_proxy).sum(),(g.predicted&~g.observed_proxy).sum(),
                (~g.predicted&g.observed_proxy).sum(),(~g.predicted&~g.observed_proxy).sum()]
        assert list(scored.loc[name,['true_positive','false_positive','false_negative','true_negative']])==counts
    print(f'Verified {len(rec)} snapshot decisions, supplied costs, exact demand windows, error scales and {len(detail)} outcome proxies.')
