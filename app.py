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

# PRE-FILLED FORM CONFIG
FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="HighLevel Performance Hub", page_icon="🚀")

# --- 2. SaaS/GHL THEME ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    .stMetric { background-color: var(--secondary-background-color); padding: 24px; border-radius: 16px; border: 1px solid rgba(0, 82, 255, 0.1); }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat; width: 180px; height: 60px; 
        margin-left: 20px; margin-top: 20px; filter: brightness(0) invert(1);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA PROCESSING ---
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
        df.columns = [re.sub(r'\s+', '_', str(c).strip().replace('\ufeff', '').replace('"', '')).lower() for c in df.columns]
        
        rmap = {
            "advisor_name": "name", "agent_name": "name",
            "advisor_email": "email", "email": "email",
            "manager": "mgr", "manager_name": "mgr",
            "access_level": "level", "password": "pass",
            "ia": "ia_raw", "advisor_call_time": "call_raw",
            "sent_rate_%": "sent_rate", "satisfied_survey_%": "sat_rate",
            "ob_calls": "ob", "q/a_calls": "qa", "total_survey": "surveys",
            "timestamp": "ts", "chat_dsat_url": "link"
        }
        df = df.rename(columns=rmap)
        if 'email' in df.columns: df['email'] = df['email'].astype(str).str.strip().str.lower()
        
        if sheet_type == "KPI":
            for col in ['sent_rate', 'sat_rate', 'qa', 'ob', 'surveys']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
            
            df['ia_min'] = df['ia_raw'].apply(parse_time) if 'ia_raw' in df.columns else 0
            df['call_min'] = df['call_raw'].apply(parse_duration) if 'call_raw' in df.columns else 0 # Fixed duration calc
            df['shift_score'] = np.where(df['ia_min'] > 0, (df['call_min']/df['ia_min']*100), 0)
            if 'date_level_-_as' in df.columns:
                df['date_parsed'] = pd.to_datetime(df['date_level_-_as'], format="%b'%d'%y", errors='coerce')
        
        if sheet_type == "DSAT":
            df['date_parsed'] = pd.to_datetime(df['ts'], errors='coerce')
            
        return df
    except Exception as e:
        return pd.DataFrame()

def create_ghl_gauge(title, value, target=None):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = round(value, 2), domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number = {'suffix': "%", 'font': {'color': '#0052FF', 'size': 36}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"},
                 'steps': [{'range': [0, 70], 'color': "#FFEDEB"}, {'range': [70, 85], 'color': "#FFF9E6"}, {'range': [85, 100], 'color': "#E6F9ED"}],
                 'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': target} if target else None}
    ))
    fig.update_layout(height=230, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_standardize(TEAM_URL, "TEAM")

if not st.session_state.auth:
    st.title("Performance Hub Login")
    with st.form("login"):
        u_email = st.text_input("Work Email").lower().strip()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['email'] == u_email) & (team_db['pass'].astype(str) == str(u_pass))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. GLOBAL FILTERS ---
user = st.session_state.auth
kpi_raw = load_and_standardize(KPI_URL, "KPI")
dsat_raw = load_and_standardize(DSAT_URL, "DSAT")

