# FORESIGHT requirements review

Reviewed 2026-09-30 against `Zidio_Project_Data_1.1 (1).pdf`, especially Sections 09 and 13. This is an assessment of the local repository. Document instructions were treated as project criteria, not as authorization to deploy, publish, contact anyone, or modify implementation.

**Verdict: not all requirements are complete.** The repository contains a substantial forecasting/dashboard prototype, but none of D1-D7 currently satisfies every acceptance criterion. “Missing” below means missing from the reviewed repository; external submissions and deployments may exist elsewhere.

## Acceptance criteria

| Criterion | Status | Evidence / outstanding work |
|---|---|---|
| D1.1 Ingest four extracts and produce an analysis-ready dataset | Partial | `src/features.py:11` reads only `data/sales_daily.csv`. No `sku_master`, `calendar`, or `inventory_snapshots`, joins, or unified cleaned-data output. |
| D1.2 Code missing-value, duplicate, and type cleaning | Partial | Dates are parsed and records sorted. No raw-data deduplication, missing-value policy, label normalization, or schema validation. Dropping unavailable lag rows is feature preparation, not raw-data cleaning. |
| D1.3 One-command end-to-end rerun | Partial | `python run_pipeline.py` exists for the current one-table implementation; does not cover the required four-table pipeline. Runtime result recorded below. |
| D1.4 Document cleaning decisions and rationale | Missing | README documents modelling and simulated-stock assumptions, but no cleaning policy/report. |
| D2.1 Report data issues and treatment | Partial | Notebook prints missing/duplicate counts for sales only. No full data-quality memo or treatment log. Current CSV has 36,550 rows, 50 SKUs, no blank cells, and no duplicate SKU/date keys. |
| D2.2 Seasonality, trend, top movers, dead stock | Partial | Daily trend, weekday/month patterns and promotion lift are present. No explicit top-mover/dead-stock analysis. |
| D2.3 At least three plain-language business insights | Partial | README reports weekend lift, seasonal pattern, and promotion lift. These need consolidation into the required memo with operational implications. |
| D2.4 Labelled, non-technical charts | Implemented in code | Notebook/dashboard charts have titles and axes. Formal stakeholder usability is not established. |
| D3.1 Weekly SKU forecast over defined horizon | Partial | Current output is daily forecasts for 30 days, not weekly SKU forecasts. The brief's 6-8 weeks is an example, not a mandatory fixed horizon. |
| D3.2 Seasonal-naive baseline | Implemented | `src/forecast.py:52` repeats the last observed week. Moving-average baseline also exists. |
| D3.3 Rolling-origin CV and WAPE comparison | Partial | Three moving forecast origins and WAPE exist, but the model is trained once before all windows and never retrained per origin (`run_pipeline.py:22`, `src/forecast.py:47`). Appendix B defines CV as repeatedly training on past data. Saved WAPE: LightGBM 22.566%, seasonal-naive 32.625%, moving average 25.011%. |
| D3.4 No future information in features | Partial / conditional | Lags and rolling features correctly use earlier demand. Backtest prices come from the last row of the complete dataset (`run_pipeline.py:16`): this would leak if prices changed. Current prices are constant within every SKU, so no observed price-leakage effect on this CSV. Backtest promotions assume advance knowledge; this assumption is documented. |
| D4.1 Stockout/overstock risk per SKU | Partial | Every current SKU has a flag, but stock, lead time and unit cost are generated rather than read from provided extracts. On-order units are ignored; lead-time demand uses average forecast demand rather than summing that lead-time window. |
| D4.2 Action and rupee value at stake | Partial | Order/pause actions and financial exposure calculations exist. Costs are assumed, and currency is explicitly unspecified in README instead of verified/labeled INR. Overstock lacks the requested markdown/clear action. |
| D4.3 Transparent logic | Implemented | Formulas, thresholds, and assumptions are readable in `src/inventory.py` and README. |
| D4.4 Reconcile with four-quadrant decision grid | Missing | No stockout-versus-overstock scatter/grid. Mutually exclusive flags cannot represent the required high-both “Watch / volatile” quadrant. |
| D5.1 Category/SKU filters, forecast/actual, risks | Partial | SKU selection, ABC-class and risk filters, forecast/actual plots and flags exist. ABC class is not product category; category filtering is missing. SKU selection controls detail view, not the full action list. |
| D5.2 Prioritised reorder/markdown list | Partial | Priority-sorted reorder table and CSV download exist. Markdown/clear recommendations are absent. |
| D5.3 Loads seeded data, usable by operations | Partial | Seeded CSVs and dashboard implementation exist. Runtime result recorded below; user usability not verified. |
| D5.4 Clear empty/loading states | Partial | Recalculation spinner exists. No explicit “no matching SKUs” state or graceful missing/invalid-file handling. |
| D6.1 Hosted at a public URL | Unverified / no link | README dashboard link is a placeholder; no live scoring URL is supplied. |
| D6.2 Returns forecast+risk for SKU/batch | Partial | Local dashboard shows saved forecast and recalculated risk for a selected SKU. No separate service exists. The brief permits dashboard-exposed scoring, so FastAPI is not mandatory if this is properly deployed and documented. |
| D6.3 Document service inputs/outputs | Missing | No scoring interface contract or request/result examples. |
| D6.4 Graceful bad-input handling | Partial | Dropdowns constrain ordinary selections, but data validation/error handling is absent; no deployed interface available to test. |
| D7.1 6-10 slides or executive memo | Missing | No executive deck/memo found; README slides link is a placeholder. |
| D7.2 Lead with rupee impact/actions | Missing | No executive readout; existing calculations depend on simulated inventory/costs. |
| D7.3 Explain accuracy/limitations honestly | Partial supporting material | README provides metrics and assumptions, but these have not been delivered in the required readout. |
| D7.4 Non-technical language | Unassessable | Executive readout absent. |

