import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
from streamlit.components.v1 import iframe

# --- 1. CONFIGURATION ---
# Using CSV export links from your repository structure
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

# --- 2. GHL THEME & SIDEBAR LOGO ---
st.markdown("""
    <style>
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 160px; height: 50px; margin-left: 20px; margin-top: 20px; filter: invert(1) brightness(2);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA LOADING ---
def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    parts = str(time_str).lower().split()
    for p in parts:
        if 'h' in p: h = int(p.replace('h', ''))
        elif 'm' in p: m = int(p.replace('m', ''))
    return (h * 60) + m

@st.cache_data(ttl=60)
def load_data(url):
    try:
        df = pd.read_csv(url)
        # Clean BOM, spaces, and lowercase headers
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '').str.lower()
        
        # Standardize crucial column names internally
        rename_map = {
            "advisor name": "advisor_name", "agent name": "advisor_name",
            "manager": "manager_name", "manager name": "manager_name",
            "access level": "access_level", "advisor email": "email",
            "call abandons ": "call_abandons", "ia": "ia_time"
        }
        df = df.rename(columns=rename_map)
        
        if 'email' in df.columns:
            df['email'] = df['email'].astype(str).str.strip().str.lower()
        return df
    except:
        return pd.DataFrame()

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_data(TEAM_URL)

if not st.session_state.auth:
    col_l1, col_l2 = st.columns([1, 3])
    with col_l1: st.image(LOGO_URL, width=150)
    with col_l2: st.title("HIGHLEVEL PERFORMANCE HUB")
    with st.form("login"):
        e_in = st.text_input("Work Email").lower().strip()
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            # Use 'email' and 'password' (lowercased by loader)
            user_match = team_db[(team_db['email'] == e_in) & (team_db['password'].astype(str).str.strip() == str(p_in).strip())]
            if not user_match.empty:
                st.session_state.auth = user_match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. DATA FETCHING ---
user = st.session_state.auth
kpi_raw = load_data(KPI_URL)
dsat_raw = load_data(DSAT_URL)

# --- 6. DYNAMIC DRILL-DOWN LOGIC ---
st.sidebar.title("Data Selection")
level = str(user.get('access_level', 'IC')).strip()
emails = []

if level == "Admin":
    # 1. Identify "Directors" (those who have managers reporting to them)
    # Based on your data: Jarvis and Sumit are in the 'manager' column for people who are themselves 'Managers'
    all_managers = team_db[team_db['access_level'] == 'Manager']['advisor_name'].unique()
    directors = team_db[team_db['advisor_name'].isin(all_managers)]['manager_name'].unique()
    
    dir_sel = st.sidebar.selectbox("Director View", ["Entire Org"] + list(directors))
    
    if dir_sel == "Entire Org":
        emails = team_db['email'].unique()
    else:
        # Find Managers reporting to selected Director
        mgrs = team_db[(team_db['manager_name'] == dir_sel) & (team_db['access_level'] == 'Manager')]['advisor_name'].unique()
        mgr_sel = st.sidebar.selectbox("Manager Team", ["All Teams"] + list(mgrs))
        
        if mgr_sel == "All Teams":
            # Get everyone who reports to any manager who reports to this director
            emails = team_db[team_db['manager_name'].isin(mgrs)]['email'].unique()
        else:
            # Individual Advisor Drilldown
            advs = team_db[team_db['manager_name'] == mgr_sel]['advisor_name'].unique()
            adv_sel = st.sidebar.selectbox("Advisor", ["Full Team"] + list(advs))
            emails = team_db[team_db['advisor_name'] == adv_sel]['email'].unique() if adv_sel != "Full Team" else team_db[team_db['manager_name'] == mgr_sel]['email'].unique()

elif level == "Manager":
    # Managers see their team and individual drill-down
    my_team = team_db[team_db['manager_name'] == user['advisor_name']]['advisor_name'].unique()
    adv_sel = st.sidebar.selectbox("Team Drill-down", ["Full Team Overview"] + list(my_team))
    
    if adv_sel == "Full Team Overview":
        emails = team_db[team_db['manager_name'] == user['advisor_name']]['email'].unique()
    else:
        emails = team_db[team_db['advisor_name'] == adv_sel]['email'].unique()

else: # IC
    # Error fix: strictly use lower 'email' key
    emails = [user['email']]

# Filter Data
f_kpi = kpi_raw[kpi_raw['email'].isin(emails)]
# Fix: DSAT uses 'advisor email' column
f_dsat = dsat_raw[dsat_raw['advisor email'].isin(emails)]

# --- 7. UI TABS ---
st.title(f"🚀 {user['advisor_name']}'s Dashboard")
tab1, tab2, tab3 = st.tabs(["📊 Performance Hub", "🚫 DSAT Analysis", "🏆 Leaderboards"])

with tab1:
    if not f_kpi.empty:
        # KPI calculations (using renamed columns)
        f_kpi['call_mins'] = f_kpi['advisor call time '].apply(parse_time)
        f_kpi['ia_mins'] = f_kpi['ia_time'].apply(parse_time)
        f_kpi['shift_score'] = np.where(f_kpi['ia_mins'] > 0, (f_kpi['call_mins']/f_kpi['ia_mins']*100), 0)
        
        avg_shift = f_kpi['shift_score'].mean()
        st.metric("Group Avg Shift Score", f"{avg_shift:.2f}%")
        
        # Trend Graph
        f_kpi['date_parsed'] = pd.to_datetime(f_kpi['date_level - as'], format="%b'%d'%y", errors='coerce')
        trend = f_kpi.groupby('date_parsed')['shift_score'].mean().reset_index()
        st.plotly_chart(px.line(trend, x='date_parsed', y='shift_score', title="Shift Score Trend"), use_container_width=True)
    else:
        st.info("No data available for the selected view.")

with tab2:
    st.markdown("### DSAT Analysis")
    if not f_dsat.empty:
        pending = len(f_dsat[f_dsat['feedback'].isna()])
        c1, c2 = st.columns(2)
        c1.metric("Total DSATs", len(f_dsat))
        c2.metric("Pending Feedback", pending)
        st.dataframe(f_dsat[['timestamp', 'advisor email', 'feedback', 'type']], hide_index=True)

with tab3:
    if level in ["Admin", "Manager"]:
        st.markdown("### Team Leaderboard")
        ldb = f_kpi.groupby('advisor_name')['shift_score'].mean().reset_index().sort_values('shift_score', ascending=False)
        st.dataframe(ldb.round(2), hide_index=True)

st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
