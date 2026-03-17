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

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub")

# --- 2. GHL THEME (LIGHT/DARK COMPATIBLE) ---
st.markdown("""
    <style>
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 180px; height: 60px; margin-left: 20px; margin-top: 20px; filter: invert(1) brightness(2);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; }
    div.stInfo { background-color: rgba(0, 82, 255, 0.08); border-left: 5px solid #0052FF; color: var(--text-color); border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA LOADER & NORMALIZER ---
def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    parts = str(time_str).lower().split()
    for p in parts:
        if 'h' in p: h = int(p.replace('h', ''))
        elif 'm' in p: m = int(p.replace('m', ''))
    return (h * 60) + m

@st.cache_data(ttl=60)
def load_data(url, sheet_type):
    try:
        df = pd.read_csv(url)
        # Standardize headers: Strip spaces, remove BOM, and lowercase everything
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '').str.lower()
        
        # Internal Rename Map to fix field inconsistencies across sheets
        name_map = {
            "advisor name": "advisor_name", "agent name": "advisor_name",
            "advisor email": "email", "email": "email",
            "manager": "manager", "manager name": "manager",
            "access level": "access_level", "password": "password",
            "ia": "ia_time", "advisor call time ": "call_time", "advisor call time": "call_time",
            "q/a calls": "qa_calls", "ob calls": "ob_calls", "timestamp": "timestamp",
            "chat dsat url": "chat_url", "feedback": "feedback", "type": "type"
        }
        df = df.rename(columns=name_map)
        
        if 'email' in df.columns:
            df['email'] = df['email'].astype(str).str.strip().str.lower()
        
        if sheet_type == "KPI":
            df['ia_mins'] = df['ia_time'].apply(parse_time) if 'ia_time' in df.columns else 0
            df['call_mins'] = df['call_time'].apply(parse_time) if 'call_time' in df.columns else 0
            df['shift_score'] = np.where(df['ia_mins'] > 0, (df['call_mins']/df['ia_mins']*100), 0)
            df['date_parsed'] = pd.to_datetime(df['date_level - as'], format="%b'%d'%y", errors='coerce')
        return df
    except Exception as e:
        return pd.DataFrame()

def create_ghl_gauge(title, value, target=None, is_percent=True):
    steps = [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}]
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number = {'suffix': "%" if is_percent else "", 'font': {'color': '#0052FF', 'size': 35}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"}, 'steps': steps,
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target} if target else None}
    ))
    fig.update_layout(height=220, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_data(TEAM_URL, "TEAM")

if not st.session_state.auth:
    col1, col2 = st.columns([1, 4])
    with col1: st.image(LOGO_URL, width=150)
    with col2: st.title("Implementation Team Performance Hub")
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

# --- 5. DATA FETCHING & FILTERING ---
user = st.session_state.auth
kpi_raw = load_data(KPI_URL, "KPI")
dsat_raw = load_data(DSAT_URL, "DSAT")

st.sidebar.title("Data Configuration")
freq = st.sidebar.selectbox("Select Frequency", ["Daily", "Weekly", "Monthly", "Yearly"])
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
        my_team = team_db[team_db['manager'] == user['advisor_name']]['advisor_name'].unique()
        adv_sel = st.sidebar.selectbox("Select Advisor", list(my_team))
        emails_to_filter = [team_db[team_db['advisor_name'] == adv_sel]['email'].values[0]]

else: # IC
    # Error Fix: Use 'email' (lowercase) to match the standardized loader
    emails_to_filter = [user['email']]

f_kpi = kpi_raw[kpi_raw['email'].isin(emails_to_filter)]
f_dsat = dsat_raw[dsat_raw['email'].isin(emails_to_filter)]

# --- 6. UI CONTENT ---
st.title("Implementation Team Performance Hub")
st.success(f"Welcome {user['advisor_name']}!!, Access Level : {access}")

tabs_list = ["Performance Overview", "DSAT Analysis"]
if access in ["Admin", "Manager"]: tabs_list.append("Leaderboard")
tabs = st.tabs(tabs_list)

with tabs[0]:
    if not f_kpi.empty:
        # Metrics Calculations
        avg_score = f_kpi['shift_score'].mean()
        avg_sent = f_kpi[f_kpi['total survey'] > 0]['sent rate %'].mean() * 100
        avg_sat = f_kpi[f_kpi['total survey'] > 0]['satisfied survey %'].mean() * 100
        
        st.info(f"Insight: The group is maintaining an average Shift Score of {avg_score:.2f}%. Focus on increasing the Sent Rate which is currently at {avg_sent:.1f}%.")
        
        g1, g2, g3 = st.columns(3)
        g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
        g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
        g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_score, 85), use_container_width=True)
        
        b1, b2 = st.columns(2)
        b1.metric("Total OB Calls", int(f_kpi['ob_calls'].sum()))
        b2.metric("Total OH Calls (QA)", int(f_kpi['qa_calls'].sum()))

        st.markdown("### Performance Trends")
        trend_data = f_kpi.groupby('date_parsed').mean(numeric_only=True).reset_index()
        st.plotly_chart(px.line(trend_data, x='date_parsed', y=['shift_score', 'sent rate %'], title="Key Metrics Over Time"), use_container_width=True)
    else:
        st.warning("No data found for this selection.")

with tabs[1]:
    st.markdown("### DSAT Summary")
    pending = len(f_dsat[f_dsat['feedback'].isna() | (f_dsat['feedback'] == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", len(f_dsat))
    s2.metric("Feedback Pending", pending)
    s3.metric("Controllable", len(f_dsat[f_dsat['type'] == 'Controllable']))
    s4.metric("Uncontrollable", len(f_dsat[f_dsat['type'] == 'Uncontrollable']))
    st.dataframe(f_dsat[['timestamp', 'chat_url', 'type', 'feedback']], hide_index=True, use_container_width=True)

st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
    
