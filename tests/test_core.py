"""Synthetic fixtures live only in temporary test directories, never project data."""
import json
import numpy as np
import pandas as pd
import pytest
from src.data import ingest, clean_table
from src.features import build_training_frame, FEATURES
from src.forecast import predict_origin, backtest, weekly
from src.inventory import compute_recommendations, inventory_inputs
from src.scoring import score, load_outputs


def synthetic_sales(days=100):
    return pd.DataFrame({'Date':pd.date_range('2024-01-01',periods=days),'SKU':'TEST001',
                         'Units_Sold':np.arange(days)%7+1.,'Revenue':20.,'Price':5.,'Promotion':0})


def write_sources(root):
    s=synthetic_sales()
    s.to_csv(root/'sales_daily.csv',index=False)
    pd.DataFrame({'SKU':['TEST001'],'Category':['Test category'],'Cost_Price':[2.],
                  'Selling_Price':[5.],'Launch_Date':['2023-01-01']}).to_csv(root/'sku_master.csv',index=False)
    pd.DataFrame({'Date':s.Date,'Holiday':[0]*len(s)}).to_csv(root/'calendar.csv',index=False)
    pd.DataFrame({'Date':[s.Date.iloc[1],s.Date.iloc[-1]],'SKU':['TEST001']*2,
                  'On_Hand':[3.,4.],'On_Order':[2.,1.],'Lead_Time_Days':[3,3]}).to_csv(root/'inventory_snapshots.csv',index=False)


def test_ingestion_asof_cleaning(tmp_path):
    write_sources(tmp_path)
    p=tmp_path/'sales_daily.csv'
    d=pd.read_csv(p);d=pd.concat([d,d.iloc[[0]]]);d['SKU']=' test001 ';d.to_csv(p,index=False)
    tables,ready,audit=ingest(tmp_path)
    assert len(ready)==100 and audit['sales_daily']['exact_duplicates_removed']==1
    assert ready.iloc[0].On_Hand != ready.iloc[0].On_Hand  # no future snapshot fill
    assert ready.iloc[1].On_Hand==3 and ready.iloc[-1].On_Hand==4
    assert ready.Category.eq('Test category').all()


@pytest.mark.parametrize('column,value',[('Units_Sold',-1),('Price',float('inf')),('Promotion',2),('Date','bad'),('SKU','')])
def test_invalid_sales(tmp_path,column,value):
    d=synthetic_sales();d[column]=d[column].astype(object);d.loc[0,column]=value
    p=tmp_path/'sales.csv';d.to_csv(p,index=False)
    with pytest.raises(ValueError):clean_table(p,'sales_daily',{})


def test_missing_conflicts_and_gaps(tmp_path):
    with pytest.raises(ValueError,match='Missing supplied'):ingest(tmp_path)
    write_sources(tmp_path)
    p=tmp_path/'sales_daily.csv';d=pd.read_csv(p)
    bad=pd.concat([d,d.iloc[[0]].assign(Units_Sold=99)])
    bad.to_csv(p,index=False)
    with pytest.raises(ValueError,match='conflicting'):ingest(tmp_path)
    d.drop(index=5).to_csv(p,index=False)
    with pytest.raises(ValueError,match='missing dates'):ingest(tmp_path)


def test_lags_do_not_see_target_or_future():
    s=synthetic_sales();s['sku_code']=0
    before=build_training_frame(s)
    s.loc[s.index>=60,'Units_Sold']=9999
    after=build_training_frame(s)
    pd.testing.assert_series_equal(before.loc[60,FEATURES],after.loc[60,FEATURES])


def test_origin_isolation_and_refits(monkeypatch):
    import src.forecast as mod
    calls=[]
    class Model:
        def predict(self,x):return x.roll_mean_7.to_numpy()
    def train(s,m):calls.append(s.Date.max());return Model()
    monkeypatch.setattr(mod,'train_model',train)
    s=synthetic_sales(140);origin=s.Date.iloc[80]
    a,audit=predict_origin(s,origin,14)
    changed=s.copy();changed.loc[changed.Date>=origin,['Price','Promotion','Units_Sold']]=999
    b,_=predict_origin(changed,origin,14)
    pd.testing.assert_frame_equal(a,b)
    assert pd.Timestamp(audit['train_max_date'])<origin
    calls.clear();bt,logs=backtest(s,horizon=14,folds=3)
    assert len(calls)==3 and len(set(calls))==3
    assert all(pd.Timestamp(x['train_max_date'])<pd.Timestamp(x['origin']) for x in logs)
    assert len(bt)==42