## Submission checklist (Section 13)

| Submission | Status |
|---|---|
| Git repository with pipeline, notebooks, model code | Present locally with a GitHub origin; remote visibility and mentor access not verified. |
| Live dashboard and scoring-service URLs | Not supplied; README live-dashboard field remains a placeholder. A dashboard can expose scoring if it meets D6. |
| README: problem, data, setup, WAPE vs baseline, assumptions | Present. Needs updates when the missing scope is implemented. |
| Executive PDF/slides and data-quality/EDA memo | Missing. |
| Unlisted 3-5 minute demo video | No video/link found; README demo field is a placeholder. |
| Completed cohort form with all links | Cannot verify from repository. |

## Other specification gaps and correctness issues

- **Forecast interval label is incorrect.** `run_pipeline.py:53` uses 1.6449 on both sides while the dashboard labels the result “95% interval.” Under a normal-error assumption that is approximately a 90% central interval; 95% central coverage would use about 1.96. This does not invalidate 1.6449 for a one-sided 95% inventory service level. Empirical interval calibration is not provided and is an optional stretch goal.
- **Baseline plot missing.** Section 7.2 calls for actual, baseline and model curves together. Only actual and model predictions are plotted; baseline metrics appear separately.
- **Risk precision is unvalidated.** No comparison of flags with historical inventory outcomes or measured precision, despite the success-metric target.
- **Sparse/new-SKU handling missing.** Section 16 describes category fallback and low-confidence flags; neither exists. Forecasting assumes adequate history.
- **Promotion scenarios missing.** Historical promo lift is shown, and future predictions assume no promotions, but forecasts with/without promotional effects are not compared as described in Section 16.
- **Secondary MAPE not reported.** Appendix B describes it as a secondary metric. MAE, RMSE, WAPE and bias are present; add MAPE with a zero-demand policy if following the appendix literally. D3 explicitly requires WAPE, which is present.
- **Data governance needs checking.** `data/sales_daily.csv` is Git-tracked and README suggests a public repository, while Section 16 calls the provided data confidential. Remote visibility was not checked, so public disclosure is not established.
- **Notebook cleanup needed.** The executed notebook retains an `externally-managed-environment` pip installation failure, although subsequent cells contain results. Record a clean execution in the supported environment.
- **Order guidance is inconsistent.** Saved recommendations for SKU001, SKU026, and SKU027 have positive recommended order quantities (96, 130, and 135) but say “No action.” The dashboard also displays a positive suggested order value beside “No action.” Distinguish optional replenishment-to-target from orders required now, or make these fields agree.
- **Checkpoint/process evidence unavailable.** Daily updates, mandatory weekly mentor checkpoints, submission deadline compliance, attendance, test results, and ability to defend the work cannot be verified from local code.

## Optional items (not blockers)

Feature importance and an interactive service-level what-if control are already implemented. Calibrated prediction intervals and a model-monitoring plan remain absent. Prophet/SARIMA, SHAP, hyperparameter search, a separate FastAPI application, and live ERP integration are not mandatory; live integration is explicitly out of scope. The contextual “~200 SKUs” is not an instruction to fabricate additional products.

## Recommended completion order

1. Obtain the missing supplied extracts and implement cleaning, joins, validation, and a documented analysis-ready output.
2. Add weekly outputs; retrain per backtest origin; use origin-valid inputs; correct interval labeling and include a baseline curve.
3. Use actual snapshot/on-order data; implement the four risk quadrants, clearance actions, and supported INR impact.
4. Finish category filtering, empty/error states, and scoring-interface documentation/validation.
5. Produce the data-quality/EDA memo and executive readout; deploy and test public URLs; add the demo link and complete the cohort form.

Implementation files were not changed during this review.

## Runtime verification

Tests used an isolated temporary copy and a new Python 3.13 virtual environment, leaving original outputs intact.

- `pip install -r requirements.txt`: completed successfully.
- `python run_pipeline.py`: failed importing LightGBM because `libomp.dylib` is missing on this Mac. README does not document the native OpenMP dependency. Consequently the saved headline model scores were inspected but not independently reproduced in this review. This is an environment/setup failure, not evidence that training logic itself fails once dependencies are supplied.
- Streamlit `AppTest`: default dashboard completed without exceptions; five tabs and two dataframes were present.
- Streamlit `AppTest`, ABC selection cleared: completed without exceptions, but no explicit empty-results message was displayed. SKU detail continued showing its independent selection.
- Raw-sales checks confirmed 36,550 rows, 50 SKUs, no blank cells or duplicate SKU/date pairs, and constant price per SKU.
- No public deployment URL was supplied, so live hosting, scoring reachability, mentor access, and form submission were not verified.
