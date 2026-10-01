"""FORESIGHT dashboard. Loads precomputed CSVs from outputs/ (no training at runtime)."""
import sys, os
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.inventory import compute_recommendations, Z
from src.scoring import load_outputs, score
OUTPUT = Path(os.environ.get("FORESIGHT_OUTPUT_DIR", str(ROOT / "outputs")))

st.set_page_config(page_title="FORESIGHT | Planning review", layout="wide")

BG = "#FFFFFF"; PANEL = "#FFFFFF"; PANEL2 = "#F5F7FA"; BORDER = "#E2E8EF"
TEXT = "#202D3A"; MUTED = "#637487"
GREEN, RED, AMBER, BLUE = "#347A66", "#B45353", "#A66E25", "#245B85"

pio.templates["foresight_light"] = pio.templates["plotly_white"]
pio.templates["foresight_light"].layout.update(
    paper_bgcolor=PANEL, plot_bgcolor=PANEL,
    font=dict(color=TEXT, family="Arial, sans-serif", size=13),
    colorway=[BLUE, GREEN, AMBER, RED, "#76638E"],
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER), yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-.2),
    margin=dict(t=60, b=65, l=10, r=10),
    hoverlabel=dict(bgcolor=PANEL2, bordercolor=BORDER, font=dict(color=TEXT, size=12)),
)
pio.templates.default = "foresight_light"

st.markdown(f"""
<style>
.stApp {{ background:{BG}; color:{TEXT}; }}
.block-container {{ padding-top:2.8rem; padding-bottom:3rem; max-width:1440px; }}
section[data-testid="stSidebar"] {{ background:{PANEL2}; border-right:1px solid {BORDER}; }}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{ padding-top:1.7rem; }}
.brand {{ font-size:1.2rem; font-weight:700; letter-spacing:.13em; color:{BLUE}; margin-bottom:.25rem; }}
.eyebrow {{ font-size:.72rem; font-weight:600; letter-spacing:.12em; color:{MUTED}; text-transform:uppercase; }}
h1 {{ font-size:2rem !important; font-weight:600 !important; letter-spacing:-.035em; padding-bottom:.25rem !important; }}
h2, h3 {{ font-weight:600 !important; letter-spacing:-.02em; }}
section[data-testid="stSidebar"] h3 {{ font-size:1.05rem !important; }}
[data-testid="stMetric"] {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:8px; padding:17px 20px; }}
[data-testid="stMetricLabel"] {{ color:{MUTED}; }}
[data-testid="stMetricValue"] {{ font-size:1.7rem; font-weight:600; }}
.stTabs [data-baseweb="tab-list"] {{ gap:24px; border-bottom:1px solid {BORDER}; margin-top:14px; }}
.stTabs [data-baseweb="tab"] {{ padding:12px 0; color:{MUTED}; background:transparent; font-weight:500; }}
.stTabs [aria-selected="true"] {{ color:{BLUE} !important; }}
[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; border-radius:8px; overflow:hidden; }}
.stButton>button, .stDownloadButton>button {{ border-radius:6px; font-weight:500; }}
div[data-testid="stExpander"] {{ border-color:{BORDER}; }}
@media (max-width:768px) {{
  .block-container {{ padding-top:2rem; }}
  .stTabs [data-baseweb="tab-list"] {{ gap:16px; }}
}}
</style>
""", unsafe_allow_html=True)


def render_chart(fig, container=None):
    """Use one light, readable chart style across all views."""
    fig.update_layout(hoverlabel=dict(
        bgcolor=PANEL2, bordercolor=BORDER,
        font=dict(color=TEXT, family="Arial, sans-serif", size=13),
        namelength=-1,
    ))
    target = st if container is None else container
    target.plotly_chart(fig, width="stretch", theme=None)



COLORS = {'Reorder now': RED, 'Markdown / clear': AMBER, 'Watch / volatile': '#76638E', 'Healthy': GREEN}


def reset_filters():
    # Explicit values also reset the browser widgets; deleting keys can leave
    # stale selections visible even when the server uses the defaults.
    st.session_state.update(
        category_filter='All categories', product_filter='All products',
        class_filter='All classes', risk_filter='All statuses', service_level=.95,
    )


def date_label(value):
    return pd.Timestamp(value).strftime('%d %b %Y') if value else 'Unavailable'

