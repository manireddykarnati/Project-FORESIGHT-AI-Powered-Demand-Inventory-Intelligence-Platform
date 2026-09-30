# Supplied data contract

Place source CSVs in `data/`. All four supplied CSVs are retained unchanged as source extracts. Never substitute synthetic business data. Dates use `YYYY-MM-DD`; SKU keys are trimmed and uppercased. Exact duplicate rows are removed after normalization. Conflicting keys, invalid/missing required values, non-finite/negative numeric quantities and internal gaps in sales history fail validation. Missing observations are not automatically interpreted as zero sales.

| Extract | Required fields | Unique key |
|---|---|---|
| sales_daily.csv | Date, SKU, Units_Sold, Revenue, Price, Promotion | SKU, Date |
| sku_master.csv | SKU, Category, Cost_Price, Selling_Price, Launch_Date | SKU |
| calendar.csv | Date; additional supplied calendar labels are retained | Date |
| inventory_snapshots.csv | Date, SKU, On_Hand, On_Order, Lead_Time_Days | SKU, Date |

The SKU-master schema matches the supplied file. Verified provider mappings: calendar `date` → `Date`; inventory `Snapshot_Date` → `Date` and `Current_Stock` → `On_Hand`. Both aliases and canonical names together are rejected as ambiguous. Literal `None` in calendar holiday/event fields is retained as a no-event label, not parsed as missing. Lead times must be positive whole days. Promotion flags must be 0 or 1. Cost/price may be zero; costs above selling price are flagged, not silently changed. Categories are whitespace-trimmed but not case-merged because category equivalence is not established. A source Currency column, if supplied, is retained; the CLI currency declaration must be supported by source-owner confirmation. Do not pass `--currency INR` based solely on the project brief.

Sales rows must have a SKU-master match and calendar date when those extracts are present. No sales rows are dropped in dimension joins. Analysis-ready inventory fields are backward-as-of joins by SKU; rows preceding the first snapshot remain null and are counted. Inventory-only SKUs are quarantined from scoring and retained in `outputs/inventory_unmatched.csv`; counts and IDs are audited. Missing sales-to-master keys still fail. The latest supported snapshot defines the historical inventory review date. It is not projected to the later sales cutoff. Inventory training uses strictly earlier dates; the forecast starts on the snapshot date (explicit start-of-day convention). Future snapshots are never used for earlier decisions.

On-order units offset proposed purchases and stockout risk, as section 8.1 specifies. Overstock uses physical on-hand; incoming excess is a separate field. On-hand-only shortfalls remain a receipt-timing warning because arrivals are unknown. If arrival dates are supplied, receipt scheduling can be refined; no arrival date is invented here. Current decisions after the latest snapshot remain unavailable; historical snapshot conclusions are labelled with their actual date. A missing unit-error history blocks safety-stock scoring for that SKU.

Supplied launch dates conflict with some observed sales dates. These are reported and retained pending source-owner clarification. The undated current master is not used as a historical CV predictor. Future calendar attributes and actual promotion flags are not treated as advance-known plans.

`--allow-partial` explicitly permits absent extracts, not malformed present extracts. The default command fails with the missing filenames. Required source filenames, SHA-256 hashes, normalization counts, join counts, anomalies and the cutoff appear in the run artifacts. No data is downloaded or published.

The supplied file covers SKU001–SKU200, but sales and master cover SKU001–SKU050. No category/cost/demand is fabricated for the other 150. The latest snapshot is 2025-12-01; sales end 2025-12-31. Source Inventory_Value is not assumed to equal the cost valuation: 1,176 matched records do not reconcile to Current_Stock × current Cost_Price. Historical cost changes and source valuation policy are unavailable, so this is a reconciliation finding, not proof of an accounting error. Source Safety_Stock/Reorder_Point are retained in the analysis-ready dataset; model recommendations explicitly recalculate these from forecast demand and the stated service rule.

Currency evidence: see CURRENCY_EVIDENCE.md. The project brief requests rupees but does not explicitly establish CSV denomination; no INR assumption is made.
