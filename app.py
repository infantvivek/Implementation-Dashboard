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

# --- 2. THEME & SETTINGS ---
st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

st.markdown("""
    <style>
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat; width: 160px; height: 50px; 
        margin-left: 20px; margin-top: 20px; filter: invert(1) brightness(2);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA LOADER ---
@st.cache_data(ttl=60)
def load_data(url, sheet_type):
    try:
        df = pd.read_csv(url)
        # 1. Clean headers: Strip spaces, remove BOM, handle quotes
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '')
        
        # 2. Strict Standardized Mapping
        mapping = {
            "Advisor Name": "advisor_name", "Agent Name": "advisor_name",
            "Email": "email", "Advisor Email": "email",
            "Manager": "manager_name", "Access level": "access_level",
            "Password": "password", "IA": "ia_time",
            "Advisor Call Time ": "call_time", "Advisor Call Time": "call_time"
        }
        df = df.rename(columns=mapping)
        
        # 3. Standardize email formats
        if 'email' in df.columns:
            df['email'] = df['email'].astype(str).str.strip().str.lower()
        return df
    except Exception as e:
        st.error(f"Loader Error ({sheet_type}): {e}")
        return pd.DataFrame()

def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    parts = str(time_str).lower().split()
    for p in parts:
        if 'h' in p: h = int(p.replace('h', ''))
        elif 'm' in p: m = int(p.replace('m', ''))
    return (h * 60) + m

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_data(TEAM_URL, "TEAM")

if not st.session_state.auth:
    col1, col2 = st.columns([1, 4])
    with col1: st.image(LOGO_URL, width=150)
    with col2: st.title("HIGHLEVEL PERFORMANCE HUB")
    with st.form("login"):
        user_email = st.text_input("Work Email").lower().strip()
        user_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['email'] == user_email) & (team_db['password'].astype(str) == str(user_pass))]
            if not match.empty:
                # Store user data with lowercased standard keys
                st.session_state.auth = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. DATA PREP ---
user = st.session_state.auth
kpi_raw = load_data(KPI_URL, "KPI")
dsat_raw = load_data(DSAT_URL, "DSAT")

# Calculations for KPI
if not kpi_raw.empty:
    kpi_raw['ia_mins'] = kpi_raw['ia_time'].apply(parse_time) if 'ia_time' in kpi_raw.columns else 0
    kpi_raw['call_mins'] = kpi_raw['call_time'].apply(parse_time) if 'call_time' in kpi_raw.columns else 0
    kpi_raw['Shift_Score'] = np.where(kpi_raw['ia_mins'] > 0, (kpi_raw['call_mins']/kpi_raw['ia_mins']*100), 0)
    kpi_raw['Date_Parsed'] = pd.to_datetime(kpi_raw['Date_level - AS'], format="%b'%d'%y", errors='coerce')

# --- 6. DYNAMIC DRILL-DOWN LOGIC ---
st.sidebar.title("Navigation")
access = str(user.get('access_level', 'IC')).strip()
emails_to_filter = []

if access == "Admin":
    # Identify Directors (Those who manage Managers)
    directors = team_db[team_db['advisor_name'].isin(team_db['manager_name'].unique())]['manager_name'].unique()
    dir_sel = st.sidebar.selectbox("Director Overview", ["Entire Org"] + list(directors))
    
    if dir_sel == "Entire Org":
        emails_to_filter = team_db['email'].unique()
    else:
        mgrs = team_db[team_db['manager_name'] == dir_sel]['advisor_name'].unique()
        mgr_sel = st.sidebar.selectbox("Manager Team", ["All Teams"] + list(mgrs))
        if mgr_sel == "All Teams":
            emails_to_filter = team_db[team_db['manager_name'].isin(mgrs)]['email'].unique()
        else:
            advs = team_db[team_db['manager_name'] == mgr_sel]['advisor_name'].unique()
            adv_sel = st.sidebar.selectbox("Advisor", ["Full Team"] + list(advs))
            if adv_sel == "Full Team":
                emails_to_filter = team_db[team_db['manager_name'] == mgr_sel]['email'].unique()
            else:
                emails_to_filter = team_db[team_db['advisor_name'] == adv_sel]['email'].unique()

elif access == "Manager":
    my_team = team_db[team_db['manager_name'] == user['advisor_name']]['advisor_name'].unique()
    adv_sel = st.sidebar.selectbox("Team Drill-down", ["Full Team"] + list(my_team))
    if adv_sel == "Full Team":
        emails_to_filter = team_db[team_db['manager_name'] == user['advisor_name']]['email'].unique()
    else:
        emails_to_filter = team_db[team_db['advisor_name'] == adv_sel]['email'].unique()

else: # IC
    # Error fix: Use the standard 'email' key generated during login
    emails_to_filter = [user['email']]

# Final Filter
f_kpi = kpi_raw[kpi_raw['email'].isin(emails_to_filter)]
f_dsat = dsat_raw[dsat_raw['email'].isin(emails_to_filter)]

# --- 7. UI TABS ---
st.title(f"🚀 {user['advisor_name']}'s Dashboard")
tabs = st.tabs(["📊 Performance Overview", "🚫 DSAT Analysis", "🏆 Leaderboards"])

with tabs[0]:
    if not f_kpi.empty:
        avg_shift = f_kpi['Shift_Score'].mean()
        st.metric("Avg Shift Score", f"{avg_shift:.2f}%")
        st.plotly_chart(px.line(f_kpi.sort_values('Date_Parsed'), x='Date_Parsed', y='Shift_Score', title="Shift Score Trend"), use_container_width=True)
    else:
        st.info("No KPI data found for the current selection.")

with tabs[1]:
    st.markdown("### DSAT Audit")
    if not f_dsat.empty:
        st.dataframe(f_dsat, hide_index=True, use_container_width=True)
    else:
        st.info("No DSAT data found.")

with tabs[2]:
    if access in ["Admin", "Manager"]:
        ldb = f_kpi.groupby('advisor_name')['Shift_Score'].mean().reset_index().sort_values('Shift_Score', ascending=False)
        st.dataframe(ldb.round(2), hide_index=True)

st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
    
