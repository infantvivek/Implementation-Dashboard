import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"

st.set_page_config(layout="wide", page_title="Performance & Feedback Portal")

# --- 2. DATA LOADING (FIXED) ---
@st.cache_data(ttl=60)
def load_data(url, is_kpi=False):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        if 'Email' in df.columns:
            # FIXED: Added .str before .lower()
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
        e_in = st.text_input("Email").lower().strip()
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            team_db = load_data(TEAM_URL)
            if not team_db.empty:
                user = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str) == p_in)]
                if not user.empty:
                    st.session_state.auth = user.iloc[0].to_dict()
                    st.rerun()
            st.error("Invalid credentials.")
    st.stop()

# --- 4. DATA PREP & FILTERING ---
user = st.session_state.auth
level = user['Access Level'] # IC, Manager, Admin
kpi_raw = load_data(KPI_URL)
dsat_raw = load_data(DSAT_URL)
team_db = load_data(TEAM_URL)

# DSAT Filter: Exclude duplicates
if 'Processed' in dsat_raw.columns:
    dsat_raw = dsat_raw[dsat_raw['Processed'] != 'DUPLICATE']

# ACCESS PERMISSIONS LOGIC
if level == "Admin":
    scope = st.sidebar.radio("View Scope", ["Global", "Manager Team", "Specific Advisor"])
    if scope == "Global":
        f_kpi, f_dsat = kpi_raw, dsat_raw
    elif scope == "Manager Team":
        mgr = st.sidebar.selectbox("Select Manager", team_db[team_db['Access Level'] == 'Manager']['Advisor Name'])
        team_emails = team_db[team_db['Manager Name'] == mgr]['Email'].unique()
        f_kpi = kpi_raw[kpi_raw['Email'].isin(team_emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(team_emails)]
    else:
        adv = st.sidebar.selectbox("Select Advisor", sorted(kpi_raw['Advisor Name'].unique()))
        f_kpi = kpi_raw[kpi_raw['Advisor Name'] == adv]
        f_dsat = dsat_raw[dsat_raw['Advisor Name'] == adv]

elif level == "Manager":
    team_emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    sub_scope = st.sidebar.radio("Scope", ["Team View", "Advisor Drill-down"])
    if sub_scope == "Advisor Drill-down":
        adv = st.sidebar.selectbox("Team Member", team_db[team_db['Email'].isin(team_emails)]['Advisor Name'])
        f_kpi = kpi_raw[kpi_raw['Advisor Name'] == adv]
        f_dsat = dsat_raw[dsat_raw['Advisor Name'] == adv]
    else:
        f_kpi = kpi_raw[kpi_raw['Email'].isin(team_emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(team_emails)]

else: # IC Access Level
    f_kpi = kpi_raw[kpi_raw['Email'] == user['Email']]
    f_dsat = dsat_raw[dsat_raw['Email'] == user['Email']]

# --- 5. APP TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["Performance Dashboard", "DSAT Analysis", "Detailed Report", "Leaderboards"])

with tab1:
    st.header("Performance Overview")
    st.info("Performance Narrative, Summary, and Trends would be displayed here.")

with tab2:
    st.header("🚫 DSAT Analysis & Feedback")
    if not f_dsat.empty:
        # Display specific fields
        display_cols = ['Timestamp', 'Advisor Name', 'DSAT chat link', 'Feedback']
        existing_cols = [c for c in display_cols if c in f_dsat.columns]
        
        if level in ["Manager", "Admin"]:
            st.write("Managers/Admins: View and provide feedback below.")
            # st.data_editor used for editable feedback workaround
            edited_dsat = st.data_editor(
                f_dsat[existing_cols],
                column_config={"DSAT chat link": st.column_config.LinkColumn("Chat Link")},
                disabled=['Timestamp', 'Advisor Name', 'DSAT chat link'],
                hide_index=True,
                use_container_width=True
            )
            st.warning("Feedback is stored locally in the app. To save permanently without an API, use the Pre-filled Google Form method.")
        else:
            # IC: Read-only
            st.dataframe(f_dsat[existing_cols], hide_index=True, use_container_width=True)

with tab3:
    st.header("Detailed Performance Report")
    st.dataframe(f_kpi, hide_index=True)

with tab4:
    if level in ["Manager", "Admin"]:
        st.header("🏆 Team Leaderboards")
        st.write("Leaderboard data restricted to Management.")
    else:
        st.error("You do not have permission to view leaderboards.")

st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'auth': None}))
