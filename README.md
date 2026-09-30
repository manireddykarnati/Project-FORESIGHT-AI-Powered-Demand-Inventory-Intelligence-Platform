# Project FORESIGHT

FORESIGHT produces weekly SKU demand forecasts, compares them with simple baselines, and provides inventory decisions when supplied stock data supports them. The pipeline runs locally; the Streamlit dashboard can also serve its saved outputs on Render.

## Current source coverage

All four supplied extracts are now ingested: 36,550 sales rows (50 SKUs, 2024-01-01 to 2025-12-31), 50 SKU-master rows, 731 calendar days, and 4,800 monthly inventory rows covering 200 SKUs. Inventory-only SKU051–SKU200 lack matching sales/master data; their 3,600 rows are retained separately and are not assigned invented forecasts or costs. All 50 supported SKUs receive risk decisions.

**Currency is not explicitly confirmed by the document.** The brief requests impact in rupees, but neither its data dictionary nor the CSVs specifies INR denomination or conversion. See [currency evidence](docs/CURRENCY_EVIDENCE.md). Financial results retain source currency units, with no ₹ label.

The newest stock snapshot is **2025-12-01**, 30 days before the sales cutoff. Inventory decisions are a historical snapshot replay, with models trained strictly before that date; no stale stock is presented as current. Demand forecasts retain the later 2025-12-31 cutoff. The stock review yields **5 reorder, 5 markdown/clearance-review, 40 healthy, and 0 watch** outcomes. At supplied master costs/prices, proposed spend is **4,228,463.18**, excess stock value **4,415,534.15**, and lead-time revenue exposure net of on-order **2,360,139.87**, all in unconfirmed source currency units. These are scenario values, not achieved benefits or current purchase instructions.

The audit flags 16 master records with cost above selling price, 3,393 sales rows before recorded launch, and 1,176 of 1,200 matched inventory values that do not reconcile to on-hand × current master cost. Provider inventory values are retained but not used as cost valuations. Historical unit-cost changes cannot be checked because the master is undated. See [data contract](docs/DATA_CONTRACT.md).

## Reproducible setup

Tested with Python 3.12.4 on macOS using a fresh virtual environment. The core dependencies are pinned in `requirements.txt`; `requirements-lock.txt` records every installed version from validation. On macOS, LightGBM may require OpenMP (`brew install libomp`); the Python and Homebrew architecture must match. If import reports `libomp.dylib` missing, resolve that native dependency before running. The clean validation environment imported LightGBM successfully without adding a system library during this task.

```bash
cd /Users/manignanendrareddy/Downloads/project-foresight
python3.12 -m venv .venv-foresight
source .venv-foresight/bin/activate
python -m pip install -r requirements-lock.txt
python run_pipeline.py
python -m pytest -q tests
python scripts/execute_notebooks.py
python scripts/verify_outputs.py
streamlit run app/streamlit_app.py
```

On Windows, activate with `.venv-foresight\Scripts\activate`. The scripts resolve project paths independently of the shell working directory, except tests should be run from the project root. Notebook execution requires permission for local Jupyter kernel sockets. Dependencies are installed in the environment, never by notebook shell commands.

The default command requires all four files and succeeds on the supplied extracts. `--allow-partial` remains available for explicit incomplete-data diagnostics; malformed present files still fail. Do not pass `--currency INR` until denomination is established. Alternative directories are supported through `--data-dir`, `--output-dir`, and `--report-dir`. Synthetic tests write only to temporary directories.

## Host the dashboard on Render

Use the included `render.yaml` Blueprint or follow the [Render deployment guide](docs/RENDER_DEPLOYMENT.md). It selects a **Free** Python web service and installs the smaller `requirements-web.txt` runtime. The service reads committed outputs without retraining at startup. Source dates and historical inventory limitations remain visible in the hosted dashboard.

## Method and verified results

The model remains global LightGBM with shifted demand features, SKU codes, date features, last-known price and promotion scenario flags. Each of three non-overlapping **56-day** backtest folds retrains using only dates before that origin. Future price changes and actual promotions cannot enter earlier-origin features. Base forecasts assume no future promotions. Seasonal naive repeats the last observed seven days; moving average repeats the prior 28-day mean.

Weekly output uses eight consecutive seven-day blocks anchored at the forecast origin, with explicit start/end dates, rather than partial calendar weeks. Final dates are **2026-01-01 to 2026-02-25**, following the historical extract cutoff, not today's date. All models are evaluated on identical folds and horizons.

| Model | Daily WAPE | Weekly WAPE | Bias |
|---|---:|---:|---:|
| LightGBM | 23.087% | 9.727% | -0.661% |
| Seasonal naive | 32.264% | 13.803% | +5.300% |
| Moving average (28 days) | 26.165% | 13.464% | +4.818% |

