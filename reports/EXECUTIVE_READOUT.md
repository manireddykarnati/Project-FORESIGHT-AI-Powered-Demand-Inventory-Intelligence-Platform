# FORESIGHT executive readout

## Financial decision

Historical snapshot review at 2025-12-01: proposed order spend 4,228,463.18; excess stock at supplied cost 4,415,534.15; lead-time revenue exposure net of on-order 2,360,139.87. All amounts are source currency units (not confirmed INR). On-hand-only revenue exposure if receipts are delayed: 3,887,946.81; this overlaps the net exposure and must not be added to it. The brief asks for rupee impact (pages 5, 11-13), but does not explicitly state the CSV currency or an INR conversion. No currency conversion or INR assumption has been applied. These quantities are scenario exposures, not achieved savings, expected losses, or additive benefits. Revenue at risk is not profit. Clearance proceeds require an approved discount and sell-through estimate; none is assumed.

## Historical snapshot actions — verify fresh stock before execution

| SKU | Priority | Order units | Clearance review units | Action |
|---|---|---:|---:|---|
| SKU012 | Critical | 361 | 0 | Order 361 units now; verify receipt timing; verify / expedite on-order receipt timing |
| SKU031 | Critical | 223 | 0 | Order 223 units now; verify receipt timing; verify / expedite on-order receipt timing |
| SKU017 | Critical | 139 | 0 | Order 139 units now; verify receipt timing; verify / expedite on-order receipt timing |
| SKU040 | Critical | 142 | 0 | Order 142 units now; verify receipt timing; verify / expedite on-order receipt timing |
| SKU010 | Critical | 181 | 0 | Order 181 units now; verify receipt timing; verify / expedite on-order receipt timing |
| SKU025 | Medium | 0 | 962 | Review 962 units for markdown / clearance; pause ordering |
| SKU020 | Medium | 0 | 231 | Review 231 units for markdown / clearance; pause ordering |
| SKU011 | Medium | 0 | 594 | Review 594 units for markdown / clearance; pause ordering |
| SKU036 | Medium | 0 | 99 | Review 99 units for markdown / clearance; pause ordering |
| SKU003 | Medium | 0 | 37 | Review 37 units for markdown / clearance; pause ordering |

Full prioritised quantities, cost exposure and actions: outputs/recommendations.csv. 50 in-scope SKUs are scored; 150 inventory-only SKUs have no supplied sales/master match and are not assigned fabricated demand or cost. No purchase order or clearance execution is authorized or performed.

Operations can already prioritise demand reviews for SKU012, SKU027, SKU018, SKU049, SKU007 based on recent unit volume. Finance should review 16 SKUs with master cost above selling price. Resolve 3393 sales rows dated before recorded product launch before relying on launch-based lifecycle analysis.

## Forecast evidence

Three sequential, non-overlapping 56-day folds retrain at every origin, each using only preceding observations. Weekly scores aggregate matching seven-day blocks anchored to each origin. LightGBM weekly WAPE is 9.727%, versus 13.803% for seasonal naive; weekly bias is -0.661%. The lowest observed weekly WAPE belongs to LightGBM (9.727%). Selected forecast: LightGBM. This selection uses the backtest and is not an independent final holdout estimate. WAPE measures aggregate absolute error relative to units sold, not a probability of correctness. Daily scores and fold-level results are in outputs/model_metrics.csv and outputs/fold_metrics.csv.

## Practical use

Use the eight-week forecast for planning from 2026-01-01 through 2026-02-25. These dates follow the historical extract cutoff; they are not current real-time predictions. The dashboard shows category/SKU filters, actual and baseline curves, local saved-forecast scoring, and risk only where supported. A supplemental 60-day (or longer lead-time) demand forecast feeds the inventory rule, without extending the eight-week reported evaluation horizon.

## Limitations and decisions outstanding

Missing extracts: None. Historical stock review date: 2025-12-01.

- lead_time_sales_exceed_position: n=150, TP=13, FP=3, FN=0, TN=134; proxy precision=0.8125, recall=1.0
- on_hand_exceeds_next_60d_sales: n=100, TP=14, FP=0, FN=0, TN=86; proxy precision=1.0, recall=1.0

The checks above measure demand-coverage proxies, not actual stockout precision or achieved business benefit. Monthly snapshots, missing receipts and unobserved unmet demand prevent that stronger validation. On-order offsets inventory-position risk and new purchases per brief section 8.1. Immediate on-hand shortfalls remain a separate receipt-timing warning; receipt dates are unknown. Overstock uses physical on-hand above 60-day forecast demand, with incoming excess recorded separately. The high-both quadrant requires investigation before buying or clearing. Inventory safety stock assumes independent daily errors and stable lead times; its error scale is prior seasonal-naive residual variation known before the snapshot. Inventory replay uses fixed LightGBM rather than selecting a model using future outcomes. The displayed bands are approximate nominal 95% central normal error bands, estimated from previous backtest residuals for final forecasts only, without empirical calibration. Weekly variance includes within-week error correlation by estimating errors on weekly sums. Sparse/new SKU fallbacks carry a low-confidence flag and may lack a band if no validation history exists.

Future promotion plans are unavailable. Base forecasts assume no promotions, with last known price at each origin. An all-promotion sensitivity scenario illustrates model response; it is not a business plan or causal impact estimate. The supplied calendar is joined and profiled; its retrospective promotion-event labels are not assumed to be advance-known plans. No deployment, publishing, demo or submission work is included. Calibrated intervals and monitoring are optional stretch goals.
