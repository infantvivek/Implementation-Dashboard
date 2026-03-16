import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"

st.set_page_config(layout="wide", page_title="Performance & Feedback Portal")

# --- 2. DATA LOADING & CLEANING ---
@st.cache_data(ttl=60)
def load_data(url):
    try:
        df = pd.read_csv(url)
        # Clean column names: remove spaces and special characters
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        if 'Email' in df.columns:
            df['Email'] = df['Email'].astype(str).str.strip().str.lower()
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# --- 3. AUTHENTICATION ---
if 'auth' not in st.session_state:
    st.session_state.auth = None

if not st.session_state.auth:
    st.title("The Go Getters Access Portal")
    with st.form("login"):
        e_in = st.text_input("Work Email").lower().strip()
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            team_db = load_data(TEAM_URL)
            if not team_db.empty:
                # Login check
                user = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str) == p_in)]
                if not user.empty:
                    st.session_state.auth = user.iloc[0].to_dict()
                    st.rerun()
            st.error("Invalid credentials.")
    st.stop()

# --- 4. PERMISSIONS & DATA FILTERING ---
user = st.session_state.auth
level = user.get('Access Level', 'IC') # Default to IC if column missing
kpi_raw = load_data(KPI_URL)
dsat_raw = load_data(DSAT_URL)
team_db = load_data(TEAM_URL)

# DSAT Filter: Exclude rows where Processed is 'DUPLICATE'
if 'Processed' in dsat_raw.columns:
    dsat_raw = dsat_raw[dsat_raw['Processed'] != 'DUPLICATE']

# Filtering based on Access Levels
if level == "Admin":
    scope = st.sidebar.radio("View Scope", ["Entire Data", "By Manager Team", "By Advisor"])
    if scope == "Entire Data":
        f_kpi, f_dsat = kpi_raw, dsat_raw
    elif scope == "By Manager Team":
        mgr = st.sidebar.selectbox("Select Manager", team_db[team_db['Access Level'] == 'Manager']['Advisor Name'])
        team_emails = team_db[team_db['Manager Name'] == mgr]['Email'].unique()
        f_kpi = kpi_raw[kpi_raw['Email'].isin(team_emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(team_emails)]
    else:
        adv = st.sidebar.selectbox("Select Advisor", sorted(kpi_raw['Advisor Name'].unique()))
        f_kpi = kpi_raw[kpi_raw['Advisor Name'] == adv]
        f_dsat = dsat_raw[dsat_raw['Advisor Name'] == adv]

elif level == "Manager":
    # Access only their own team data
    team_emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    mgr_view = st.sidebar.radio("Manager Scope", ["Full Team View", "Advisor Drill-down"])
    if mgr_view == "Advisor Drill-down":
        adv = st.sidebar.selectbox("Team Member", team_db[team_db['Email'].isin(team_emails)]['Advisor Name'])
        f_kpi = kpi_raw[kpi_raw['Advisor Name'] == adv]
        f_dsat = dsat_raw[dsat_raw['Advisor Name'] == adv]
    else:
        f_kpi = kpi_raw[kpi_raw['Email'].isin(team_emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(team_emails)]

else: # IC - access to just their own data
    f_kpi = kpi_raw[kpi_raw['Email'] == user['Email']]
    f_dsat = dsat_raw[dsat_raw['Email'] == user['Email']]

# --- 5. DASHBOARD TABS ---
# Tab structure: Performance, DSAT, Detailed Report, Leaderboards
tab_list = ["Performance", "DSAT Analysis", "Detailed Report"]
if level in ["Manager", "Admin"]:
    tab_list.append("Leaderboards")

tabs = st.tabs(tab_list)

# TAB 1: Performance Overview
with tabs[0]:
    st.header(f"Performance Overview: {user['Advisor Name']}")
    st.info("Performance Narrative, Summary, and Trends section.")

# TAB 2: DSAT Analysis
with tabs[1]:
    st.header("🚫 DSAT Analysis & Feedback")
    if not f_dsat.empty:
        # Display specific fields
        dsat_cols = ['Timestamp', 'Advisor Name', 'DSAT chat link', 'Feedback']
        existing_cols = [c for c in dsat_cols if c in f_dsat.columns]
        
        # Date formatting for Timestamp
        display_dsat = f_dsat[existing_cols].copy()
        if 'Timestamp' in display_dsat.columns:
            display_dsat.rename(columns={'Timestamp': 'Date'}, inplace=True)
        
        if level in ["Manager", "Admin"]:
            st.write("Click on 'Feedback' to edit. *Note: Saves require a Google Form workaround.*")
            st.data_editor(
                display_dsat,
                column_config={"DSAT chat link": st.column_config.LinkColumn("Chat Link")},
                disabled=['Date', 'Advisor Name', 'DSAT chat link'],
                hide_index=True,
                use_container_width=True
            )
        else:
            # IC: Read-only
            st.dataframe(display_dsat, hide_index=True, use_container_width=True)

# TAB 3: Detailed Report
with tabs[2]:
    st.header("Detailed Performance Report")
    st.dataframe(f_kpi, hide_index=True)

# TAB 4: Leaderboards (Manager/Admin Only)
if len(tabs) > 3:
    with tabs[3]:
        st.header("🏆 Team Leaderboards")
        st.write("Success Champions and team metrics display.")

st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'auth': None}))