LightGBM is selected by weekly WAPE. Selection and measurement use the same backtest, so this is not an untouched holdout estimate. Weekly aggregation reduces day-level noise; weekly and daily WAPE answer different questions. MAE, RMSE and secondary MAPE are also saved. MAPE excludes zero-demand observations; WAPE/bias are undefined when total actual demand is zero. `100 - WAPE` is not labelled as accuracy.

Final uncertainty bands are **approximate nominal 95% central normal error bands**, using ±1.96 residual standard deviations. Daily and weekly residual scales are estimated separately; weekly errors are computed from weekly sums, avoiding an assumption of independent daily errors within each week. Bands are uncalibrated, clipped at zero, and absent when error history is unavailable. Backtest rows do not carry bands fitted to those same residuals. Sparse/new SKUs use a category-peer mean or their own recent mean with a low-confidence flag; no-history/no-peer forecasts fail gracefully. Current master metadata is not used as a historical forecasting feature. An all-promotion sensitivity scenario is saved separately and is not treated as an actual plan or causal uplift estimate.

## Inventory and actions

Supplied on-hand, on-order, lead time and master cost drive the historical snapshot review. The snapshot is treated as start-of-day: training/error estimation excludes that day's sales, and the risk forecast begins on the snapshot date. This explicit convention avoids using same-day or later outcomes in the decision. No receipts/movements are invented to update stale stock.

- Safety stock = one-sided service-level Z × prior 56-day seasonal-naive daily residual standard deviation × square root of lead time. The historical error benchmark is available before the decision, without using future final-model backtest errors.
- Reorder point = forecast lead-time demand + safety stock, rounded up. Lead-time and review demand are exact sums of the snapshot-origin forecast.
- Inventory position = on-hand + on-order; **stockout risk** compares it with the reorder point, following brief section 8.1.
- **Overstock** compares physical on-hand with forecast demand over 60 days. Potential incoming excess is recorded separately.
- Reorder now: high stockout risk only; order to the lead-time-plus-seven-day target net of on-order.
- Markdown / clear: high excess only; pause ordering and review excess units for clearance.
- Watch / volatile: both high; investigate before ordering/clearing. No automatic purchase or clearance quantity is issued.
- Healthy: both low; no new order. Any on-hand shortfall still triggers a separate receipt-timing warning.

Order spend = proposed units × supplied cost; excess value = physical excess × supplied cost; net revenue exposure = lead-time demand above inventory position × supplied selling price. On-hand-only exposure if receipts are delayed is reported separately and overlaps net exposure. These are not additive savings, and neither cost-history nor clearance proceeds is established. EOQ remains excluded because ordering/holding costs are absent.

Risk validation replays the latest three monthly snapshot dates, each with a fresh origin-valid fit. Lead-time sales-pressure proxy: 150 cases, 13 true positives, 3 false positives, 0 false negatives and 134 true negatives (proxy precision 81.25%). Sixty-day excess proxy: 100 complete cases, 14 true positives and 86 true negatives. These compare flags with later observed sales coverage; **they are not actual stockout/lost-sales precision**, because receipts, intra-month stock movements and unmet demand are not observed. No claim is made that monthly positive stock means zero intervening stockouts.

## Deliverables and local scoring

- [Requirement-by-requirement status](REQUIREMENTS_STATUS.md), including blocked acceptance conditions.
- [Data-quality / EDA memo](reports/DATA_QUALITY_EDA_MEMO.md), [labelled interactive charts](reports/eda_charts.html), [top movers](reports/top_movers.csv).
- [Executive readout](reports/EXECUTIVE_READOUT.md).
- [Local scoring contract and examples](docs/LOCAL_SCORING.md).
- [Verification evidence](reports/VALIDATION.md).
- Both notebooks import the maintained pipeline and contain clean executed outputs.

`outputs/` includes analysis-ready rows, data-quality audit, daily/weekly forecasts, daily/weekly backtest predictions, global/fold metrics, feature importance, promotion sensitivity, SKU inputs, historical recommendations, snapshot forecasts, unmatched inventory rows, proxy validation details, and run metadata with source hashes and training cutoffs. Forecasts, reports, notebooks and the dashboard use the same computation. The dashboard keeps category/ABC/SKU/risk filters, service-level what-if, baseline curves, four-quadrant grid, prioritised downloads and explicit loading/empty/error states. Missing risk is displayed as unavailable.

Optional stretch work: empirical interval calibration and a monitoring plan. A separate FastAPI server is unnecessary for this local scoring contract.