def test_weekly_totals():
    d=pd.DataFrame({'date':pd.date_range('2024-01-04',periods=56),'origin':pd.Timestamp('2024-01-04'),
                    'sku':'TEST','forecast':1.,'actual':2.,'baseline':3.})
    w=weekly(d)
    assert len(w)==8 and w.days.eq(7).all()
    assert w.forecast.sum()==56 and w.actual.sum()==112
    assert w.week_start.iloc[0]==pd.Timestamp('2024-01-04')


def risk_inputs():
    return pd.DataFrame({'sku':['SHORT','EXCESS','BOTH','OK','INBOUND'],'current_stock':[0,100,100,20,0],
                         'on_order':[0,0,0,0,20],'lead_time_days':3,'unit_cost':2.,'price':5.,'demand_std':[0.,0.,40.,0.,0.],
                         'lead_time_demand':10.,'review_demand':20.,'demand_60d':60.,'avg_daily_demand':1.})


def test_quadrants_onorder_and_action_consistency():
    r=compute_recommendations(risk_inputs()).set_index('sku')
    assert r.loc['SHORT','flag']=='Reorder now'
    assert r.loc['EXCESS','flag']=='Markdown / clear'
    assert r.loc['BOTH','flag']=='Watch / volatile'
    assert r.loc['OK','flag']=='Healthy'
    assert r.loc['INBOUND','recommended_order_qty']==0 and 'expedite' in r.loc['INBOUND','action']
    assert r.loc['SHORT','order_value']==40 and r.loc['SHORT','lead_time_revenue_exposure']==50
    assert r.loc['EXCESS','excess_inventory_value']==80
    assert r.loc['BOTH','recommended_order_qty']==0 and r.loc['BOTH','clearance_review_units']==0
    assert r.loc['OK','recommended_order_qty']==0
    with pytest.raises(ValueError):compute_recommendations(risk_inputs(),.5)
    d=risk_inputs();d.loc[0,'on_order']=-1
    with pytest.raises(ValueError):compute_recommendations(d)


def test_inventory_sums_and_stale_snapshots():
    end=pd.Timestamp('2024-01-01')
    future=pd.DataFrame({'sku':'TEST','date':pd.date_range('2024-01-02',periods=60),'forecast':np.arange(1,61.)})
    summary=pd.DataFrame({'sku':['TEST'],'demand_std':[1.]})
    master=pd.DataFrame({'SKU':['TEST'],'Cost_Price':[2.],'Selling_Price':[5.]})
    snap=pd.DataFrame({'SKU':['TEST'],'Date':[end],'On_Hand':[4.],'On_Order':[2.],'Lead_Time_Days':[3]})
    i,errors=inventory_inputs(summary,future,master,snap,end)
    assert not errors and i.lead_time_demand.iloc[0]==6 and i.review_demand.iloc[0]==55
    snap['Date']=end-pd.Timedelta(days=1)
    i,errors=inventory_inputs(summary,future,master,snap,end)
    assert i.empty and errors


def test_sparse_category_fallback():
    s=synthetic_sales(20)
    master=pd.DataFrame({'SKU':['TEST001','NEW'],'Category':['Test','Test']})
    f,_=predict_origin(s,s.Date.max()+pd.Timedelta(days=1),7,master)
    assert f.low_confidence.all() and set(f.sku)=={'TEST001','NEW'}
    assert f[f.sku=='NEW'].method.eq('category mean fallback').all()


def test_scoring_invalid(tmp_path):
    for value in [None,[],[''],[1],'TEST']:
        with pytest.raises(ValueError):score(value,tmp_path)
    with pytest.raises(ValueError,match='Cannot load'):load_outputs(tmp_path)


