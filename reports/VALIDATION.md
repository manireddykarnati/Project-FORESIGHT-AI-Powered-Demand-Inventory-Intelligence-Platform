# Validation evidence

Validation date: 30 September 2026. Synthetic fixtures are generated only under pytest temporary directories. They do not enter source data or reported business results.

## Environment and execution

- A fresh environment was created at `/private/tmp/foresight-clean-env` with Python 3.12.4; `pip install -r requirements.txt` completed. Full installed versions are recorded in `requirements-lock.txt`.
- Network access was needed only to install packages. No source data was sent externally.
- `python run_pipeline.py --allow-partial` succeeded with supplied sales and SKU master, producing the eight-week forecasts and reports. Calendar and inventory snapshots remained explicitly missing.
- A first run in the existing environment and the fresh-environment run agreed on the reported model scores to the displayed precision.
- `python run_pipeline.py` without the explicit partial flag exits nonzero and identifies missing calendar and inventory files. This is expected validation, not a successful full-data run.
- `python scripts/execute_notebooks.py` completed. Both notebooks contain executed cells with no error outputs and no pip-install cells. Local kernel sockets required execution outside the restricted socket sandbox; no remote service was used.

## Tests

`python -m pytest -q tests`: **20 passed in 6.61 seconds** in the final rerun after integration.

Coverage includes:

- Four-table joins, row counts, backward snapshot matching, normalized labels and exact duplicates.
- Invalid/missing values, negative/infinite numbers, conflicting keys, unknown join keys and missing sales days.
- Shifted target features, retraining at distinct origins and future-only price/promotion/demand perturbation.
- Weekly totals, eight complete horizon blocks and forecast-band ordering.
- All four inventory quadrants, on-order coverage, exact lead-time/review demand sums, stale snapshots, consistent actions/spend, zero demand and financial formulas.
- An end-to-end four-table pipeline with isolated synthetic fixtures, including independently recomputed metrics and local forecast+risk scoring.
- Dashboard defaults, real category selection, empty category and ABC filters, unknown SKU error, missing/malformed outputs and populated four-quadrant fixture.

Streamlit smoke tests use its `AppTest` runner. They establish rendering and interaction behavior; no stakeholder usability study or public deployment test is claimed.

Independent reconciliation: `python scripts/verify_outputs.py` verifies all six daily/weekly WAPE values directly from predictions, weekly totals, interval ordering, source hashes, fold cutoffs and both executed notebooks.

## Metrics and practical limits

Three 56-day folds begin 2025-07-17, 2025-09-11 and 2025-11-06; every training cutoff precedes its origin. There are 8,400 SKU-day evaluation rows and 1,200 SKU-week rows. Weekly LightGBM WAPE is 9.726882%, seasonal naive 13.802549%, moving average 13.464041%. LightGBM daily WAPE is 23.086507%, with -0.661190% bias. Full precision is in `outputs/model_metrics.csv`. Final forecasts have 2,800 daily rows and 400 weekly rows.

No source-backed full four-table run, real inventory outcome precision, real clearance proceeds, achieved savings or INR exposure can be verified from the current supplied data. Inventory logic has only fixture evidence until snapshots arrive. Interval coverage is not empirically calibrated. Reported forecasts follow the 2025-12-31 cutoff, rather than current-date demand.
