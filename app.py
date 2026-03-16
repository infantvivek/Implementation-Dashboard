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
def load_data(url, sheet_name=None):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        
        # Mapping 'Advisor Email' to internal 'Email' key for all relevant sheets
        if 'Advisor Email' in df.columns:
            df['Email'] = df['Advisor Email'].astype(str).str.strip().str.lower()
        elif 'Email' in df.columns:
            df['Email'] = df['Email'].astype(str).str.strip().str.lower()
            
        return df
    except Exception as e:
        st.error(f"Error loading {sheet_name}: {e}")
        return pd.DataFrame()

# --- 3. AUTHENTICATION ---
if 'auth' not in st.session_state:
    st.session_state.auth = None

if not st.session_state.auth:
    col1, col2 = st.columns([1, 5])
    with col1: st.image(LOGO_URL, width=100)
    with col2: st.title("HIGHLEVEL CS PERFORMANCE TRACKER")
    
    with st.form("login"):
        e_in = st.text_input("Advisor Email").lower().strip()
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            team_db = load_data(TEAM_URL, "Team Details")
            if not team_db.empty:
                # Login logic using the updated Advisor Email field
                user_match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str).str.strip() == p_in)]
                if not user_match.empty:
                    st.session_state.auth = user_match.iloc[0].to_dict()
                    st.rerun()
            st.error("Invalid credentials. Please verify your Advisor Email and Password.")
    st.stop()

# --- 4. PERMISSIONS & DATA FILTERING ---
user = st.session_state.auth
level = user.get('Access Level', 'IC') 
kpi_raw = load_data(KPI_URL, "KPI Data")
dsat_raw = load_data(DSAT_URL, "DSAT Data")
team_db = load_data(TEAM_URL, "Team Details")

# DSAT Filter: Exclude rows marked DUPLICATE in the 'Processed' column
if 'Processed' in dsat_raw.columns:
    dsat_raw = dsat_raw[dsat_raw['Processed'] != 'DUPLICATE']

# Hierarchy Filtering
if level == "Admin":
    scope = st.sidebar.radio("View Scope", ["Entire Org", "Manager Team", "Individual Advisor"])
    if scope == "Entire Org":
        f_kpi, f_dsat = kpi_raw, dsat_raw
    elif scope == "Manager Team":
        mgr = st.sidebar.selectbox("Select Manager", team_db[team_db['Access Level'] == 'Manager']['Advisor Name'].unique())
        team_emails = team_db[team_db['Manager Name'] == mgr]['Email'].unique()
        f_kpi = kpi_raw[kpi_raw['Email'].isin(team_emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(team_emails)]
    else:
        adv = st.sidebar.selectbox("Select Advisor", sorted(kpi_raw['Advisor Name'].dropna().unique()))
        f_kpi = kpi_raw[kpi_raw['Advisor Name'] == adv]
        f_dsat = dsat_raw[dsat_raw['Email'] == team_db[team_db['Advisor Name'] == adv]['Email'].iloc[0]]

elif level == "Manager":
    team_emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    mgr_view = st.sidebar.radio("Manager Scope", ["Team Summary", "Advisor Drill-down"])
    if mgr_view == "Advisor Drill-down":
        adv_name = st.sidebar.selectbox("Team Member", team_db[team_db['Email'].isin(team_emails)]['Advisor Name'])
        f_kpi = kpi_raw[kpi_raw['Advisor Name'] == adv_name]
        f_dsat = dsat_raw[dsat_raw['Email'] == team_db[team_db['Advisor Name'] == adv_name]['Email'].iloc[0]]
    else:
        f_kpi = kpi_raw[kpi_raw['Email'].isin(team_emails)]
        f_dsat = dsat_raw[dsat_raw['Email'].isin(team_emails)]

else: # IC Access Level
    f_kpi = kpi_raw[kpi_raw['Email'] == user['Email']]
    f_dsat = dsat_raw[dsat_raw['Email'] == user['Email']]

# --- 5. DASHBOARD LAYOUT (TABS) ---
head1, head2 = st.columns([1, 6])
with head1: st.image(LOGO_URL, width=80)
with head2: st.header("HIGHLEVEL CS PERFORMANCE TRACKER")
st.caption(f"Welcome {user['Advisor Name']} | Access: {level}")

tab_titles = ["Performance Hub", "DSAT Analysis", "Detailed Logs"]
if level in ["Manager", "Admin"]:
    tab_titles.append("Leaderboards")

tab1, tab2, tab3, *tab4 = st.tabs(tab_titles)

with tab1:
    st.subheader("📊 Performance Insights")
    st.info("Performance Narrative, Visual Trends, and Metric cards appear here.")

with tab2:
    st.subheader("🚫 DSAT Analysis & Feedback")
    if not f_dsat.empty:
        # Field mapping: Timestamp becomes Date
        dsat_cols = ['Timestamp', 'Advisor Name', 'DSAT chat link', 'Feedback']
        existing = [c for c in dsat_cols if c in f_dsat.columns]
        display_df = f_dsat[existing].copy()
        if 'Timestamp' in display_df.columns:
            display_df.rename(columns={'Timestamp': 'Date'}, inplace=True)
        
        if level in ["Manager", "Admin"]:
            st.write("Management: You can review and draft coaching feedback below.")
            st.data_editor(
                display_df,
                column_config={"DSAT chat link": st.column_config.LinkColumn("Chat Link")},
                disabled=['Date', 'Advisor Name', 'DSAT chat link'],
                hide_index=True,
                use_container_width=True
            )
        else:
            st.dataframe(display_df, hide_index=True, use_container_width=True)
    else:
        st.write("No DSAT records found for this scope.")

with tab3:
    st.subheader("📝 Detailed KPI Log")
    st.dataframe(f_kpi, hide_index=True, use_container_width=True)

if tab4:
    with tab4[0]:
        st.subheader("🏆 Organization Rankings")
        st.write("Leaderboard data restricted to Management and Admin access.")

st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
