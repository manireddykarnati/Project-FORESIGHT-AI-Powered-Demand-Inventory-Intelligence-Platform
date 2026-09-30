"""Strict source contracts; no fabricated dimensions, inventory, or missing-day sales."""
from pathlib import Path
import numpy as np
import pandas as pd

SCHEMAS = {
    'sales_daily': ['Date', 'SKU', 'Units_Sold', 'Revenue', 'Price', 'Promotion'],
    'sku_master': ['SKU', 'Category', 'Cost_Price', 'Selling_Price', 'Launch_Date'],
    'calendar': ['Date'],
    'inventory_snapshots': ['Date', 'SKU', 'On_Hand', 'On_Order', 'Lead_Time_Days'],
}
KEYS = {'sales_daily': ['SKU', 'Date'], 'sku_master': ['SKU'], 'calendar': ['Date'],
        'inventory_snapshots': ['SKU', 'Date']}
NUMBERS = {'sales_daily': ['Units_Sold', 'Revenue', 'Price', 'Promotion'],
           'sku_master': ['Cost_Price', 'Selling_Price'], 'calendar': [],
           'inventory_snapshots': ['On_Hand', 'On_Order', 'Lead_Time_Days']}


def clean_table(path, name, audit):
    d = pd.read_csv(path, keep_default_na=False)
    aliases = {'calendar': {'date':'Date'},
               'inventory_snapshots': {'Snapshot_Date':'Date', 'Current_Stock':'On_Hand'}}.get(name, {})
    applied = {a:b for a,b in aliases.items() if a in d.columns}
    if any(b in d.columns for b in applied.values()):
        raise ValueError(f'{name}: ambiguous canonical and provider column names')
    d = d.rename(columns=applied)
    missing = set(SCHEMAS[name]) - set(d.columns)
    if missing:
        raise ValueError(f'{name}: missing columns {sorted(missing)}; see docs/DATA_CONTRACT.md')
    before = len(d)
    changes = 0
    for col in d.select_dtypes(include=['object', 'string']).columns:
        old = d[col].copy()
        d[col] = d[col].str.strip().replace('', pd.NA)
        if col in ['SKU', 'Currency']:
            d[col] = d[col].str.upper()
        changes += int((old.fillna('') != d[col].fillna('')).sum())
    if d[SCHEMAS[name]].isna().any().any():
        raise ValueError(f'{name}: missing required values; repair source, no demand/stock/cost imputation')
    if 'Date' in d:
        parsed = pd.to_datetime(d.Date, errors='coerce', format='%Y-%m-%d')
        if parsed.isna().any():
            raise ValueError(f'{name}: invalid Date; use YYYY-MM-DD')
        d['Date'] = parsed
    if name == 'sku_master':
        d['Launch_Date'] = pd.to_datetime(d.Launch_Date, errors='coerce', format='%Y-%m-%d')
        if d.Launch_Date.isna().any():
            raise ValueError('sku_master: invalid Launch_Date')
    for col in NUMBERS[name]:
        d[col] = pd.to_numeric(d[col], errors='coerce')
        if (~np.isfinite(d[col]) | (d[col] < 0)).any():
            raise ValueError(f'{name}: {col} must be finite and nonnegative')
    if name == 'inventory_snapshots' and ((d.Lead_Time_Days < 1) | (d.Lead_Time_Days % 1 != 0)).any():
        raise ValueError('inventory_snapshots: Lead_Time_Days must be positive whole days')
    if name == 'calendar':
        for col in ['is_weekend', 'is_holiday']:
            if col in d:
                d[col] = pd.to_numeric(d[col], errors='coerce')
                if not d[col].isin([0,1]).all():
                    raise ValueError(f'calendar: {col} must be 0 or 1')
    if name == 'sales_daily' and not d.Promotion.isin([0, 1]).all():
        raise ValueError('sales_daily: Promotion must be 0 or 1')
    d = d.drop_duplicates()
    if d.duplicated(KEYS[name]).any():
        raise ValueError(f'{name}: conflicting duplicate keys {KEYS[name]}')
    audit[name] = dict(input_rows=before, output_rows=len(d), exact_duplicates_removed=before-len(d),
                       labels_normalized=changes, column_mapping=applied, missing_required=0,
                       policy='Trim labels; uppercase SKU/currency; remove exact duplicates; reject conflicting keys, missing required values and invalid types.')
    return d.sort_values(KEYS[name]).reset_index(drop=True)


