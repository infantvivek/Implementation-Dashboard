import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

# --- 2. DATA LOADING & CLEANING ---
@st.cache_data(ttl=60)
def load_data(url):
    try:
        df = pd.read_csv(url)
        # Clean column names: remove hidden BOMs, spaces, and ensure consistent casing
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
    # Login Screen Header
    col1, col2 = st.columns([1, 5])
    with col1: st.image(LOGO_URL, width=100)
    with col2: st.title("HIGHLEVEL CS PERFORMANCE TRACKER")
    
    with st.form("login"):
        e_in = st.text_input("Work Email").lower().strip()
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            team_db = load_data(TEAM_URL)
            if not team_db.empty:
                # Login check using cleaned 'Email' column
                user_match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str).str.strip() == p_in)]
                if not user_match.empty:
                    st.session_state.auth = user_match.iloc[0].to_dict()
                    st.rerun()
            st.error("Invalid credentials.")
    st.stop()

# --- 4. PERMISSIONS & DATA FILTERING ---
user = st.session_state.auth
# Use .get() to prevent KeyError if 'Access Level' is missing in Team sheet
level = user.get('Access Level', 'IC') 
kpi_raw = load_data(KPI_URL)
dsat_raw = load_data(DSAT_URL)
team_db = load_data(TEAM_URL)

# DSAT Filter: Exclude duplicates
if 'Processed' in dsat_raw.columns:
    dsat_raw = dsat_raw[dsat_raw['Processed'] != 'DUPLICATE']

# Role-Based Filtering Logic
if level == "Admin":
    scope = st.sidebar.radio("View Scope", ["Entire Data", "By Manager Team", "By Advisor"])
    if scope == "Entire Data":
        f_kpi, f_dsat = kpi_raw, dsat_raw
    elif scope == "By Manager Team":
        mgr_list = team_db[team_db['Access Level'] == 'Manager']['Advisor Name'].unique()
        mgr = st.sidebar.selectbox("Select Manager", mgr_list)
        team_emails = team_db[team_db['Manager Name'] == mgr]['Email'].unique()
        f_kpi = kpi_raw[kpi_raw['Email'].isin(team_emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(team_emails)]
    else:
        adv_list = sorted(kpi_raw['Advisor Name'].dropna().unique())
        adv = st.sidebar.selectbox("Select Advisor", adv_list)
        f_kpi = kpi_raw[kpi_raw['Advisor Name'] == adv]
        f_dsat = dsat_raw[dsat_raw['Advisor Name'] == adv]

elif level == "Manager":
    team_emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    mgr_view = st.sidebar.radio("Manager Scope", ["Full Team View", "Advisor Drill-down"])
    if mgr_view == "Advisor Drill-down":
        adv_name = st.sidebar.selectbox("Team Member", team_db[team_db['Email'].isin(team_emails)]['Advisor Name'])
        f_kpi = kpi_raw[kpi_raw['Advisor Name'] == adv_name]
        f_dsat = dsat_raw[dsat_raw['Advisor Name'] == adv_name]
    else:
        f_kpi = kpi_raw[kpi_raw['Email'].isin(team_emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(team_emails)]

else: # IC Access Level
    f_kpi = kpi_raw[kpi_raw['Email'] == user['Email']]
    f_dsat = dsat_raw[dsat_raw['Email'] == user['Email']]

# --- 5. DASHBOARD HEADER ---
head1, head2 = st.columns([1, 6])
with head1: st.image(LOGO_URL, width=80)
with head2: st.header(f"HIGHLEVEL CS PERFORMANCE TRACKER")
st.subheader(f"Welcome {user['Advisor Name']} | Access: {level}")

# --- 6. APP TABS ---
tab_list = ["Performance", "DSAT Analysis", "Detailed Report"]
if level in ["Manager", "Admin"]:
    tab_list.append("Leaderboards")
tabs = st.tabs(tab_list)

# TAB 1: Performance Overview
with tabs[0]:
    st.markdown("### 📊 Performance Metrics")
    st.info("Performance Narrative, Summary, and Trends section goes here.")

# TAB 2: DSAT Analysis
with tabs[1]:
    st.markdown("### 🚫 DSAT Analysis & Feedback")
    if not f_dsat.empty:
        # Field selection: Map 'Timestamp' to 'Date' for display
        dsat_cols = ['Timestamp', 'Advisor Name', 'DSAT chat link', 'Feedback']
        existing_cols = [c for c in dsat_cols if c in f_dsat.columns]
        display_dsat = f_dsat[existing_cols].copy()
        if 'Timestamp' in display_dsat.columns:
            display_dsat.rename(columns={'Timestamp': 'Date'}, inplace=True)
        
        if level in ["Manager", "Admin"]:
            st.data_editor(
                display_dsat,
                column_config={"DSAT chat link": st.column_config.LinkColumn("Chat Link")},
                disabled=['Date', 'Advisor Name', 'DSAT chat link'],
                hide_index=True,
                use_container_width=True
            )
        else:
            st.dataframe(display_dsat, hide_index=True, use_container_width=True)
    else:
        st.write("No DSAT records found for this selection.")

# TAB 3: Detailed Report
with tabs[2]:
    st.markdown("### 📝 Detailed KPI Report")
    st.dataframe(f_kpi, hide_index=True, use_container_width=True)

# TAB 4: Leaderboards (Manager/Admin Only)
if len(tabs) > 3:
    with tabs[3]:
        st.markdown("### 🏆 Team Leaderboards")
        st.write("Leaderboard metrics and Success Champions rankings.")

st.sidebar.divider()
st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'auth': None}))