st.markdown('<div class="eyebrow">FORESIGHT / Planning review</div>', unsafe_allow_html=True)
st.title('Demand & inventory')
try:
    with st.spinner('Loading validated forecasts and source availability…'):
        fc, inputs, metrics, info = load_outputs(OUTPUT)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

st.caption(f"Sales through {date_label(info['as_of'])} · Forecast {date_label(info['forecast_start'])} – {date_label(info['forecast_end'])}")
st.sidebar.markdown('<div class="brand">FORESIGHT</div>', unsafe_allow_html=True)
st.sidebar.caption('Demand & inventory planning')
st.sidebar.divider()
st.sidebar.subheader('Filter view')
categories = sorted(inputs.category.dropna().unique())
category = st.sidebar.selectbox('Category', ['All categories']+categories, key='category_filter')
category_inputs = inputs if category == 'All categories' else inputs[inputs.category == category]
choices = ['All products']+sorted(category_inputs.sku)
if st.session_state.get('product_filter') not in choices:
    st.session_state['product_filter'] = 'All products'
product = st.sidebar.selectbox('Product', choices, key='product_filter', help='Type a SKU to find a product.')
risk = st.sidebar.selectbox('Action status', ['All statuses']+list(COLORS)+['Unavailable'], key='risk_filter')
with st.sidebar.expander('Planning settings'):
    abc = st.selectbox('Revenue class', ['All classes','A','B','C'], key='class_filter',
                       help='A: largest revenue contributors. B: middle group. C: remaining products.')
    sl = st.select_slider('Target service level', options=list(Z), value=.95, key='service_level',
                          format_func=lambda x:f'{x:.0%}', help='Higher targets increase the safety-stock allowance.')
st.sidebar.button('Reset filters', on_click=reset_filters, use_container_width=True, key='reset_filters')
st.sidebar.divider()
st.sidebar.caption(f"Stock snapshot · {date_label(info.get('inventory_as_of'))}")
st.sidebar.caption('Historical review. Confirm fresh stock before placing orders.')
valid_inputs = inputs[inputs.inventory_available == True]
try:
    with st.spinner('Updating inventory recommendations…'):
        rec = compute_recommendations(valid_inputs, sl) if not valid_inputs.empty else pd.DataFrame(columns=['sku','flag'])
except ValueError as exc:
    st.error(f'Inventory inputs are invalid: {exc}')
    st.stop()
view = category_inputs.copy()
if product != 'All products':
    view = view[view.sku == product]
if abc != 'All classes':
    view = view[view.abc_class == abc]
view['flag'] = view.sku.map(rec.set_index('sku').flag).fillna('Unavailable')
if risk != 'All statuses':
    view = view[view.flag == risk]
if info['missing_extracts']:
    st.warning('Incomplete source data: ' + ', '.join(info['missing_extracts']) + '. Inventory results are shown only where supported.')
scope = f"Inventory review: {date_label(info.get('inventory_as_of'))} snapshot"
if not info.get('currency'):
    scope += ' · Financial values in unconfirmed source currency'
st.caption(scope)
with st.expander('Data scope & assumptions'):
    st.write('Inventory decisions reflect the recorded snapshot. Confirm fresh stock and receipt dates before acting.')
    if info.get('inventory_unmatched_skus'):
        st.write(f"{info['inventory_unmatched_skus']} inventory-only SKUs lack matching sales and master records and are excluded from scoring.")
    if not info.get('currency'):
        st.write('The source currency is not confirmed. Financial values have not been converted or labelled as INR.')
    st.write('Forecasts assume no planned promotions. Uncertainty bands are approximate and have not been empirically calibrated.')
if view.empty:
    st.info('No matching SKUs. Choose a broader category or action status, or reset the filters.')
    st.stop()
