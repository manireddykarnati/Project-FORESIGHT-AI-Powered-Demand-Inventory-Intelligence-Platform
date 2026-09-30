# Data-quality and EDA memo

As of 2025-12-31; 36,550 sales rows, 50 observed SKUs. Supplied extracts missing: None.
Currency: unconfirmed; revenue and costs retain source units.

## Treatment and quality findings

- sales_daily: {'input_rows': 36550, 'output_rows': 36550, 'exact_duplicates_removed': 0, 'labels_normalized': 0, 'column_mapping': {}, 'missing_required': 0, 'policy': 'Trim labels; uppercase SKU/currency; remove exact duplicates; reject conflicting keys, missing required values and invalid types.'}
- sku_master: {'input_rows': 50, 'output_rows': 50, 'exact_duplicates_removed': 0, 'labels_normalized': 0, 'column_mapping': {}, 'missing_required': 0, 'policy': 'Trim labels; uppercase SKU/currency; remove exact duplicates; reject conflicting keys, missing required values and invalid types.'}
- calendar: {'input_rows': 731, 'output_rows': 731, 'exact_duplicates_removed': 0, 'labels_normalized': 0, 'column_mapping': {'date': 'Date'}, 'missing_required': 0, 'policy': 'Trim labels; uppercase SKU/currency; remove exact duplicates; reject conflicting keys, missing required values and invalid types.'}
- inventory_snapshots: {'input_rows': 4800, 'output_rows': 4800, 'exact_duplicates_removed': 0, 'labels_normalized': 0, 'column_mapping': {'Snapshot_Date': 'Date', 'Current_Stock': 'On_Hand'}, 'missing_required': 0, 'policy': 'Trim labels; uppercase SKU/currency; remove exact duplicates; reject conflicting keys, missing required values and invalid types.'}
- inventory_unmatched_skus: 150 SKUs; full IDs in outputs/data_quality.json
- inventory_unmatched_rows: 3600
- latest_inventory_snapshot: 2025-12-01
- snapshot_age_at_sales_cutoff_days: 30
- inventory_value_cost_mismatch_rows: 1176
- negative_margin_skus: ['SKU002', 'SKU007', 'SKU009', 'SKU010', 'SKU011', 'SKU016', 'SKU018', 'SKU020', 'SKU023', 'SKU024', 'SKU028', 'SKU033', 'SKU037', 'SKU038', 'SKU040', 'SKU048']
- sales_before_launch_rows: 3393
- missing_extracts: []
- join_rows: 36550
- snapshot_unmatched_rows: 0
- revenue_price_mismatch_rows: 0

Missing required values and invalid types fail validation rather than being guessed. Exact duplicates are removed after label normalization; conflicting business keys fail. SKU/date joins are validated. Inventory joins use backward snapshots, never future snapshots. Internal sales-date gaps are rejected rather than imputed as zero. Launch-date anomalies and negative margins are retained and disclosed for source-owner review; deleting these observations would silently alter history. A current, undated master is not used as a historical forecasting feature. Calendar descriptive fields are joined when supplied, but are not assumed known in advance for backtesting.

## Business insights and actions

1. Recent 28-day sales total 17,338 units versus 17,298 in the preceding 28 days (+0.2%). Review procurement targets weekly as the trend changes; do not extrapolate a two-period change as annual growth.
2. Weekend SKU-day demand is +24.9% relative to weekdays. Schedule warehouse picking capacity and replenishment reviews ahead of weekends.
3. Promotion days show +38.1% average observed demand relative to non-promotion days. This is an association, not causal promotion lift; use an explicit promotion scenario and check margin before budgeting a campaign.
4. The highest recent-volume SKU is SKU012 with 646 units in 28 days. Prioritise availability checks for the top movers in top_movers.csv. Category and launch-date mix can confound comparisons.
5. Seasonal monthly means peak in month 3 and are lowest in month 10. Use this to time planning reviews; only two years of history support these patterns.

## Calendar context

Holiday and named-event means are saved in holiday_summary.csv and promotion_event_summary.csv with sample counts. None is a literal no-event label, not an imputed missing value. These descriptive comparisons are not causal effects and are not used as future-known plans.

## Slow movers and dead stock

0 observed SKUs have zero sales in the 28 days strictly before the stock review date 2025-12-01. Zero sales alone do not establish dead stock. Snapshot-aligned dead-stock candidates: 0. Master-only new products are marked low-confidence and use category peers where available. No missing-day sales are fabricated. Dead stock means positive snapshot stock with zero observed sales in the preceding 28 days; it does not imply a confirmed clearance recovery. The 150 inventory-only SKUs, when present, are outside the sales/master scope and remain unscored, with raw records retained in outputs/inventory_unmatched.csv.

## Snapshot coverage and outcome checks

Stock review date: 2025-12-01. This is a historical review, not current inventory at the later sales cutoff. Safety-stock scale uses prior 56-day seasonal-naive daily errors available before the snapshot. Provider Inventory_Value is retained but not used when it fails reconciliation with supplied master cost. See the audit counts above.

- lead_time_sales_exceed_position: n=150, TP=13, FP=3, FN=0, TN=134; proxy precision=0.8125, recall=1.0
- on_hand_exceeds_next_60d_sales: n=100, TP=14, FP=0, FN=0, TN=86; proxy precision=1.0, recall=1.0

These are demand-coverage proxies from subsequent observed sales, not actual lost-sales/stockout precision. Monthly positive snapshots do not prove that stockouts never occurred between snapshots. Unknown receipts, transfers and censored sales limit interpretation. No positive proxy cases means recall is undefined, not perfect.

See [labelled charts](eda_charts.html), [top movers](top_movers.csv), and ../outputs/data_quality.json for the machine-readable audit.
