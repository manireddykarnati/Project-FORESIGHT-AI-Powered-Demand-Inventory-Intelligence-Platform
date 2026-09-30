# Local scoring

The light dashboard uses compact Category, Product and Action status dropdowns. Each starts with an All option. Revenue class and the percentage-formatted service level are under Planning settings. Reset filters restores the default view. Changing category clears any product that no longer belongs to it. Detailed source limitations are available under Data scope & assumptions, with the historical stock date and currency status also visible above the charts.

Start `streamlit run app/streamlit_app.py` after the pipeline. Category, ABC, SKU and risk filters apply to forecast choices, inventory KPIs, the action list and EDA. Model-comparison metrics describe the global evaluation and are labelled separately. The Forecast tab accepts comma-separated SKU IDs for batch lookup. It returns the saved 56-day daily forecast (plus the displayed weekly table) and inventory risk at the selected service level. It does not retrain at interaction time.

Python interface:

```python
from src.scoring import score
result = score(["SKU001", "SKU002"], output_dir="outputs", service_level=0.95)
print(result["forecast"][["sku", "date", "forecast", "lower", "upper"]])
print(result["risk"])
print(result["unavailable_risk_skus"])
```

Inputs: a nonempty list of nonempty SKU strings; whitespace/case are normalized and duplicates removed. Service level is 0.90, 0.95, 0.97 or 0.99. Unknown SKUs, malformed artifacts, unsupported service levels and empty requests raise a descriptive `ValueError`. The dashboard catches it and displays an error without a traceback. An unavailable inventory result is an explicit list of affected SKUs, never a zero-stock assumption. Output includes demand `as_of`, historical `risk_as_of`, `risk_scope`, and nullable `currency`. The dates differ: final demand uses 2025-12-31 history, while risk replays the 2025-12-01 snapshot using only earlier demand.

`forecast` is a pandas DataFrame with SKU/date, origin, selected forecast, seasonal-naive baseline, LightGBM model forecast, uncertainty bounds, low-confidence flag and method. `risk` contains supported stock positions, safety stock, lead-time demand, four-quadrant status, priority, consistent order/clearance quantities and financial exposures. No INR claim is made until confirmed.

Forecast dates follow the source cutoff and must not be mistaken for today's demand. Nominal 95% normal error bands use ±1.96 times the final selected model's backtest residual standard deviation; weekly bands use residuals of weekly sums. They are approximate and uncalibrated. No bands are attached to the same backtest observations used to estimate their scale.

Promotion sensitivity is in `outputs/promotion_scenario.csv`: all days promoted versus the model's no-promotion scenario. This is a hypothetical model response, not a confirmed plan or causal lift. Sparse/new SKUs use category-peer recent mean demand if available, otherwise their own recent mean; no-history/no-peer SKUs fail with an actionable error.

The historical inventory forecast is separately saved in `outputs/inventory_forecasts.csv`. Risk safety stock uses prior 56-day seasonal-naive errors available before its snapshot, rather than the later final-forecast validation errors. Run metadata records the scope and proxy-validation outcomes. Verify fresh stock before acting on any historical recommendation.
