import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
from streamlit.components.v1 import iframe

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

# --- 2. GHL THEME ---
st.markdown("""
    <style>
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 160px; height: 50px; margin-left: 20px; margin-top: 20px; filter: invert(1) brightness(2);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; }
    div.stInfo { background-color: rgba(0, 82, 255, 0.08); border-left: 5px solid #0052FF; color: var(--text-color); border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA LOADER (FIX FOR KEYERROR) ---
@st.cache_data(ttl=60)
def load_and_clean_data(url):
    try:
        df = pd.read_csv(url)
        # CRITICAL FIX: Strip whitespace from headers AND data
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '')
        # Clean specific columns if they exist
        if 'Email' in df.columns: df['Email'] = df['Email'].astype(str).str.strip().str.lower()
        if 'Advisor Email' in df.columns: df['Advisor Email'] = df['Advisor Email'].astype(str).str.strip().str.lower()
        return df
    except:
        return pd.DataFrame()

def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    try:
        parts = time_str.lower().split()
        for p in parts:
            if 'h' in p: h = int(p.replace('h', ''))
            elif 'm' in p: m = int(p.replace('m', ''))
        return (h * 60) + m
    except: return 0

def create_ghl_gauge(title, value, target=None, is_percent=True, color_steps=False):
    steps = [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}] if color_steps else []
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 18, 'color': 'gray'}},
        number = {'suffix': "%" if is_percent else "", 'font': {'color': '#0052FF', 'size': 35}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"}, 'bgcolor': "white", 'steps': steps,
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target} if target else None}
    ))
    fig.update_layout(height=220, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_clean_data(TEAM_URL)

if not st.session_state.auth:
    col_l1, col_l2 = st.columns([1, 4])
    with col_l1: st.image(LOGO_URL, width=150)
    with col_l2: st.title("HIGHLEVEL PERFORMANCE HUB")
    with st.form("login"):
        e_in = st.text_input("Work Email").lower().strip()
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            user_match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str).str.strip() == str(p_in).strip())]
            if not user_match.empty:
                st.session_state.auth = user_match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. DATA PREP ---
user = st.session_state.auth
kpi_raw = load_and_clean_data(KPI_URL)
dsat_raw = load_and_clean_data(DSAT_URL)

# Process KPI data using standardized columns
if not kpi_raw.empty:
    # Use .get() to avoid KeyError if columns are missing
    kpi_raw['IA_Mins'] = kpi_raw['IA'].apply(parse_time) if 'IA' in kpi_raw.columns else 0
    # The fix for your specific KeyError:
    call_col = 'Advisor Call Time' if 'Advisor Call Time' in kpi_raw.columns else 'Advisor Call Time '
    kpi_raw['Call_Mins'] = kpi_raw[call_col].apply(parse_time) if call_col in kpi_raw.columns else 0
    
    kpi_raw['Shift_Score'] = np.where(kpi_raw['IA_Mins'] > 0, (kpi_raw['Call_Mins'] / kpi_raw['IA_Mins'] * 100), 0)
    kpi_raw['Date_Parsed'] = pd.to_datetime(kpi_raw['Date_level - AS'], format="%b'%d'%y", errors='coerce')
    
    for col in ['Sent Rate %', 'Satisfied Survey %', 'Q/A Calls', 'OB Calls']:
        if col in kpi_raw.columns:
            kpi_raw[col] = pd.to_numeric(kpi_raw[col], errors='coerce').fillna(0)

# --- 6. DYNAMIC HIERARCHY ---
st.sidebar.title("Navigation")
level = str(user.get('Access level', 'IC')).strip()
emails = []

if level == "Admin":
    directors = team_db[team_db['Advisor Name'].isin(team_db['Manager'].unique())]['Manager'].unique()
    dir_sel = st.sidebar.selectbox("Director View", ["Entire Org"] + list(directors))
    if dir_sel == "Entire Org":
        emails = team_db['Email'].unique()
    else:
        mgrs = team_db[team_db['Manager'] == dir_sel]['Advisor Name'].unique()
        mgr_sel = st.sidebar.selectbox("Manager Team", ["All Teams"] + list(mgrs))
        if mgr_sel == "All Teams":
            emails = team_db[team_db['Manager'] == dir_sel]['Email'].unique()
        else:
            advs = team_db[team_db['Manager'] == mgr_sel]['Advisor Name'].unique()
            adv_sel = st.sidebar.selectbox("Advisor", ["Full Team"] + list(advs))
            if adv_sel == "Full Team":
                emails = team_db[team_db['Manager'] == mgr_sel]['Email'].unique()
            else:
                emails = team_db[team_db['Advisor Name'] == adv_sel]['Email'].unique()

elif level == "Manager":
    my_team = team_db[team_db['Manager'] == user['Advisor Name']]['Advisor Name'].unique()
    adv_sel = st.sidebar.selectbox("Team Drill-down", ["Full Team"] + list(my_team))
    if adv_sel == "Full Team":
        emails = team_db[team_db['Manager'] == user['Advisor Name']]['Email'].unique()
    else:
        emails = team_db[team_db['Advisor Name'] == adv_sel]['Email'].unique()
else:
    emails = [user['Email']]

f_kpi = kpi_raw[kpi_raw['Email'].isin(emails)]
f_dsat = dsat_raw[dsat_raw['Advisor Email'].isin(emails)]

# --- 7. TABS ---
st.title("🚀 PERFORMANCE HUB")
tabs = st.tabs(["Performance Overview", "DSAT Analysis", "Leaderboards"])

with tabs[0]:
    if not f_kpi.empty:
        avg_score = f_kpi['Shift_Score'].mean()
        # Scale to 100 if stored as 0.85
        avg_sent = f_kpi[f_kpi['Total Survey'] > 0]['Sent Rate %'].mean()
        if avg_sent <= 1: avg_sent *= 100
        avg_sat = f_kpi[f_kpi['Total Survey'] > 0]['Satisfied Survey %'].mean()
        if avg_sat <= 1: avg_sat *= 100
        
        g1, g2, g3 = st.columns(3)
        g1.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_score, 85, color_steps=True), use_container_width=True)
        g2.plotly_chart(create_ghl_gauge("Avg Sent Rate %", avg_sent, 85, color_steps=True), use_container_width=True)
        g3.plotly_chart(create_ghl_gauge("Avg Satisfied %", avg_sat, 90, color_steps=True), use_container_width=True)

        st.markdown("### 📈 Trend Analysis")
        trend = f_kpi.groupby('Date_Parsed').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'}).reset_index()
        tc1, tc2 = st.columns(2)
        with tc1:
            st.plotly_chart(px.line(trend, x='Date_Parsed', y='Sent Rate %', title="Survey Sent Trend"), use_container_width=True)
            st.plotly_chart(px.line(trend, x='Date_Parsed', y='Q/A Calls', title="Total QA Calls Trend"), use_container_width=True)
        with tc2:
            st.plotly_chart(px.line(trend, x='Date_Parsed', y='Satisfied Survey %', title="Satisfied Survey Trend"), use_container_width=True)
            st.plotly_chart(px.line(trend, x='Date_Parsed', y='OB Calls', title="Total OB Calls Trend"), use_container_width=True)

with tabs[1]:
    st.markdown("### 🚫 DSAT Analysis")
    pending = len(f_dsat[f_dsat['Feedback'].isna() | (f_dsat['Feedback'] == "")])
    st.metric("Feedback Pending", pending, delta_color="inverse")
    st.dataframe(f_dsat, hide_index=True)

with tabs[2]:
    if not f_kpi.empty:
        ldb = f_kpi.groupby('Agent Name').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'OB Calls':'sum'}).reset_index().round(2)
        st.dataframe(ldb.sort_values('Satisfied Survey %', ascending=False), hide_index=True)

st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
