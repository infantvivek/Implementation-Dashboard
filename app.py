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

# --- 2. DYNAMIC THEME (DARK MODE OPTIMIZED) ---
st.markdown("""
    <style>
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 180px; height: 60px; margin-left: 20px; margin-top: 20px; filter: invert(1) brightness(2);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA LOADER ---
@st.cache_data(ttl=60)
def load_and_clean_data(url):
    try:
        df = pd.read_csv(url)
        # Clean column names: remove BOM, whitespace, and standardize mapping
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '')
        
        # Internal mapping to fix common naming variations across sheets
        name_map = {
            "Advisor Email": "email", "Email": "email",
            "Advisor Name": "advisor_name", "Agent Name": "advisor_name",
            "Manager": "manager_name", "Manager Name": "manager_name",
            "Access level": "access_level", "Access Level": "access_level",
            "Date_level - AS": "date", "Timestamp": "timestamp"
        }
        df = df.rename(columns=name_map)
        if 'email' in df.columns:
            df['email'] = df['email'].astype(str).str.strip().str.lower()
        return df
    except Exception as e:
        return pd.DataFrame()

# --- 4. HELPERS ---
def create_ghl_gauge(title, value, target=None, color_steps=True):
    steps = [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}] if color_steps else []
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, title = {'text': title, 'font': {'size': 16}},
        number = {'suffix': "%", 'font': {'color': '#0052FF'}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"}, 'steps': steps,
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target} if target else None}
    ))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

# --- 5. AUTHENTICATION & SESSION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_clean_data(TEAM_URL)

if not st.session_state.auth:
    col_a, col_b = st.columns([1, 4])
    with col_a: st.image(LOGO_URL, width=150)
    with col_b: st.title("PERFORMANCE HUB LOGIN")
    with st.form("login"):
        e_in = st.text_input("Work Email").lower().strip()
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            # The 'email' column is now guaranteed lowercase and stripped
            user_match = team_db[(team_db['email'] == e_in) & (team_db['Password'].astype(str).str.strip() == str(p_in).strip())]
            if not user_match.empty:
                st.session_state.auth = user_match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 6. DYNAMIC DATA FETCHING ---
user = st.session_state.auth
kpi_raw = load_and_clean_data(KPI_URL)
dsat_raw = load_and_clean_data(DSAT_URL)

# --- 7. DYNAMIC HIERARCHY FILTERING ---
st.sidebar.title("Navigation Filters")
level = str(user.get('access_level', 'IC')).strip()
f_kpi, f_dsat = pd.DataFrame(), pd.DataFrame()

if level == "Admin":
    # Find Sr Managers (Directors) -> Managers -> Advisors
    directors = team_db[team_db['advisor_name'].isin(team_db['manager_name'].unique())]['manager_name'].unique()
    dir_sel = st.sidebar.selectbox("Director View", ["Entire Org"] + list(directors))
    
    if dir_sel == "Entire Org":
        emails = team_db['email'].unique()
    else:
        managers = team_db[team_db['manager_name'] == dir_sel]['advisor_name'].unique()
        mgr_sel = st.sidebar.selectbox("Manager Team", ["All Depts"] + list(managers))
        
        if mgr_sel == "All Depts":
            emails = team_db[team_db['manager_name'] == dir_sel]['email'].unique()
        else:
            advisors = team_db[team_db['manager_name'] == mgr_sel]['advisor_name'].unique()
            adv_sel = st.sidebar.selectbox("Individual Advisor", ["Entire Team"] + list(advisors))
            emails = team_db[team_db['advisor_name'] == adv_sel]['email'].unique() if adv_sel != "Entire Team" else team_db[team_db['manager_name'] == mgr_sel]['email'].unique()

elif level == "Manager":
    advisors = team_db[team_db['manager_name'] == user['advisor_name']]['advisor_name'].unique()
    adv_sel = st.sidebar.selectbox("Team View", ["Full Team Overview"] + list(advisors))
    emails = team_db[team_db['advisor_name'] == adv_sel]['email'].unique() if adv_sel != "Full Team Overview" else team_db[team_db['manager_name'] == user['advisor_name']]['email'].unique()

else: # IC
    emails = [user['email']]

f_kpi = kpi_raw[kpi_raw['email'].isin(emails)]
f_dsat = dsat_raw[dsat_raw['email'].isin(emails)]

# --- 8. DASHBOARD UI ---
st.title(f"🚀 {user['advisor_name']}'s Dashboard")
st.caption(f"Access Level: {level}")

tab1, tab2 = st.tabs(["Performance", "DSAT Audit"])

with tab1:
    if not f_kpi.empty:
        # Trend Analysis
        f_kpi['date_parsed'] = pd.to_datetime(f_kpi['date'], format="%b'%d'%y", errors='coerce')
        trend = f_kpi.groupby('date_parsed').mean(numeric_only=True).reset_index()
        st.plotly_chart(px.line(trend, x='date_parsed', y='Shift_Score', title="Shift Score Trend", markers=True), use_container_width=True)
    else:
        st.warning("No performance data found for the selected scope.")

with tab2:
    st.markdown("### 🚫 DSAT Analysis Summary")
    pending = len(f_dsat[f_dsat['Feedback'].isna()]) if not f_dsat.empty else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Total DSATs", len(f_dsat))
    c2.metric("Feedback Pending", pending)
    
    if not f_dsat.empty:
        st.dataframe(f_dsat[['timestamp', 'advisor_name', 'DSAT chat link', 'Feedback', 'Type']], hide_index=True)

st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
