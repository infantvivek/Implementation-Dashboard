import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURATION ---
# Replace these with your actual CSV export links
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"

# SETTING AUTO-ADJUST WIDTH
st.set_page_config(layout="wide", page_title="GoHighLevel Performance Portal")

# --- DATA LOADING ---
@st.cache_data(ttl=60)
def load_data(url):
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip().str.replace('\ufeff', '')
    if 'Email' in df.columns:
        df['Email'] = df['Email'].astype(str).str.strip().lower()
    return df

# --- AUTHENTICATION ---
if 'auth' not in st.session_state:
    st.session_state.auth = None

if not st.session_state.auth:
    st.title("The Go Getters Access Portal")
    with st.form("login"):
        e_in = st.text_input("Email").lower().strip()
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            team_db = load_data(TEAM_URL)
            user = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str) == p_in)]
            if not user.empty:
                st.session_state.auth = user.iloc[0].to_dict()
                st.rerun()
            st.error("Invalid credentials.")
    st.stop()

# --- GLOBAL DATA PREP ---
user = st.session_state.auth
level = user['Access Level'] # IC, Manager, Admin
kpi_raw = load_data(KPI_URL)
dsat_raw = load_data(DSAT_URL)
team_db = load_data(TEAM_URL)

# Filter DSAT for non-duplicates
dsat_raw = dsat_raw[dsat_raw.get('Processed', '') != 'DUPLICATE']

# --- PRIVILEGED FILTERING ---
if level == "Admin":
    scope = st.sidebar.radio("View Scope", ["Global", "Manager Team", "Specific IC"])
    if scope == "Global":
        f_kpi, f_dsat = kpi_raw, dsat_raw
    elif scope == "Manager Team":
        mgr = st.sidebar.selectbox("Select Manager", team_db['Advisor Name'][team_db['Access Level'] == 'Manager'])
        team_emails = team_db[team_db['Manager Name'] == mgr]['Email'].unique()
        f_kpi = kpi_raw[kpi_raw['Email'].isin(team_emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(team_emails)]
    else:
        ic = st.sidebar.selectbox("Select Advisor", sorted(kpi_raw['Advisor Name'].unique()))
        f_kpi = kpi_raw[kpi_raw['Advisor Name'] == ic]
        f_dsat = dsat_raw[dsat_raw['Advisor Name'] == ic]

elif level == "Manager":
    team_emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    sub_view = st.sidebar.radio("Scope", ["My Team", "Advisor Drill-down"])
    if sub_view == "Advisor Drill-down":
        ic = st.sidebar.selectbox("Team Member", team_db[team_db['Email'].isin(team_emails)]['Advisor Name'])
        f_kpi = kpi_raw[kpi_raw['Advisor Name'] == ic]
        f_dsat = dsat_raw[dsat_raw['Advisor Name'] == ic]
    else:
        f_kpi = kpi_raw[kpi_raw['Email'].isin(team_emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(team_emails)]

else: # IC Level
    f_kpi = kpi_raw[kpi_raw['Email'] == user['Email']]
    f_dsat = dsat_raw[dsat_raw['Email'] == user['Email']]

# --- APP TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["Performance Dashboard", "DSAT Analysis", "Detailed Report", "Leaderboards"])

with tab1:
    st.header(f"Performance Metrics: {user['Advisor Name']}")
    # Metric logic with color indicators
    # (Insert Performance Narrative, Summary, and Trends logic here)
    st.info("Performance summary and trends calculated based on selected timeframe.")

with tab2:
    st.header("🚫 DSAT Analysis & Feedback")
    # Mapping Timestamp to Date for display
    if not f_dsat.empty:
        dsat_display = f_dsat[['Timestamp', 'Advisor Name', 'DSAT chat link', 'Feedback']].copy()
        dsat_display.rename(columns={'Timestamp': 'Date'}, inplace=True)
        
        if level in ["Manager", "Admin"]:
            st.write("Managers: To update feedback, click the chat link to review and use the external update form.")
            st.dataframe(dsat_display, hide_index=True)
            # Suggesting workaround: Pre-filled Google Form Link for feedback storage
            st.warning("Workaround: Because Direct API is disabled, use the linked Google Form in the main sheet to submit 'Feedback Overrides' linked by Timestamp.")
        else:
            st.dataframe(dsat_display, hide_index=True)

with tab3:
    st.header("Detailed Performance Report")
    st.dataframe(f_kpi, hide_index=True)

with tab4:
    if level in ["Manager", "Admin"]:
        st.header("🏆 Team Leaderboards")
        # Logic for Success Champions based on 85%/90% criteria
        st.write("Leaderboard data available for team-wide comparison.")
    else:
        st.error("You do not have permission to view leaderboards.")

st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'auth': None}))