def test_full_pipeline_synthetic_only(tmp_path):
    from run_pipeline import run
    data=tmp_path/'data';data.mkdir()
    write_sources(data)
    s=synthetic_sales(224);s.to_csv(data/'sales_daily.csv',index=False)
    pd.DataFrame({'Date':s.Date}).to_csv(data/'calendar.csv',index=False)
    pd.DataFrame({'Date':[s.Date.max()],'SKU':['TEST001'],'On_Hand':[2.],
                  'On_Order':[3.],'Lead_Time_Days':[3]}).to_csv(data/'inventory_snapshots.csv',index=False)
    out=tmp_path/'out'
    info=run(data,out,tmp_path/'reports',currency='INR')
    assert not info['missing_extracts'] and info['inventory_skus']==1
    result=score(['TEST001'],out)
    assert len(result['forecast'])==56 and len(result['risk'])==1
    rec=pd.read_csv(out/'recommendations.csv')
    pd.testing.assert_series_equal(result['risk'].reset_index(drop=True).order_value,rec.order_value,check_names=False)
    w=pd.read_csv(out/'weekly_forecasts.csv')
    assert len(w)==8 and w.days.eq(7).all()
    assert w.lower.le(w.forecast).all() and w.upper.ge(w.forecast).all()
    saved=pd.read_csv(out/'model_metrics.csv')
    bt=pd.read_csv(out/'backtest_predictions.csv')
    expected=abs(bt.actual-bt.model_forecast).sum()/bt.actual.sum()*100
    assert saved.loc[(saved.model=='LightGBM')&(saved.scale=='daily'),'WAPE_pct'].iloc[0]==pytest.approx(expected)
    # Corrupt a required output field and verify graceful loading.
    pd.DataFrame({'bad':[1]}).to_csv(out/'forecasts.csv',index=False)
    with pytest.raises(ValueError,match='Cannot load'):score(['TEST001'],out)


def test_zero_demand_and_unknown_join(tmp_path):
    from src.forecast import metrics
    d=pd.DataFrame({'actual':[0.], 'forecast':[0.], 'baseline':[0.], 'moving_average':[0.]})
    assert metrics(d,'daily').WAPE_pct.isna().all()
    r=risk_inputs();r.loc[0,['avg_daily_demand','demand_60d','lead_time_demand','review_demand']]=0
    result=compute_recommendations(r)
    assert not np.isinf(result.select_dtypes('number')).any().any()
    write_sources(tmp_path)
    p=tmp_path/'sku_master.csv';m=pd.read_csv(p);m['SKU']='UNKNOWN';m.to_csv(p,index=False)
    with pytest.raises(ValueError,match='unknown sales SKU'):ingest(tmp_path)


def test_provider_aliases_and_unmatched_inventory_retained(tmp_path):
    write_sources(tmp_path)
    p=tmp_path/'calendar.csv';d=pd.read_csv(p);d=d.rename(columns={'Date':'date'});d['promotion_event']='None';d.to_csv(p,index=False)
    p=tmp_path/'inventory_snapshots.csv';d=pd.read_csv(p);d=pd.concat([d,d.iloc[[0]].assign(SKU='UNMATCHED')])
    d=d.rename(columns={'Date':'Snapshot_Date','On_Hand':'Current_Stock'});d.to_csv(p,index=False)
    tables,ready,audit=ingest(tmp_path)
    assert audit['inventory_unmatched_skus']==['UNMATCHED']
    assert audit['inventory_unmatched_rows']==1 and len(tables['inventory_snapshots'])==3
    assert len(ready)==100 and tables['calendar'].promotion_event.eq('None').all()
    assert audit['calendar']['column_mapping']=={'date':'Date'}


def test_snapshot_replay_has_no_same_day_or_future_leakage(monkeypatch):
    import src.forecast as mod
    from src.inventory import snapshot_review
    s=synthetic_sales(100);cutoff=s.Date.iloc[70]
    master=pd.DataFrame({'SKU':['TEST001'],'Category':['Test'],'Cost_Price':[2.],'Selling_Price':[5.]})
    snap=pd.DataFrame({'SKU':['TEST001'],'Date':[cutoff],'On_Hand':[10.],'On_Order':[2.],'Lead_Time_Days':[3]})
    seen=[]
    def predict(past,origin,horizon,master):
        seen.append((past.Date.max(),origin))
        return pd.DataFrame({'sku':'TEST001','date':pd.date_range(origin,periods=horizon),
                             'forecast':float(past.Units_Sold.mean())}),{}
    monkeypatch.setattr(mod,'predict_origin',predict)
    a,_,_,_=snapshot_review(s,master,snap)
    changed=s.copy();changed.loc[changed.Date>=cutoff,['Units_Sold','Price']]=99999
    b,_,_,_=snapshot_review(changed,master,snap)
    pd.testing.assert_frame_equal(a,b)
    assert all(last < origin == cutoff for last,origin in seen)
