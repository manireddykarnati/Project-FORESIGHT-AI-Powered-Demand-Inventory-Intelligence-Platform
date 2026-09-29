"""FORESIGHT dashboard. Loads precomputed CSVs from outputs/ (no training at runtime)."""
import json, sys
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.inventory import compute_recommendations, Z, OVERSTOCK_COVER

st.set_page_config(page_title="FORESIGHT | Demand & Inventory Intelligence", page_icon="📦", layout="wide")

BG = "#0E1117"; PANEL = "#161B22"; PANEL2 = "#1C2430"; BORDER = "#2A3441"
TEXT = "#E6EDF3"; MUTED = "#8B96A5"
GREEN, RED, AMBER, BLUE = "#3BA776", "#E5484D", "#E8A33D", "#4C8DF6"

pio.templates["foresight_dark"] = pio.templates["plotly_dark"]
pio.templates["foresight_dark"].layout.update(
    paper_bgcolor=PANEL, plot_bgcolor=PANEL,
    font=dict(color=TEXT, family="Inter, sans-serif", size=13),
    colorway=[GREEN, BLUE, AMBER, RED, "#B084F0"],
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER), yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    legend=dict(bgcolor="rgba(0,0,0,0)"), margin=dict(t=50, b=20, l=10, r=10),
    hoverlabel=dict(bgcolor=PANEL2, bordercolor=BORDER, font=dict(color=TEXT, size=12)),
)
pio.templates.default = "foresight_dark"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: radial-gradient(circle at 15% 0%, #131A24 0%, {BG} 45%); }}
#MainMenu, header, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px; }}
.kpi-card, .stButton>button, .stDownloadButton>button {{ transition: background-color .18s ease, border-color .18s ease, transform .12s ease, box-shadow .18s ease; }}
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #10151D 0%, #0B0F14 100%); border-right: 1px solid {BORDER}; }}
.kpi-card {{ background: linear-gradient(160deg, {PANEL2}, {PANEL}); border:1px solid {BORDER}; border-radius:16px;
    padding:18px 20px; position:relative; overflow:hidden; }}
.kpi-card:hover {{ border-color:#3A4757; transform: translateY(-2px); box-shadow: 0 10px 28px rgba(0,0,0,.35); }}
.kpi-card::before {{ content:""; position:absolute; top:0; left:0; width:4px; height:100%; background:var(--accent, {GREEN}); }}
.kpi-label {{ color:{MUTED}; font-size:.76rem; font-weight:600; text-transform:uppercase; letter-spacing:.06em; margin-bottom:6px; }}
.kpi-value {{ font-size:1.65rem; font-weight:800; color:{TEXT}; line-height:1.1; }}
.kpi-delta {{ font-size:.78rem; margin-top:6px; font-weight:600; }}
.card {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:16px; padding:20px 22px; margin-bottom:1rem; }}
.card h4 {{ margin-top:0; font-size:1rem; font-weight:700; color:{TEXT}; }}
.stTabs [data-baseweb="tab-list"] {{ gap:4px; background:{PANEL}; padding:5px; border-radius:12px; border:1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{ border-radius:9px; padding:8px 16px; color:{MUTED}; font-weight:600; font-size:.9rem; }}
.stTabs [aria-selected="true"] {{ background:{GREEN} !important; color:#04140C !important; }}
[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; border-radius:12px; overflow:hidden; }}
.stButton>button, .stDownloadButton>button {{ background:linear-gradient(135deg,{GREEN},#1f6e4a); color:white;
    border:none; border-radius:10px; font-weight:600; padding:.5rem 1.1rem; }}
.stButton>button:hover, .stDownloadButton>button:hover {{ box-shadow:0 6px 18px rgba(59,167,118,.4); transform:translateY(-1px); }}
.rec-banner {{ background:linear-gradient(135deg, rgba(59,167,118,.14), rgba(59,167,118,.03));
    border:1px solid rgba(59,167,118,.35); border-radius:14px; padding:16px 20px; }}
.mini-metric {{ text-align:center; }}
.mini-metric .v {{ font-size:1.3rem; font-weight:800; }}
.mini-metric .l {{ color:{MUTED}; font-size:.75rem; text-transform:uppercase; letter-spacing:.05em; }}
</style>
""", unsafe_allow_html=True)


def kpi(col, label, value, delta=None, accent=GREEN, delta_color=MUTED):
    d = f'<div class="kpi-delta" style="color:{delta_color}">{delta}</div>' if delta else ""
    col.markdown(f"""<div class="kpi-card" style="--accent:{accent}">
        <div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>{d}</div>""", unsafe_allow_html=True)

def render_chart(fig, container=None):
    """Keep our dark hover labels and avoid Streamlit theme overrides."""
    fig.update_layout(hoverlabel=dict(
        bgcolor=PANEL2, bordercolor=BORDER,
        font=dict(color=TEXT, family="Inter, sans-serif", size=13),
        namelength=-1,
    ))
    target = st if container is None else container
    target.plotly_chart(fig, width="stretch", theme=None)



COLORS = {"Stockout risk": "#D64545", "Overstock": "#E8A33D", "Healthy": "#3BA776"}


@st.cache_data
def load():
    fc = pd.read_csv(ROOT / "outputs/forecasts.csv", parse_dates=["date"])
    inputs = pd.read_csv(ROOT / "outputs/sku_inputs.csv")
    metrics = pd.read_csv(ROOT / "outputs/model_metrics.csv")
    imp = pd.read_csv(ROOT / "outputs/feature_importance.csv")
    info = json.load(open(ROOT / "outputs/run_info.json"))
    sales = pd.read_csv(ROOT / "data/sales_daily.csv", parse_dates=["Date"])
    return fc, inputs, metrics, imp, info, sales


fc, inputs, metrics, imp, info, sales = load()

# ---------------- sidebar ----------------
st.sidebar.title("📦 FORESIGHT")
st.sidebar.caption("AI-powered demand & inventory intelligence")
sl = st.sidebar.select_slider("Target service level", options=list(Z.keys()), value=0.95,
                              format_func=lambda x: f"{int(x*100)}%",
                              help="Higher service level = more safety stock = fewer stockouts, more cash tied up.")
abc = st.sidebar.multiselect("ABC class (by revenue)", ["A", "B", "C"], default=["A", "B", "C"])
flags = st.sidebar.multiselect("Risk flag", list(COLORS), default=list(COLORS))
sku_sel = st.sidebar.selectbox("SKU for detail view", sorted(inputs["sku"]))
st.sidebar.divider()
st.sidebar.caption("Stock, lead time and unit cost are **simulated** (the dataset has no inventory data). "
                   "Forecast assumes no promotions in the next 30 days.")

@st.cache_data(show_spinner=False)
def recompute(inputs, sl):
    return compute_recommendations(inputs, sl)

with st.spinner("Recomputing inventory recommendations…"):
    rec = recompute(inputs, sl)
    view = rec[rec["abc_class"].isin(abc) & rec["flag"].isin(flags)]

# ---------------- header + KPIs ----------------
st.title("Project FORESIGHT")
st.caption(f"Forecast window: {info['forecast_start']} → {info['forecast_end']}  |  "
           f"Backtest: {info['test_start']} → {info['test_end']}")

k1, k2, k3, k4, k5 = st.columns(5)
kpi(k1, "Forecast demand (30d)", f"{rec['forecast_30d_units'].sum():,.0f}", "units, next 30 days", BLUE)
n_stock, n_crit = int((rec.flag == "Stockout risk").sum()), int((rec.priority == "Critical").sum())
kpi(k2, "Stockout risk", f"{n_stock} SKUs", f"{n_crit} critical", RED, RED if n_crit else MUTED)
kpi(k3, "Overstocked", f"{int((rec.flag=='Overstock').sum())} SKUs", "> 60 days cover", AMBER)
kpi(k4, "Excess inventory value", f"{rec['excess_inventory_value'].sum()/1e6:,.2f}M", "cash tied up", AMBER)
acc = 100 - info['wape_lightgbm']
kpi(k5, "Forecast accuracy", f"{acc:.1f}%", f"WAPE {info['wape_lightgbm']:.1f}% vs {info['wape_naive']:.1f}% naive", GREEN, GREEN)
t1, t2, t3, t4, t5 = st.tabs(["📈 Forecast", "🏭 Inventory health", "✅ Recommendations", "🧪 Model performance", "🔍 Data insights"])

# ---------------- Tab 1 ----------------
with t1:
    d = fc[fc.sku == sku_sel]
    r = rec[rec.sku == sku_sel].iloc[0]
    st.subheader(f"{sku_sel}: actual vs forecast")
    fig = go.Figure()
    hist = d[d.type.isin(["history", "backtest"])]
    fig.add_trace(go.Scatter(x=hist.date, y=hist.actual, name="Actual", line=dict(color=TEXT, width=2),
                             hovertemplate="Actual: %{y:.1f}<extra></extra>"))
    bt = d[d.type == "backtest"]
    fig.add_trace(go.Scatter(x=bt.date, y=bt.forecast, name="Backtest forecast",
                             line=dict(color=AMBER, dash="dot", width=2),
                             hovertemplate="Backtest forecast: %{y:.1f}<extra></extra>"))
    fu = d[d.type == "future"]
    fig.add_trace(go.Scatter(x=pd.concat([fu.date, fu.date[::-1]]), y=pd.concat([fu.upper, fu.lower[::-1]]),
                             fill="toself", fillcolor="rgba(59,167,118,0.15)", line=dict(width=0),
                             name="95% interval", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fu.date, y=fu.forecast, name="30-day forecast", line=dict(color=GREEN, width=3),
                             hovertemplate="30-day forecast: %{y:.1f}<extra></extra>"))
    fig.update_layout(height=420, hovermode="x", legend=dict(orientation="h", y=1.1))

    render_chart(fig)
    c = st.columns(4)
    c[0].metric("Avg forecast demand", f"{r.avg_daily_demand:.1f} / day")
    c[1].metric("Current stock", f"{int(r.current_stock)} units")
    c[2].metric("Days of cover", f"{r.days_of_cover:.1f} d", f"lead time {int(r.lead_time_days)} d", delta_color="off")
    c[3].metric("Status", r.flag)
    st.info(f"**Recommendation:** {r.action}. Reorder point is {int(r.reorder_point)} units "
            f"(safety stock {int(r.safety_stock)}). Suggested order value: {r.order_value:,.0f}.")

# ---------------- Tab 2 ----------------
with t2:
    a, b = st.columns([1, 2])
    cnt = view["flag"].value_counts().reset_index()
    cnt.columns = ["flag", "SKUs"]
    render_chart(px.pie(cnt, names="flag", values="SKUs", hole=.55, color="flag", color_discrete_map=COLORS)
                   .update_layout(height=380, margin=dict(t=30, b=0)), container=a)
    v = view.sort_values("days_of_cover")
    fig = px.bar(v, x="sku", y="days_of_cover", color="flag", color_discrete_map=COLORS,
                     hover_data=["current_stock", "reorder_point", "lead_time_days"])
    fig.add_hline(y=OVERSTOCK_COVER, line_dash="dash", line_color=AMBER, annotation_text="overstock threshold")
    fig.update_layout(height=340, showlegend=False,
                          hoverlabel=dict(bgcolor=PANEL2, bordercolor=BORDER, font=dict(color=TEXT, size=12)))
    render_chart(fig.update_layout(height=380, margin=dict(t=40, b=0)), container=b)

    top = view.sort_values("current_stock", ascending=False).head(20)
    fig = go.Figure()
    fig.add_bar(x=top.sku, y=top.current_stock, name="Current stock", marker_color="#1f3a5f")
    fig.add_scatter(x=top.sku, y=top.reorder_point, name="Reorder point", mode="markers",
                    marker=dict(color="#D64545", size=11, symbol="diamond"))
    fig.update_layout(title="Stock vs reorder point (20 largest positions)", height=380, margin=dict(t=40, b=0))
    render_chart(fig)

    m1, m2 = st.columns(2)
    m1.metric("Lost-sales exposure (lead-time shortfall)", f"{view['expected_lost_sales_value'].sum()/1e6:,.2f} M")
    m2.metric("Cash tied up in excess stock", f"{view['excess_inventory_value'].sum()/1e6:,.2f} M")

# ---------------- Tab 3 ----------------
with t3:
    st.subheader("Action list")
    order = {"Critical": 0, "High": 1, "Low": 2, "-": 3}
    tbl = view.assign(_o=view.priority.map(order)).sort_values(["_o", "days_of_cover"])
    cols = ["sku", "abc_class", "flag", "priority", "current_stock", "reorder_point", "safety_stock",
            "days_of_cover", "lead_time_days", "recommended_order_qty", "eoq", "order_value", "action"]
    st.dataframe(tbl[cols], width="stretch", hide_index=True, height=480)
    st.download_button("⬇ Download recommendations (CSV)", tbl[cols].to_csv(index=False).encode(),
                       "foresight_recommendations.csv", "text/csv")
    st.caption(f"Recomputed live at a {int(sl*100)}% service level. Move the slider in the sidebar to see "
               "safety stock, reorder points and order quantities change.")

# ---------------- Tab 4 ----------------
with t4:
    st.subheader("Model comparison (90-day rolling backtest, 30-day horizon)")
    st.dataframe(metrics.rename(columns={"WAPE_pct": "WAPE %", "Bias_pct": "Bias %"}), hide_index=True,
                 width="stretch")
    gain = (info["wape_naive"] - info["wape_lightgbm"]) / info["wape_naive"] * 100
    st.success(f"LightGBM reduces forecast error by **{gain:.1f}%** versus the naive baseline (WAPE).")
    st.caption("Each 30-day window is forecast recursively from actual history only, the same way the model is used "
               "in production. Actual promotion flags are used in the backtest (promos are usually planned in advance).")
    x, y = st.columns(2)
    render_chart(px.bar(imp.sort_values("importance"), x="importance", y="feature", orientation="h",
                          title="Feature importance (gain %)").update_layout(height=420), container=x)
    sa = inputs.sort_values("wape_pct")
    render_chart(px.bar(sa, x="sku", y="wape_pct", title="Backtest WAPE % by SKU").update_layout(height=420),
                   container=y)

# ---------------- Tab 5 ----------------
with t5:
    tot = sales.groupby("Date")["Units_Sold"].sum().reset_index()
    render_chart(px.line(tot, x="Date", y="Units_Sold", title="Total daily units sold").update_layout(height=320),
                    )
    c1, c2 = st.columns(2)
    dow = tot.assign(day=tot.Date.dt.day_name()).groupby("day")["Units_Sold"].mean() \
             .reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]).reset_index()
    render_chart(px.bar(dow, x="day", y="Units_Sold", title="Average units by weekday"), container=c1)
    mo = tot.groupby(tot.Date.dt.month)["Units_Sold"].mean().reset_index()
    render_chart(px.bar(mo, x="Date", y="Units_Sold", title="Average units by month").update_xaxes(title="Month"),
                    container=c2)
    lift = sales.groupby("Promotion")["Units_Sold"].mean()
    st.metric("Promotion lift", f"+{(lift[1]/lift[0]-1)*100:.0f}% units on promo days")
