# Project FORESIGHT: AI-Powered Demand & Inventory Intelligence

FORESIGHT forecasts SKU-level demand with machine learning, flags stockout and overstock risk, and
recommends what to order, all in an interactive Streamlit dashboard.

**Live dashboard:** _add your Streamlit link here_  |  **Demo video:** _add link_  |  **Slides:** _add link_

## Problem
Too little stock loses sales; too much ties up cash. Planners need a forward-looking view of demand per SKU and a
clear list of what to reorder now and what to stop buying.

## Pipeline
```
sales_daily.csv -> feature engineering -> LightGBM (global model, 50 SKUs)
                -> 90-day rolling backtest vs baselines
                -> 30-day recursive forecast + 95% interval
                -> inventory logic (safety stock, ROP, EOQ, days of cover)
                -> risk flags + order recommendations -> Streamlit dashboard
```

## Data
`data/sales_daily.csv`: 50 SKUs x 731 days (2024-01-01 to 2025-12-31); columns Date, SKU, Units_Sold, Revenue,
Price, Promotion. No missing values or duplicates. Weekend demand is about 25% higher, demand is seasonal
(peak Mar-Jun, low Oct), and promo days sell about 38% more.

## Method
- **Features:** weekday, month, day of year, weekend flag, promotion, price, lag 7/14/28, rolling mean 7/28 and
  rolling std 28 (all shifted, so there is no future leakage), SKU id as a categorical.
- **Models:** naive (last week's same weekday), 28-day moving average, and one global **LightGBM** model.
- **Validation:** time-based. Train on data before the last 90 days, then forecast the last 90 days in three
  30-day windows, each from actual history only (rolling-origin backtest). This matches how the model is used.
- **Metrics:** MAE, RMSE, WAPE, bias.

## Results (backtest, 30-day horizon)
| Model | MAE | RMSE | WAPE % |
|---|---|---|---|
| Naive (last week) | 3.92 | 5.12 | 32.6 |
| Moving average (28d) | 3.00 | 4.00 | 25.0 |
| **LightGBM** | **2.71** | **3.52** | **22.6** |

LightGBM cuts WAPE by about 31% versus the naive baseline. The remaining error is mostly random day-to-day
noise, which is why the inventory logic adds safety stock.

## Inventory logic
- Safety stock = Z x sigma x sqrt(lead time), where sigma is the SKU's daily backtest error std (Z = 1.65 at 95%)
- Reorder point = daily demand x lead time + safety stock
- Days of cover = current stock / forecast daily demand
- Order quantity = max(0, demand x (lead time + 7-day review) + safety stock - current stock)
- EOQ = sqrt(2 x annual demand x ordering cost / holding cost)
- **Stockout risk:** stock below reorder point (Critical if cover is shorter than the lead time)
- **Overstock:** more than 60 days of cover

## Assumptions (please read)
- **Stock levels, lead times (3-14 days) and unit cost (65% of price) are SIMULATED** with a fixed seed (42),
  because the dataset has no inventory data. Ordering cost (2,000) and holding rate (20%/yr) are assumed.
  Replace `simulate_inventory()` in `src/inventory.py` with real data to use this in practice.
- The 30-day forecast assumes **no promotions** are planned.
- Backtest uses actual promotion flags (promos are normally planned in advance).
- Currency is not stated in the data; values are shown in the same units as `Price`.

## Run it
```bash
pip install -r requirements.txt
python run_pipeline.py                  # trains, backtests, writes outputs/*.csv
streamlit run app/streamlit_app.py      # dashboard
```
The dashboard reads the precomputed CSVs in `outputs/`, so it needs no training at runtime.

## Deploy
Push to a public GitHub repo, open share.streamlit.io, choose the repo and `app/streamlit_app.py`, then Deploy.

## Structure
```
data/sales_daily.csv   src/features.py  src/forecast.py  src/inventory.py
run_pipeline.py        app/streamlit_app.py   outputs/ (forecasts, recommendations, metrics)
```

## Future work
Prophet/SARIMA comparison, hyperparameter tuning, holiday calendar, probabilistic (quantile) forecasts,
multi-echelon stock, SHAP explanations, real ERP stock feed.