def ingest(data_dir, allow_partial=False):
    root = Path(data_dir)
    absent = [n + '.csv' for n in SCHEMAS if not (root / (n + '.csv')).is_file()]
    if 'sales_daily.csv' in absent or (absent and not allow_partial):
        raise ValueError('Missing supplied extracts: ' + ', '.join(absent) + '. Use --allow-partial for explicitly partial-source work.')
    audit = {}
    tables = {n: clean_table(root / (n + '.csv'), n, audit) for n in SCHEMAS if n + '.csv' not in absent}
    s = tables['sales_daily']
    # Gaps are unknown observations, not zero sales. Permit different launch dates.
    for sku, g in s.groupby('SKU'):
        if len(g) != (g.Date.max() - g.Date.min()).days + 1:
            raise ValueError(f'sales_daily: missing dates inside history for {sku}; confirm missing vs zero sales')
        if g.Date.max() != s.Date.max():
            raise ValueError(f'sales_daily: stale final observation for {sku}')
    ready = s.copy()
    master = tables.get('sku_master')
    if master is not None:
        if not set(s.SKU) <= set(master.SKU):
            raise ValueError('sku_master: unknown sales SKU join keys')
        ready = ready.merge(master, on='SKU', how='left', validate='many_to_one', suffixes=('', '_master'))
    cal = tables.get('calendar')
    if cal is not None:
        if not set(s.Date) <= set(cal.Date):
            raise ValueError('calendar: missing sales dates')
        ready = ready.merge(cal, on='Date', how='left', validate='many_to_one', suffixes=('', '_calendar'))
    inv = tables.get('inventory_snapshots')
    if inv is not None:
        unmatched = inv[~inv.SKU.isin(master.SKU)] if master is not None else inv.iloc[0:0]
        audit['inventory_unmatched_skus'] = sorted(unmatched.SKU.unique().tolist())
        audit['inventory_unmatched_rows'] = len(unmatched)
        audit['latest_inventory_snapshot'] = str(inv.Date.max().date())
        audit['snapshot_age_at_sales_cutoff_days'] = int((s.Date.max()-inv.Date.max()).days)
        if master is not None and 'Inventory_Value' in inv:
            cost = inv.SKU.map(master.set_index('SKU').Cost_Price)
            values = pd.to_numeric(inv.Inventory_Value, errors='coerce')
            audit['inventory_value_cost_mismatch_rows'] = int((cost.notna() & ((values-inv.On_Hand*cost).abs() > .02)).sum())
        inv = inv[inv.SKU.isin(s.SKU)]
        # Backward as-of only: future snapshots never fill earlier sales dates.
        ready = pd.merge_asof(ready.sort_values('Date'), inv.rename(columns={'Date': 'Snapshot_Date'}).sort_values('Snapshot_Date'),
                              left_on='Date', right_on='Snapshot_Date', by='SKU', direction='backward', suffixes=('', '_inventory'))
    if master is not None:
        audit['negative_margin_skus'] = master.loc[master.Cost_Price > master.Selling_Price, 'SKU'].tolist()
        audit['sales_before_launch_rows'] = int((ready.Date < ready.Launch_Date).sum())
    audit['missing_extracts'] = absent
    audit['join_rows'] = len(ready)
    audit['snapshot_unmatched_rows'] = int(ready.Snapshot_Date.isna().sum()) if 'Snapshot_Date' in ready else None
    audit['revenue_price_mismatch_rows'] = int((abs(s.Revenue-s.Units_Sold*s.Price) > .02).sum())
    return tables, ready.sort_values(['SKU', 'Date']), audit