st.sidebar.title("Configuration")
freq_mode = st.sidebar.radio("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

if freq_mode == "Daily":
    available = sorted(kpi_raw['date_parsed'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Date", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    kpi_f, dsat_f = kpi_raw[kpi_raw['date_parsed'] == sel], dsat_raw[dsat_raw['date_parsed'].dt.date == sel.date()]
elif freq_mode == "Weekly":
    kpi_raw['week_start'] = kpi_raw['date_parsed'].dt.to_period('W').apply(lambda r: r.start_time)
    available = sorted(kpi_raw['week_start'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Week Starting", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    kpi_f, dsat_f = kpi_raw[kpi_raw['week_start'] == sel], dsat_raw[(dsat_raw['date_parsed'] >= sel) & (dsat_raw['date_parsed'] < sel + pd.Timedelta(days=7))]
else:
    kpi_raw['period'] = kpi_raw['date_parsed'].dt.strftime('%B %Y') if freq_mode == "Monthly" else kpi_raw['date_parsed'].dt.year
    available = kpi_raw.sort_values('date_parsed', ascending=False)['period'].unique()
    sel = st.sidebar.selectbox(f"Select Period", available)
    kpi_f = kpi_raw[kpi_raw['period'] == sel]
    dsat_f = dsat_raw[dsat_raw['date_parsed'].dt.strftime('%B %Y') == sel] if freq_mode == "Monthly" else dsat_raw[dsat_raw['date_parsed'].dt.year == sel]

# --- 6. HIERARCHY SCOPING ---
access = str(user.get('level', 'IC')).strip()
emails = []

if access == "Admin":
    view_mode = st.sidebar.selectbox("Hierarchy", ["Entire Organisation", "Jarvis Sokolowich", "Sumit Ludhwani"])
    if view_mode == "Entire Organisation":
        emails = team_db['email'].unique()
    else:
        mgrs = team_db[team_db['mgr'] == view_mode]['name'].unique()
        mgr_sel = st.sidebar.selectbox(f"Managers under {view_mode}", ["All Teams"] + list(mgrs))
        if mgr_sel == "All Teams":
            emails = team_db[team_db['mgr'] == view_mode]['email'].unique()
        else:
            advs = team_db[team_db['mgr'] == mgr_sel]['name'].unique()
            adv_sel = st.sidebar.selectbox(f"Advisors under {mgr_sel}", ["Full Team"] + list(advs))
            emails = [team_db[team_db['name'] == adv_sel]['email'].values[0]] if adv_sel != "Full Team" else team_db[team_db['mgr'] == mgr_sel]['email'].unique()
elif access == "Manager":
    view_mode = st.sidebar.selectbox("Team View", ["Team Overview", "Specific Advisor"])
    my_advs = team_db[team_db['mgr'] == user['name']]
    if view_mode == "Team Overview":
        emails = my_advs['email'].unique()
    else:
        adv_sel = st.sidebar.selectbox("Select Advisor", list(my_advs['name'].unique()))
        emails = [my_advs[my_advs['name'] == adv_sel]['email'].values[0]]
else:
    emails = [user['email']]

f_kpi = kpi_f[kpi_f['email'].isin(emails)]
f_dsat = dsat_f[dsat_f['email'].isin(emails)]

# --- 7. UI CONTENT ---
st.title("Performance Hub Dashboard")
st.markdown(f"**Welcome {user['name']}!** | Access Level: `{access}`")

tab1, tab2 = st.tabs(["Performance Overview", "DSAT Analysis"])

with tab1:
    if not f_kpi.empty:
        st.markdown("### Performance Summary")
        g1, g2, g3 = st.columns(3)
        
        # Scaling Percentage Fix (0.85 -> 85.00)
        raw_sent = f_kpi[f_kpi['surveys'] > 0]['sent_rate'].mean() if not f_kpi.empty else 0
        avg_sent = raw_sent * 100 if raw_sent <= 1 else raw_sent
        
        raw_sat = f_kpi[f_kpi['surveys'] > 0]['sat_rate'].mean() if not f_kpi.empty else 0
        avg_sat = raw_sat * 100 if raw_sat <= 1 else raw_sat
        
        avg_shift = f_kpi['shift_score'].mean() if not f_kpi.empty else 0
        
        g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
        g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
        g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_shift, 85), use_container_width=True)
        
        m1, m2 = st.columns(2)
        m1.metric("Total OB Calls", f"{int(f_kpi['ob'].sum()):,}")
        m2.metric("Total OH Calls (QA)", f"{int(f_kpi['qa'].sum()):,}")

with tab2:
    st.markdown("### DSAT Summary")
    # FEEDBACK PENDING: Blank or "-"
    pending = len(f_dsat[f_dsat['feedback'].isna() | (f_dsat['feedback'].isin(["", "-"]))])
    
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSATs", f"{len(f_dsat)}")
    s2.metric("Controllable", f"{len(f_dsat[f_dsat['type'] == 'Controllable'])}")
    s3.metric("Uncontrollable", f"{len(f_dsat[f_dsat['type'] == 'Uncontrollable'])}")
    s4.metric("Feedback Pending", f"{pending}")
    
    st.dataframe(f_dsat[['ts', 'link', 'type', 'feedback']].fillna("-"), hide_index=True, use_container_width=True)

st.sidebar.divider()
if st.sidebar.button("Logout"): 
    st.session_state.auth = None
    st.rerun()
