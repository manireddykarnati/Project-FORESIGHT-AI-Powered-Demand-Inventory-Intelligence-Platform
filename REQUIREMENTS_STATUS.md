# FORESIGHT implementation checklist and evidence

Updated after receiving calendar and inventory snapshots on 30 September 2026. The implementation is checked against all 15 tasks in `FORESIGHT_Pending_Project_Requirements.pdf` and the supporting `Zidio_Project_Data_1.1 (1).pdf`. The original `REQUIREMENTS_REVIEW.md` is preserved as historical context. Deployment, publishing, video, forms and submission administration remain excluded.

All four supplied extracts now run successfully in strict mode. Coverage is **50 SKUs with sales and master records**. Inventory contains 200 SKUs; the remaining 150 have no supplied sales/master match and are retained separately rather than given fabricated inputs. Latest stock is **2025-12-01**, sales end **2025-12-31**: inventory decisions explicitly replay the stock date, while the final demand forecast uses the later cutoff.

Currency review: the brief asks for rupee impact but does not explicitly identify the CSV denomination as INR. `docs/CURRENCY_EVIDENCE.md` records exact sections and the source hash. Source-unit calculations are supported; confirmed INR reporting remains unresolved. No exchange rate or currency assumption is invented.

| # | Requirement | Status | Evidence and practical limits |
|---|---|---|---|
| 01 | Four-table ingestion | Complete for supported scope | `src/data.py`, `outputs/analysis_ready.csv`: all four extracts joined, 36,550 fact rows preserved. 3,600 unmatched inventory records retained in `inventory_unmatched.csv`; audit lists 150 excluded SKUs. |
| 02 | Cleaning and documented decisions | Complete | Verified provider aliases, strict required values/types, normalized keys, duplicate handling, gap checks, join validation and explicit no-event labels. `data_quality.json` and `docs/DATA_CONTRACT.md` record changes and semantic anomalies. |
| 03 | EDA and memo | Complete for supported scope | `reports/DATA_QUALITY_EDA_MEMO.md`, charts, top movers, holiday/event summaries and snapshot-aligned dead-stock screen. No dead-stock candidates among the 50 supported SKUs; no claim for the 150 without sales/master. |
| 04 | Weekly SKU forecasts | Complete | 400 forecast rows: 50 SKUs × 8 seven-day blocks, explicit dates, 56-day horizon. Matching weekly evaluation and independently reconciled totals. |
| 05 | Retrain at each origin | Complete | Three separate fits, recorded cutoffs and fold metrics. LightGBM weekly WAPE 9.726882% versus seasonal naive 13.802549%; model selection rationale documented. |
| 06 | Origin-valid inputs | Complete | Tests perturb future price/promotion/demand without changing earlier-origin predictions. Snapshot replay also excludes same-day and subsequent observations; its model is fixed and not selected using later validation outcomes. |
| 07 | Intervals and baseline curve | Complete | Approximate nominal central 95% normal error bands (±1.96), separate daily/weekly residual scales, assumptions stated. Actual/model/baseline curves shown. Calibration is not claimed. |
| 08 | Supplied inventory and costs | Complete historical quantities/valuations; INR unresolved | Supplied stock, on-order, lead time and master cost replace generated values. Demand is summed over lead/review windows. Stock is never rolled forward without movements. Currency evidence cannot support an explicit INR denomination. |
| 09 | Four-quadrant grid | Complete for 50-SKU snapshot review | Section 8.1 semantics: stockout uses position, overstock uses physical on-hand; receipt-timing warnings separate. 5 reorder, 5 clearance-review, 40 healthy, 0 watch. All four paths tested, including high-both fixture. |
| 10 | Consistent recommendations | Complete for historical review | Order quantities/spend/actions agree; clearance/watch/healthy have zero immediate purchase quantities. Supported quantities and financial exposures saved in `recommendations.csv`. Verify fresh stock before executing historical decisions. |
| 11 | Category filters and states | Complete | Master categories, coordinated filters, service-level what-if, historical-stock warning, unscored-SKU disclosure, empty/loading/error states and prioritised downloads. AppTest covers populated and empty/error paths. |
| 12 | Risk usefulness | Justified proxy checks complete; actual stockout precision unavailable | `risk_proxy_predictions.csv` and `risk_proxy_metrics.csv`: 150 lead-time sales-pressure cases and 100 complete 60-day excess cases. Lead proxy precision 81.25%; excess proxy precision 100%. These are demand-coverage proxies, not observed lost sales or intra-month stockout precision. Missing movements/receipts/unmet demand prevent stronger claims. |
| 13 | Local scoring | Complete for supported SKUs | Dashboard/Python return forecast plus snapshot risk, with separate dates and nullable currency. Bad SKU, malformed inputs and absent data are handled gracefully. Contract in `docs/LOCAL_SCORING.md`. |
| 14 | Reproducible full run and notebooks | Complete | Strict `python run_pipeline.py` succeeds on supplied four-table data in the isolated pinned environment. 22 tests pass; both notebooks execute cleanly. `scripts/verify_outputs.py` independently reconciles metrics, source hashes, stock calculations and proxy counts. |
| 15 | Executive readout | Delivered; confirmed-INR condition unresolved | `reports/EXECUTIVE_READOUT.md` leads with historical source-unit exposures and actions, then verified forecast scores, outcome proxies and limitations. Does not claim current inventory, achieved savings, actual stockout precision or confirmed rupees. |

## Evidence that remains unavailable

- CSV denomination/currency confirmation: the brief specifies the requested reporting unit, not an explicit INR label for supplied amounts.
- Stock at the later sales cutoff or today: monthly snapshots stop at 1 December 2025. The completed system supports a clearly dated historical review; it does not fabricate a stock roll-forward.
- Sales/master for SKU051–SKU200: these products remain outside the supported scoring scope.
- Actual stockout/lost-sales outcomes and receipts: only proxy validation is possible from supplied extracts.
- Historical cost valuation: 1,176 matched inventory values differ from on-hand × current master cost. Original values are preserved, and exposures use explicitly stated master-cost valuation.

No additional implementation is blocked by these facts; the limitations are surfaced in the outputs and dashboard. Full confirmed-INR/current-stock/all-200-SKU claims require additional source evidence.

## Related safeguards and optional goals

Sparse/new SKU fallback and low-confidence flags are implemented and tested. All-promotion versus no-promotion model sensitivity is separate from confirmed plans. Secondary MAPE excludes zero-demand observations. Feature importance and service-level what-if remain available. Unsupported EOQ assumptions are removed.

Empirically calibrated intervals and monitoring are optional stretch goals. No separate FastAPI service is needed for the verified local scoring interface.
