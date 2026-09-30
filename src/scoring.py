"""Local saved-forecast scoring contract shared with the dashboard."""
import json
from pathlib import Path
import pandas as pd
from .inventory import compute_recommendations


def load_outputs(root):
    root = Path(root)
    try:
        info = json.loads((root/'run_info.json').read_text())
        if info.get('schema_version') != 2:
            raise ValueError('Outputs are outdated; rerun the pipeline')
        fc = pd.read_csv(root/'forecasts.csv', parse_dates=['date', 'origin'])
        summary = pd.read_csv(root/'sku_inputs.csv')
        metrics = pd.read_csv(root/'model_metrics.csv')
        fc['date'] = pd.to_datetime(fc.date, errors='raise')
        fc['origin'] = pd.to_datetime(fc.origin, errors='raise')
        if fc[['sku','date','origin']].isna().any().any() or fc.duplicated(['sku','date','type']).any():
            raise ValueError('Missing or duplicate forecast keys')
        if not summary.inventory_available.isin([True, False]).all():
            raise ValueError('Invalid inventory availability flags')
        if fc.empty or summary.empty or not {'sku', 'forecast', 'type', 'baseline', 'lower', 'upper'} <= set(fc):
            raise ValueError('Forecast output is empty or malformed')
        if not {'sku', 'category', 'abc_class', 'inventory_available'} <= set(summary):
            raise ValueError('SKU output is malformed')
        if not {'model', 'scale', 'WAPE_pct'} <= set(metrics):
            raise ValueError('Metrics output is malformed')
        if summary.sku.duplicated().any():
            raise ValueError('Duplicate SKU output')
        future = fc[fc.type == 'future']
        if future.empty or not set(summary.sku) <= set(future.sku):
            raise ValueError('Missing future SKU forecasts')
        if not future.forecast.ge(0).all() or not pd.to_numeric(future.forecast, errors='coerce').map(lambda x: pd.notna(x) and abs(x) != float('inf')).all():
            raise ValueError('Invalid future forecasts')
        return fc, summary, metrics, info
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(f'Cannot load project outputs: {e}. Run python run_pipeline.py --allow-partial after repairing inputs.') from e


def score(skus, output_dir='outputs', service_level=.95):
    if not isinstance(skus, list) or not skus or any(not isinstance(s, str) or not s.strip() for s in skus):
        raise ValueError('skus must be a nonempty list of SKU strings')
    fc, summary, _, info = load_outputs(output_dir)
    if service_level not in [.90, .95, .97, .99]:
        raise ValueError('Unsupported service_level; choose 0.90, 0.95, 0.97, or 0.99')
    skus = list(dict.fromkeys(s.strip().upper() for s in skus))
    unknown = set(skus)-set(summary.sku)
    if unknown:
        raise ValueError(f'Unknown SKU(s): {sorted(unknown)}')
    selected = summary[summary.sku.isin(skus)]
    inventory = selected[selected.inventory_available == True]
    rec = compute_recommendations(inventory, service_level) if not inventory.empty else pd.DataFrame()
    return {'forecast': fc[(fc.sku.isin(skus)) & (fc.type == 'future')], 'risk': rec,
            'unavailable_risk_skus': selected.loc[selected.inventory_available != True, 'sku'].tolist(),
            'currency': info.get('currency'), 'as_of': info['as_of'], 'risk_as_of': info.get('inventory_as_of'),
            'risk_scope': info.get('inventory_scope')}