selected = view.sku.tolist()
rv = rec[rec.sku.isin(selected)]
unit = 'INR (₹)' if info.get('currency') == 'INR' else 'source currency units (unconfirmed)'
k1,k2,k3,k4 = st.columns(4)
k1.metric('Forecast units · 8 weeks', f'{view.forecast_56d_units.sum():,.0f}')
k2.metric('Products in view', len(view))
k3.metric('Reorder review', int((rv.flag == 'Reorder now').sum()))
k4.metric('Clearance review', int((rv.flag == 'Markdown / clear').sum()))
st.sidebar.caption(f'{len(view)} of {len(inputs)} supported products in view')
t1,t2,t3,t4,t5 = st.tabs(['Forecast','Inventory','Actions','Performance','Insights'])
with t1:
    sku_sel = st.selectbox('Product forecast', selected)
    d = fc[fc.sku == sku_sel]
    fig = go.Figure()
    bt, fu = d[d.type == 'backtest'], d[d.type == 'future']
    for frame, column, name, color in [(bt,'actual','Actual',TEXT),(bt,'forecast','Selected backtest forecast',GREEN),
                                       (bt,'baseline','Seasonal naive',AMBER),(fu,'forecast','Next 8 weeks',BLUE)]:
        fig.add_scatter(x=frame.date,y=frame[column],name=name,line=dict(color=color))
    if 'model_forecast' in bt and info['selected_model'] != 'LightGBM':
        fig.add_scatter(x=bt.date,y=bt.model_forecast,name='LightGBM backtest',line=dict(dash='dot'))
    fig.add_scatter(x=pd.concat([fu.date,fu.date[::-1]]),y=pd.concat([fu.upper,fu.lower[::-1]]),
                    fill='toself',fillcolor='rgba(76,141,246,.15)',line=dict(width=0),name='Approx. nominal 95% band')
    fig.update_layout(title=f'{sku_sel}: daily demand',xaxis_title='Date',yaxis_title='Units',height=460)
    render_chart(fig)
    st.caption(info['interval'] + '. Final-forecast bands only; normal, stable-error assumption. No calibrated coverage claim.')
    if bool(view.set_index('sku').loc[sku_sel,'low_confidence']):
        st.warning('Low-confidence forecast: sparse/new SKU fallback; validate category comparability.')
    try:
        wf = pd.read_csv(OUTPUT/'weekly_forecasts.csv')
        st.subheader('Weekly forecast')
        weekly_view = wf[wf.sku == sku_sel][['week_start','week_end','forecast','lower','upper']].rename(columns={
            'week_start':'Week starting', 'week_end':'Week ending', 'forecast':'Forecast units',
            'lower':'Lower estimate', 'upper':'Upper estimate'})
        st.dataframe(weekly_view, hide_index=True, use_container_width=True,
                     column_config={c:st.column_config.NumberColumn(format='%.0f')
                                    for c in ['Forecast units','Lower estimate','Upper estimate']})
    except (OSError, ValueError, KeyError) as exc:
        st.error(f'Weekly output unavailable: {exc}')
    st.subheader('Product lookup')
    entered = st.text_input('SKU IDs, separated by commas', value=sku_sel, key='score_request')
    if st.button('Get forecast & risk', key='score_button', type='primary'):
        try:
            result = score([s.strip() for s in entered.split(',')], OUTPUT, sl)
            st.dataframe(result['forecast'], hide_index=True)
            if result['unavailable_risk_skus']:
                st.warning('Risk unavailable for: ' + ', '.join(result['unavailable_risk_skus']))
            if not result['risk'].empty:
                st.dataframe(result['risk'], hide_index=True)
        except ValueError as exc:
            st.error(str(exc))
with t2:
    st.subheader('Stockout versus overstock decision grid')
    st.caption('Stockout risk uses on-hand plus on-order; excess uses physical on-hand. Receipt-timing shortfalls are shown separately. Positive values on both axes mean investigate before acting.')
    if rv.empty:
        st.info('Inventory risk unavailable: supply dated inventory snapshots with on-hand, on-order and lead times.')
    else:
        fig = px.scatter(rv,x='overstock_axis',y='stockout_axis',size='revenue_at_stake',color='flag',
                         hover_name='sku',color_discrete_map=COLORS, size_max=50,
                         labels={'overstock_axis':'Excess / 60-day demand','stockout_axis':'Position shortage / reorder point'})
        fig.add_vline(x=0,line_dash='dash');fig.add_hline(y=0,line_dash='dash')
        fig.update_layout(xaxis_range=[-.1,max(.2,rv.overstock_axis.max()*1.1)],yaxis_range=[-.1,1.1])
        render_chart(fig)
        st.dataframe(rv[['sku','flag','current_stock','on_order','inventory_position','reorder_point','days_of_cover']],hide_index=True)
        st.caption('Bubble size is revenue at stake, not expected savings. Receipt dates are unknown; verify arrivals. High shortage/low excess: Reorder now; low shortage/high excess: Markdown / clear; high both: Watch / volatile; low both: Healthy.')
