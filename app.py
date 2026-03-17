import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
import re
from streamlit.components.v1 import iframe

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub")

# --- 2. GHL DYNAMIC THEME ---
st.markdown("""
    <style>
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat; width: 180px; height: 60px; margin-left: 20px; margin-top: 20px; filter: invert(1) brightness(2);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA LOADER ---
def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    try:
        parts = str(time_str).lower().split()
        for p in parts:
            if 'h' in p: h = int(re.sub(r'\D', '', p))
            elif 'm' in p: m = int(re.sub(r'\D', '', p))
        return (h * 60) + m
    except: return 0

@st.cache_data(ttl=60)
def load_and_standardize(url, sheet_type):
    try:
        df = pd.read_csv(url)
        # Clean Headers: Strip, lowercase, and convert ALL whitespace to underscores
        df.columns = [re.sub(r'\s+', '_', str(c).strip().replace('\ufeff', '').replace('"', '')).lower() for c in df.columns]
        
        # Internal Field Mapping
        rmap = {
            "advisor_name": "advisor_name", "agent_name": "advisor_name",
            "advisor_email": "email", "email": "email",
            "manager_name": "manager_name", "manager": "manager_name",
            "ia": "ia_time", "advisor_call_time": "call_time",
            "q/a_calls": "qa_calls", "ob_calls": "ob_calls"
        }
        df = df.rename(columns=rmap)
        
        if 'email' in df.columns:
            df['email'] = df['email'].astype(str).str.strip().str.lower()
        
        if sheet_type == "KPI":
            # Force numeric conversion for math
            for col in ['sent_rate_%', 'satisfied_survey_%', 'qa_calls', 'ob_calls', 'total_survey']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
            
            df['ia_mins'] = df['ia_time'].apply(parse_time) if 'ia_time' in df.columns else 0
            df['call_mins'] = df['call_time'].apply(parse_time) if 'call_time' in df.columns else 0
            df['shift_score'] = np.where(df['ia_mins'] > 0, (df['call_mins']/df['ia_mins']*100), 0)
            
            date_col = 'date_level_-_as'
            if date_col in df.columns:
                df['date_parsed'] = pd.to_datetime(df[date_col], format="%b'%d'%y", errors='coerce')
        
        if sheet_type == "DSAT":
            if 'timestamp' in df.columns:
                df['date_parsed'] = pd.to_datetime(df['timestamp'], errors='coerce')
            if 'processed' in df.columns:
                # Keep duplicates if they still have pending feedback
                df = df[df['processed'] != 'DUPLICATE']

        return df
    except: return pd.DataFrame()

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_standardize(TEAM_URL, "TEAM")

if not st.session_state.auth:
    col1, col2 = st.columns([1, 4])
    with col1: st.image(LOGO_URL, width=150)
    with col2: st.title("Performance Hub Login")
    with st.form("login"):
        u_email = st.text_input("Work Email").lower().strip()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['email'] == u_email) & (team_db['password'].astype(str) == str(u_pass))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. DATA FETCHING ---
user = st.session_state.auth
kpi_raw = load_and_standardize(KPI_URL, "KPI")
dsat_raw = load_and_standardize(DSAT_URL, "DSAT")

# --- 6. NAVIGATION & FILTERING (FIXED CASING) ---
st.sidebar.title("Navigation")
freq = st.sidebar.radio("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

# Select Period (Controls Entire App)
if not kpi_raw.empty:
    if freq == "Daily":
        available = sorted(kpi_raw['date_parsed'].dropna().unique(), reverse=True)
        sel_date = st.sidebar.selectbox("Select Date", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
        kpi_f = kpi_raw[kpi_raw['date_parsed'] == sel_date]
        dsat_f = dsat_raw[dsat_raw['date_parsed'].dt.date == sel_date.date()]
    elif freq == "Weekly":
        kpi_raw['week_start'] = kpi_raw['date_parsed'].dt.to_period('W').apply(lambda r: r.start_time)
        available = sorted(kpi_raw['week_start'].dropna().unique(), reverse=True)
        sel_date = st.sidebar.selectbox("Select Week Starting", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
        kpi_f = kpi_raw[kpi_raw['week_start'] == sel_date]
        dsat_f = dsat_raw[(dsat_raw['date_parsed'] >= sel_date) & (dsat_raw['date_parsed'] < sel_date + pd.Timedelta(days=7))]
    else: # Monthly/Yearly
        kpi_raw['month_label'] = kpi_raw['date_parsed'].dt.strftime('%B %Y')
        available = kpi_raw.sort_values('date_parsed', ascending=False)['month_label'].unique()
        sel_date = st.sidebar.selectbox("Select Period", available)
        kpi_f = kpi_raw[kpi_raw['month_label'] == sel_date]
        dsat_f = dsat_raw[dsat_raw['date_parsed'].dt.strftime('%B %Y') == sel_date]
else:
    kpi_f, dsat_f = pd.DataFrame(), pd.DataFrame()

# Hierarchy Scoping
access = str(user.get('access_level', 'IC')).strip()
emails = []

if access == "Admin":
    mode = st.sidebar.selectbox("View Mode", ["Entire Organisation", "Jarvis Sokolowich", "Sumit Ludhwani"])
    if mode == "Entire Organisation": emails = team_db['email'].unique()
    else:
        mgrs = team_db[team_db['manager_name'] == mode]['advisor_name'].unique()
        mgr_sel = st.sidebar.selectbox(f"Managers under {mode}", ["All Teams"] + list(mgrs))
        if mgr_sel == "All Teams": emails = team_db[team_db['manager_name'] == mode]['email'].unique()
        else:
            advs = team_db[team_db['manager_name'] == mgr_sel]['advisor_name'].unique()
            adv_sel = st.sidebar.selectbox(f"Advisors under {mgr_sel}", ["Full Team"] + list(advs))
            emails = [team_db[team_db['advisor_name'] == adv_sel]['email'].values[0]] if adv_sel != "Full Team" else team_db[team_db['manager_name'] == mgr_sel]['email'].unique()

elif access == "Manager":
    # Managers (like Jitendra Kumar) see their team defined in Team_Detail
    my_team = team_db[team_db['manager_name'] == user['advisor_name']]
    mode = st.sidebar.selectbox("View Mode", ["Team Overview", "Individual Advisor View"])
    if mode == "Team Overview": emails = my_team['email'].unique()
    else:
        adv_sel = st.sidebar.selectbox("Select Advisor", list(my_team['advisor_name'].unique()))
        emails = [my_team[my_team['advisor_name'] == adv_sel]['email'].values[0]]
else:
    emails = [user['email']]

f_kpi = kpi_f[kpi_f['email'].isin(emails)]
f_dsat = dsat_f[dsat_f['email'].isin(emails)]

# --- 7. UI TABS & DSAT SUMMARY ---
st.title("Implementation Team Performance Hub")
st.info(f"Welcome **{user['advisor_name']}**!!, Access Level : **{access}**")

tab1, tab2 = st.tabs(["Performance Overview", "DSAT Analysis"])

with tab1:
    if not f_kpi.empty:
        avg_score = f_kpi['shift_score'].mean()
        st.metric("Avg Shift Score", f"{avg_score:.2f}%")
        st.plotly_chart(px.line(f_kpi.sort_values('date_parsed'), x='date_parsed', y='shift_score', title="Trend"), use_container_width=True)

with tab2:
    st.markdown("### DSAT Analysis")
    # DSAT Summary Metric Cards
    pending = len(f_dsat[f_dsat['feedback'].isna() | (f_dsat['feedback'] == "")])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total DSATs", len(f_dsat))
    c2.metric("Pending Feedback", pending)
    c3.metric("Controllable", len(f_dsat[f_dsat['type'] == 'Controllable']))
    c4.metric("Uncontrollable", len(f_dsat[f_dsat['type'] == 'Uncontrollable']))
    
    # DSAT Detail Table
    if not f_dsat.empty:
        # Re-merge to get Names correctly in the audit table
        table_data = f_dsat.merge(team_db[['email', 'advisor_name', 'manager_name']], on='email', how='left')
        st.dataframe(table_data[['date_parsed', 'advisor_name', 'manager_name', 'chat_url', 'type', 'feedback']].fillna("-"), hide_index=True)
