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

# PRE-FILLED FORM CONFIG
FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY = "entry.1"
ENTRY_FEEDBACK = "entry.2"
ENTRY_TYPE = "entry.3"

st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

# --- 2. GHL DYNAMIC THEME ---
st.markdown("""
    <style>
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 180px; height: 60px; margin-left: 20px; margin-top: 20px; filter: invert(1) brightness(2);
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. HELPERS & DIALOG ---
def create_ghl_gauge(title, value, target=None, is_percent=True, color_steps=False):
    steps = []
    if color_steps:
        steps = [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}]
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 18, 'color': 'gray'}},
        number = {'suffix': "%" if is_percent else "", 'font': {'color': '#0052FF', 'size': 35}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"}, 'steps': steps}
    ))
    fig.update_layout(height=220, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update DSAT Record", width="large")
def open_form_dialog(url):
    iframe(url, height=700, scrolling=True)
    if st.button("Close & Sync Dashboard"): st.rerun()

# --- 4. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data(url, sheet_type=None):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '')
        if 'Email' in df.columns: df['Email'] = df['Email'].astype(str).str.strip().str.lower()
        return df
    except Exception as e: return pd.DataFrame()

# --- 5. AUTHENTICATION (DYNAMIC) ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_data(TEAM_URL, "TEAM")

if not st.session_state.auth:
    c1, c2 = st.columns([1, 4])
    with c1: st.image(LOGO_URL, width=150)
    with c2: st.title("HIGHLEVEL PERFORMANCE HUB")
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

# --- 6. DATA FETCHING ---
user = st.session_state.auth
kpi_raw = load_data(KPI_URL, "KPI")
dsat_raw = load_data(DSAT_URL, "DSAT")

# Generic KPI Cleaning (Dynamic Mapping)
kpi_raw = kpi_raw.rename(columns={"Date_level - AS": "Date", "Agent Name": "Advisor Name", "IA": "IA_Hours", "Advisor Call Time ": "Advisor Call Time", "Manager": "Manager Name"})
dsat_raw = dsat_raw.rename(columns={"Advisor Email": "Email", "Chat DSAT URL": "DSAT chat link", "Manager": "Manager Name"})

kpi_raw['Date_Parsed'] = pd.to_datetime(kpi_raw['Date'], format="%b'%d'%y", errors='coerce')
dsat_raw['Date_Parsed'] = pd.to_datetime(dsat_raw['Timestamp'], errors='coerce')

# --- 7. DYNAMIC HIERARCHY FILTERING ---
level = user.get('Access level', 'IC')
f_kpi, f_dsat = kpi_raw, dsat_raw

st.sidebar.title("Data Filtering")

if level == "Admin":
    # 1. Get all unique Senior Managers (Managers of other Managers)
    all_managers = team_db['Manager Name'].unique()
    advisors_who_are_managers = team_db[team_db['Advisor Name'].isin(all_managers)]
    senior_managers = advisors_who_are_managers['Manager Name'].unique()

    sr_mgr_opt = st.sidebar.selectbox("Organization Overview", ["Entire Org"] + list(senior_managers))
    
    if sr_mgr_opt == "Entire Org":
        f_kpi, f_dsat = kpi_raw, dsat_raw
    else:
        # Find all managers reporting to this Senior Manager
        managers_under = team_db[team_db['Manager Name'] == sr_mgr_opt]['Advisor Name'].unique()
        mgr_opt = st.sidebar.selectbox(f"Managers under {sr_mgr_opt}", ["All Teams"] + list(managers_under))
        
        if mgr_opt == "All Teams":
            emails = team_db[team_db['Manager Name'].isin(managers_under)]['Email'].unique()
        else:
            # Individual Advisor Drill-down within Manager Team
            advisors_under = team_db[team_db['Manager Name'] == mgr_opt]['Advisor Name'].unique()
            adv_opt = st.sidebar.selectbox(f"Advisors under {mgr_opt}", ["Entire Team"] + list(advisors_under))
            
            if adv_opt == "Entire Team":
                emails = team_db[team_db['Manager Name'] == mgr_opt]['Email'].unique()
            else:
                emails = team_db[team_db['Advisor Name'] == adv_opt]['Email'].unique()
        
        f_kpi = kpi_raw[kpi_raw['Email'].isin(emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(emails)]

elif level == "Manager":
    # Managers see their team and can drill down to individual advisors
    team_members = team_db[team_db['Manager Name'] == user['Advisor Name']]['Advisor Name'].unique()
    view_opt = st.sidebar.selectbox("Team View", ["Full Team"] + list(team_members))
    
    if view_opt == "Full Team":
        emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    else:
        emails = team_db[team_db['Advisor Name'] == view_opt]['Email'].unique()
        
    f_kpi = kpi_raw[kpi_raw['Email'].isin(emails)]
    f_dsat = dsat_raw[dsat_raw['Email'].isin(emails)]

else: # IC Level
    f_kpi = kpi_raw[kpi_raw['Email'] == user['Email']]
    f_dsat = dsat_raw[dsat_raw['Email'] == user['Email']]

# --- 8. UI TABS & CONTENT (Remains Same as requested) ---
# [Gauges, Trends, and DSAT Table logic follows here using f_kpi and f_dsat]
st.write(f"Showing data for: {user['Advisor Name']} ({level})")
st.divider()

# Final Footer Step
st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
