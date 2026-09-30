from pathlib import Path
from streamlit.testing.v1 import AppTest
from src.scoring import score
import pytest

APP = str(Path(__file__).resolve().parents[1]/'app/streamlit_app.py')


def test_default_filters_and_empty_states():
    at=AppTest.from_file(APP,default_timeout=30).run()
    assert not at.exception
    assert len(at.tabs)==5
    at.selectbox(key='category_filter').set_value('Furniture').run()
    assert not at.exception
    import pandas as pd
    master=pd.read_csv(Path(APP).parents[1]/'data/sku_master.csv')
    expected=set(master.loc[master.Category=='Furniture','SKU'])
    assert set(at.selectbox(key='product_filter').options[1:])==expected
    sku=next(iter(expected))
    at.selectbox(key='product_filter').set_value(sku).run()
    assert at.metric[1].value=='1'
    at.selectbox(key='category_filter').set_value('Kitchen').run()
    assert not at.exception and at.selectbox(key='product_filter').value=='All products'
    at.selectbox(key='risk_filter').set_value('Unavailable').run()
    assert not at.exception and any('No matching SKUs' in x.value for x in at.info)
    at.button(key='reset_filters').click().run()
    assert not at.exception and at.selectbox(key='category_filter').value=='All categories'
    assert at.selectbox(key='risk_filter').value=='All statuses'
    assert at.metric[1].value=='50'
    at.select_slider(key='service_level').set_value(.99).run()
    assert not at.exception


def test_scoring_and_bad_sku():
    at=AppTest.from_file(APP,default_timeout=30).run()
    at.text_input(key='score_request').set_value('UNKNOWN').run()
    at.button(key='score_button').click().run()
    assert not at.exception and any('Unknown SKU' in x.value for x in at.error)
    result=score(['SKU001',' sku002 '])
    assert len(result['forecast'])==112
    with pytest.raises(ValueError,match='Unknown SKU'):score(['UNKNOWN'])


def test_missing_outputs(monkeypatch,tmp_path):
    monkeypatch.setenv('FORESIGHT_OUTPUT_DIR',str(tmp_path))
    at=AppTest.from_file(APP,default_timeout=30).run()
    assert not at.exception and any('Cannot load' in x.value for x in at.error)


def test_populated_inventory_and_malformed_outputs(monkeypatch,tmp_path):
    import pandas as pd
    import shutil
    from tests.test_core import risk_inputs
    root=Path(__file__).resolve().parents[1]/'outputs'
    for p in root.glob('*'):
        if p.is_file():shutil.copy2(p,tmp_path/p.name)
    summary=pd.read_csv(tmp_path/'sku_inputs.csv')
    r=risk_inputs()
    summary=summary.head(5).reset_index(drop=True)
    for col in r.columns:
        if col!='sku':summary[col]=r[col].to_numpy()
    summary['inventory_available']=True
    summary.to_csv(tmp_path/'sku_inputs.csv',index=False)
    monkeypatch.setenv('FORESIGHT_OUTPUT_DIR',str(tmp_path))
    at=AppTest.from_file(APP,default_timeout=30).run()
    assert not at.exception and len(at.tabs)==5
    assert len(at.dataframe)>=4
    (tmp_path/'run_info.json').write_text('{invalid')
    at=AppTest.from_file(APP,default_timeout=30).run()
    assert not at.exception and any('Cannot load' in x.value for x in at.error)
