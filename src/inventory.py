"""Inventory intelligence: safety stock, reorder point, EOQ, risk flags, order recommendations."""
import numpy as np
import pandas as pd

Z = {0.90: 1.2816, 0.95: 1.6449, 0.97: 1.8808, 0.99: 2.3263}
REVIEW_DAYS = 7          # how often stock is reviewed / ordered
OVERSTOCK_COVER = 60     # days of cover above which stock is "excess"
COST_RATIO = 0.65        # simulated unit cost as share of selling price
ORDERING_COST = 2000     # simulated fixed cost per purchase order (same currency as Price)
HOLDING_RATE = 0.20      # annual holding cost as share of unit cost


def simulate_inventory(sku_summary, seed=42):
    """The dataset has no stock data, so these columns are SIMULATED (fixed seed, documented in README)."""
    rng = np.random.default_rng(seed)
    n = len(sku_summary)
    out = sku_summary.copy()
    out["lead_time_days"] = rng.integers(3, 15, n)
    # current cover drawn from a wide range so the demo shows healthy, low and excess stock
    cover = np.where(rng.random(n) < 0.35, rng.uniform(2, 14, n),
             np.where(rng.random(n) < 0.35, rng.uniform(60, 110, n), rng.uniform(15, 55, n)))
    out["current_stock"] = np.round(cover * out["avg_daily_demand_hist"]).astype(int)
    out["unit_cost"] = (out["price"] * COST_RATIO).round(2)
    return out


def compute_recommendations(df, service_level=0.95):
    """df needs: sku, avg_daily_demand (forecast), demand_std (daily forecast error),
    lead_time_days, current_stock, unit_cost, price."""
    z = Z[service_level]
    r = df.copy()
    d, L = r["avg_daily_demand"], r["lead_time_days"]
    r["safety_stock"] = np.ceil(z * r["demand_std"] * np.sqrt(L))
    r["reorder_point"] = np.ceil(d * L + r["safety_stock"])
    r["days_of_cover"] = (r["current_stock"] / d).round(1)
    annual = d * 365
    holding = r["unit_cost"] * HOLDING_RATE
    r["eoq"] = np.ceil(np.sqrt(2 * annual * ORDERING_COST / holding))
    target = d * (L + REVIEW_DAYS) + r["safety_stock"]
    r["recommended_order_qty"] = np.ceil(np.maximum(0, target - r["current_stock"]))

    stockout = (r["current_stock"] < r["reorder_point"])
    overstock = r["days_of_cover"] > OVERSTOCK_COVER
    r["flag"] = np.where(stockout, "Stockout risk", np.where(overstock, "Overstock", "Healthy"))
    r["priority"] = np.select(
        [stockout & (r["days_of_cover"] < L), stockout, overstock],
        ["Critical", "High", "Low"], default="-")

    # money impact
    r["expected_lost_sales_value"] = (np.maximum(0, d * L - r["current_stock"]) * r["price"]).round(0)
    r["excess_units"] = np.maximum(0, r["current_stock"] - d * OVERSTOCK_COVER).round(0)
    r["excess_inventory_value"] = (r["excess_units"] * r["unit_cost"]).round(0)
    r["order_value"] = (r["recommended_order_qty"] * r["unit_cost"]).round(0)
    r["action"] = np.select(
        [r["flag"] == "Stockout risk", r["flag"] == "Overstock"],
        ["Order " + r["recommended_order_qty"].astype(int).astype(str) + " units now",
         "Pause reordering; " + r["excess_units"].astype(int).astype(str) + " excess units"],
        default="No action")
    return r