with t3:
    if rv.empty:
        st.info('No supported reorder or clearance recommendations. Missing stock is not treated as zero.')
    else:
        st.subheader('Recommended actions')
        st.caption(f"Prioritised from the {date_label(info.get('inventory_as_of'))} stock snapshot. Verify fresh stock before acting.")
        cols=['sku','priority','flag','recommended_order_qty','clearance_review_units','order_value','excess_inventory_value','lead_time_revenue_exposure','receipt_delay_revenue_exposure','action']
        st.dataframe(rv[cols].rename(columns={
            'sku':'SKU', 'priority':'Priority', 'flag':'Action status', 'recommended_order_qty':'Order units',
            'clearance_review_units':'Clearance review units', 'order_value':'Proposed spend',
            'excess_inventory_value':'Excess stock value', 'lead_time_revenue_exposure':'Revenue exposure',
            'receipt_delay_revenue_exposure':'Receipt-delay exposure', 'action':'Recommendation'}),hide_index=True)
        st.download_button('Download recommendations',rv[cols].to_csv(index=False),'recommendations.csv','text/csv')
        st.caption(f'Financial amounts: {unit}. Spend, stock at cost and revenue exposure are separate measures; do not sum as savings.')
with t4:
    st.subheader('Three rolling-origin folds; retrained every 56 days')
    st.dataframe(metrics,hide_index=True)
    st.caption(f"Selected on weekly WAPE: {info['selected_model']}. Both baselines use identical folds and horizon. Zero-demand observations are excluded from secondary MAPE; zero-total WAPE is undefined. Scores do not represent classification accuracy.")
    if 'wape_pct' in view:
        render_chart(px.bar(view, x='sku', y='wape_pct', title='Selected SKU daily backtest WAPE', labels={'wape_pct':'WAPE (%)'}))
    st.caption('Prices are last observed before each origin. Backtests and base forecasts assume no promotions; future actual promotions are not read.')
    try:
        imp = pd.read_csv(OUTPUT/'feature_importance.csv')
        render_chart(px.bar(imp.sort_values('importance'),x='importance',y='feature',orientation='h',title='Final LightGBM feature gain (%)'))
    except (OSError, ValueError, KeyError):
        st.caption('Feature importance is unavailable for this run.')
with t5:
    try:
        sales = pd.read_csv(OUTPUT/'analysis_ready.csv',parse_dates=['Date'])
        sales = sales[sales.SKU.isin(selected)]
        if sales.empty:
            st.info('No observed sales for the selected new SKUs.')
        else:
            tot = sales.groupby('Date',as_index=False).Units_Sold.sum()
            render_chart(px.line(tot,x='Date',y='Units_Sold',title='Observed daily demand for filtered SKUs',labels={'Units_Sold':'Units sold'}))
            movers = sales[sales.Date > sales.Date.max()-pd.Timedelta(days=28)].groupby('SKU',as_index=False).Units_Sold.sum().sort_values('Units_Sold',ascending=False)
            render_chart(px.bar(movers.head(15),x='SKU',y='Units_Sold',title='Top movers: final 28 observed days',labels={'Units_Sold':'Units sold'}))
        if not sales.empty:
            weekday = sales.assign(weekday=sales.Date.dt.day_name()).groupby('weekday',as_index=False).Units_Sold.mean()
            monthly = sales.assign(month=sales.Date.dt.month).groupby('month',as_index=False).Units_Sold.mean()
            render_chart(px.bar(weekday,x='weekday',y='Units_Sold',title='Average daily SKU demand by weekday',labels={'Units_Sold':'Mean units / SKU-day'}))
            render_chart(px.bar(monthly,x='month',y='Units_Sold',title='Average daily SKU demand by month',labels={'Units_Sold':'Mean units / SKU-day'}))
            promo = sales.groupby('Promotion').Units_Sold.mean()
            if 0 in promo and 1 in promo and promo[0] > 0:
                st.metric('Observed promotion-day association', f'{(promo[1]/promo[0]-1)*100:+.1f}%')
                st.caption('Association only; not a causal campaign effect.')
        st.caption('Read reports/DATA_QUALITY_EDA_MEMO.md and reports/EXECUTIVE_READOUT.md for quality findings, actions and limitations.')
    except (OSError, ValueError, KeyError) as exc:
        st.error(f'Analysis-ready data unavailable: {exc}')
