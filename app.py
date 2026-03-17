import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
import re
from streamlit.components.v1 import iframe

# --- 1. CONFIGURATION & URLS ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

# FORM CONFIG
FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub")

# --- 2. GHL DYNAMIC THEME ---
st.markdown("""
    <style>
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 160px; height: 60px; margin-left: 20px; margin-top: 20px; filter: invert(1) brightness(2);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; }
    div.stInfo { background-color: rgba(0, 82, 255, 0.08); border-left: 5px solid #0052FF; color: var(--text-color); border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA LOADER ---
def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    try:
        parts = str(time_str).lower().split()
        for p in parts:
            if 'h' in p: h = int(p.replace('h', ''))
            elif 'm' in p: m = int(p.replace('m', ''))
        return (h * 60) + m
    except: return 0

@st.cache_data(ttl=60)
def load_and_standardize(url, sheet_type):
    try:
        df = pd.read_csv(url)
        # Clean Headers: Strip, lowercase, and underscores
        df.columns = [re.sub(r'\s+', '_', str(c).strip().replace('\ufeff', '').replace('"', '')).lower() for c in df.columns]
        
        # Internal Field Mapping
        rmap = {
            "advisor_name": "advisor_name", "agent_name": "advisor_name",
            "advisor_email": "email", "email": "email",
            "access_level": "access_level", "password": "password",
            "ia": "ia_time", "advisor_call_time": "call_time",
            "q/a_calls": "qa_calls", "ob_calls": "ob_calls",
            "chat_dsat_url": "chat_url", "timestamp": "timestamp"
        }
        df = df.rename(columns=rmap)
        
        if 'email' in df.columns:
            df['email'] = df['email'].astype(str).str.strip().str.lower()
        
        # FIXED: Robust Numeric Conversion for KPI metrics
        if sheet_type == "KPI":
            metric_cols = ['sent_rate_%', 'satisfied_survey_%', 'qa_calls', 'ob_calls', 'total_survey']
            for col in metric_cols:
                if col in df.columns:
                    # Remove '%' symbols if any and convert to numeric, turning errors into 0
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
            
            df['ia_mins'] = df['ia_time'].apply(parse_time) if 'ia_time' in df.columns else 0
            df['call_mins'] = df['call_time'].apply(parse_time) if 'call_time' in df.columns else 0
            df['shift_score'] = np.where(df['ia_mins'] > 0, (df['call_mins']/df['ia_mins']*100), 0)
            
            date_col = 'date_level_-_as'
            if date_col in df.columns:
                df['date_parsed'] = pd.to_datetime(df[date_col], format="%b'%d'%y", errors='coerce')
        return df
    except Exception as e:
        st.error(f"Loader Error: {e}")
        return pd.DataFrame()

def create_ghl_gauge(title, value, target=None):
    steps = [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}]
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number = {'suffix': "%", 'font': {'color': '#0052FF', 'size': 35}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"}, 'bgcolor': "white", 'steps': steps,
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target} if target else None}
    ))
    fig.update_layout(height=220, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update DSAT Record", width="large")
def open_form_dialog(row):
    params = {ENTRY_KEY: row.get('recordkey',''), ENTRY_FEEDBACK: row.get('feedback',''), ENTRY_TYPE: row.get('type','')}
    url = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url&{urllib.parse.urlencode(params)}"
    iframe(url, height=700, scrolling=True)
    if st.button("Close & Sync"): st.rerun()

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_standardize(TEAM_URL, "TEAM")

if not st.session_state.auth:
    col_l1, col_l2 = st.columns([1, 4])
    with col_l1: st.image(LOGO_URL, width=150)
    with col_l2: st.title("Implementation Team Performance Hub")
    with st.form("login"):
        user_email = st.text_input("Work Email").lower().strip()
        user_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['email'] == user_email) & (team_db['password'].astype(str) == str(user_pass))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. DATA FETCHING ---
user = st.session_state.auth
kpi_raw = load_and_standardize(KPI_URL, "KPI")
dsat_raw = load_and_standardize(DSAT_URL, "DSAT")

# --- 6. NAVIGATION & DRILL-DOWN ---
st.sidebar.title("Navigation")
freq = st.sidebar.selectbox("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"])
access = str(user.get('access_level', 'IC')).strip()
emails_to_filter = []

if access == "Admin":
    directors = team_db[team_db['advisor_name'].isin(team_db['manager'].unique())]['manager'].unique()
    view_mode = st.sidebar.selectbox("View Mode", ["Entire Organisation"] + list(directors))
    if view_mode == "Entire Organisation":
        emails_to_filter = team_db['email'].unique()
    else:
        mgrs = team_db[team_db['manager'] == view_mode]['advisor_name'].unique()
        mgr_sel = st.sidebar.selectbox("Select Manager", ["All Teams"] + list(mgrs))
        if mgr_sel == "All Teams":
            emails_to_filter = team_db[team_db['manager'].isin(mgrs)]['email'].unique()
        else:
            advs = team_db[team_db['manager'] == mgr_sel]['advisor_name'].unique()
            adv_sel = st.sidebar.selectbox("Select Advisor", ["Full Team"] + list(advs))
            emails_to_filter = [team_db[team_db['advisor_name'] == adv_sel]['email'].values[0]] if adv_sel != "Full Team" else team_db[team_db['manager'] == mgr_sel]['email'].unique()

elif access == "Manager":
    view_mode = st.sidebar.selectbox("View Mode", ["Team Overview", "Specific Advisor View"])
    if view_mode == "Team Overview":
        emails_to_filter = team_db[team_db['manager'] == user['advisor_name']]['email'].unique()
    else:
        advs = team_db[team_db['manager'] == user['advisor_name']]['advisor_name'].unique()
        adv_sel = st.sidebar.selectbox("Select Advisor", list(advs))
        emails_to_filter = [team_db[team_db['advisor_name'] == adv_sel]['email'].values[0]]

else: # IC Level
    emails_to_filter = [user['email']]

f_kpi = kpi_raw[kpi_raw['email'].isin(emails_to_filter)]
f_dsat = dsat_raw[dsat_raw['email'].isin(emails_to_filter)]

# --- 7. UI ---
st.title("Implementation Team Performance Hub")
st.success(f"Welcome {user['advisor_name']}!!, Access Level : {access}")

tabs_list = ["Performance Overview", "DSAT Analysis"]
if access != "IC": tabs_list.append("Leaderboard")
tabs = st.tabs(tabs_list)

with tabs[0]:
    st.markdown("### Performance Narrative")
    avg_score = f_kpi['shift_score'].mean() if not f_kpi.empty else 0
    st.info(f"The group is currently maintaining a Shift Score of {avg_score:.2f}%. Monitoring shows consistent engagement in daily operations.")
    
    st.markdown("### Performance Summary")
    g1, g2, g3 = st.columns(3)
    # Scale percentages: if values are decimals (0.85), multiply by 100. If they are already whole numbers (85.0), keep as is.
    raw_avg_sent = f_kpi[f_kpi['total_survey'] > 0]['sent_rate_%'].mean() if not f_kpi.empty else 0
    avg_sent = (raw_avg_sent * 100) if raw_avg_sent <= 1 else raw_avg_sent
    
    raw_avg_sat = f_kpi[f_kpi['total_survey'] > 0]['satisfied_survey_%'].mean() if not f_kpi.empty else 0
    avg_sat = (raw_avg_sat * 100) if raw_avg_sat <= 1 else raw_avg_sat
    
    g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
    g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
    g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_score, 85), use_container_width=True)
    
    n1, n2 = st.columns(2)
    n1.metric("Total OB Calls", int(f_kpi['ob_calls'].sum()) if not f_kpi.empty else 0)
    n2.metric("Total OH Calls (QA)", int(f_kpi['qa_calls'].sum()) if not f_kpi.empty else 0)

    st.markdown("### Performance Trends")
    if not f_kpi.empty:
        trend = f_kpi.groupby('date_parsed').agg({'sent_rate_%':'mean', 'satisfied_survey_%':'mean', 'shift_score':'mean', 'ob_calls':'sum', 'qa_calls':'sum'}).reset_index()
        tc1, tc2 = st.columns(2)
        with tc1:
            st.plotly_chart(px.line(trend, x='date_parsed', y=['sent_rate_%', 'satisfied_survey_%'], title="Survey Trends"), use_container_width=True)
        with tc2:
            st.plotly_chart(px.line(trend, x='date_parsed', y='shift_score', title="Shift Score Trend"), use_container_width=True)

with tabs[1]:
    st.markdown("### DSAT Summary")
    pending = len(f_dsat[f_dsat['feedback'].isna() | (f_dsat['feedback'] == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", len(f_dsat))
    s2.metric("Feedback Pending", pending)
    s3.metric("Controllable", len(f_dsat[f_dsat['type'] == 'Controllable']))
    s4.metric("Uncontrollable", len(f_dsat[f_dsat['type'] == 'Uncontrollable']))

    st.markdown("### DSAT Details")
    if not f_dsat.empty:
        col_w = [1.5, 2.5, 1.5, 3] + ([1] if access != "IC" else [])
        for idx, row in f_dsat.reset_index().iterrows():
            r = st.columns(col_w)
            r[0].write(str(row['timestamp'])[:10]); r[1].markdown(f"[Chat Link]({row['chat_url']})")
            r[2].write(row['type']); r[3].write(row['feedback'] if pd.notna(row['feedback']) else "-")
            if access != "IC":
                if r[4].button("Update", key=f"upd_{idx}"): open_form_dialog(row)

if access != "IC":
    with tabs[2]:
        st.markdown("### 🏆 Leaderboards")
        if not f_kpi.empty:
            ldb = f_kpi.groupby('advisor_name').agg({'sent_rate_%':'mean', 'satisfied_survey_%':'mean', 'qa_calls':'sum', 'ob_calls':'sum'}).reset_index()
            # Normalize for leaderboard display
            ldb['sent_rate_%'] = ldb['sent_rate_%'].apply(lambda x: x*100 if x <= 1 else x)
            ldb['satisfied_survey_%'] = ldb['satisfied_survey_%'].apply(lambda x: x*100 if x <= 1 else x)
            st.dataframe(ldb.sort_values('satisfied_survey_%', ascending=False), hide_index=True, use_container_width=True)

st.sidebar.divider()
if st.sidebar.button("Logout"): st.session_state.auth = None; st.rerun()
