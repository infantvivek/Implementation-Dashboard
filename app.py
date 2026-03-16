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
def load_data(url, sheet_type=None):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        
        # Standardizing Emails
        if sheet_type == "DSAT" and 'Advisor Email' in df.columns:
            df['Email'] = df['Advisor Email'].astype(str).str.strip().str.lower()
        elif 'Email' in df.columns:
            df['Email'] = df['Email'].astype(str).str.strip().str.lower()
            
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
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
            team_db = load_data(TEAM_URL)
            if not team_db.empty:
                user_match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str).str.strip() == p_in)]
                if not user_match.empty:
                    st.session_state.auth = user_match.iloc[0].to_dict()
                    st.rerun()
            st.error("Invalid credentials.")
    st.stop()

# --- 4. DATA PREP ---
user = st.session_state.auth
level = user.get('Access Level', 'IC') 
kpi_raw = load_data(KPI_URL)
dsat_raw = load_data(DSAT_URL, sheet_type="DSAT")
team_db = load_data(TEAM_URL)

# Basic Date Parsing
kpi_raw['Date_Parsed'] = pd.to_datetime(kpi_raw['Date'], format="%b'%d'%y", errors='coerce')
dsat_raw['Date_Parsed'] = pd.to_datetime(dsat_raw['Timestamp'], errors='coerce')

# Filter DSAT Duplicates
if 'Processed' in dsat_raw.columns:
    dsat_raw = dsat_raw[dsat_raw['Processed'] != 'DUPLICATE']

# --- 5. FREQUENCY SELECTION (GLOBAL) ---
st.sidebar.header("Filter Settings")
freq = st.sidebar.radio("Select Frequency:", ["Daily", "Weekly", "Monthly"], horizontal=True)

# Time-based Filtering Logic
if freq == "Daily":
    available_dates = sorted(kpi_raw['Date_Parsed'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Date:", available_dates, format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_time = kpi_raw[kpi_raw['Date_Parsed'] == sel]
    f_dsat_time = dsat_raw[dsat_raw['Date_Parsed'].dt.normalize() == sel]
elif freq == "Weekly":
    kpi_raw['W_Start'] = kpi_raw['Date_Parsed'] - pd.to_timedelta((kpi_raw['Date_Parsed'].dt.dayofweek + 1) % 7, unit='d')
    weeks = sorted(kpi_raw['W_Start'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Week Starting:", weeks, format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_time = kpi_raw[kpi_raw['W_Start'] == sel]
    dsat_raw['W_Start'] = dsat_raw['Date_Parsed'] - pd.to_timedelta((dsat_raw['Date_Parsed'].dt.dayofweek + 1) % 7, unit='d')
    f_dsat_time = dsat_raw[dsat_raw['W_Start'] == sel]
else: # Monthly
    kpi_raw['Month_Label'] = kpi_raw['Date_Parsed'].dt.strftime('%B %Y')
    months = kpi_raw.sort_values('Date_Parsed', ascending=False)['Month_Label'].dropna().unique()
    sel = st.sidebar.selectbox("Select Month:", months)
    f_kpi_time = kpi_raw[kpi_raw['Month_Label'] == sel]
    dsat_raw['Month_Label'] = dsat_raw['Date_Parsed'].dt.strftime('%B %Y')
    f_dsat_time = dsat_raw[dsat_raw['Month_Label'] == sel]

# --- 6. PERMISSIONS FILTERING ---
if level == "Admin":
    scope = st.sidebar.radio("View Scope", ["Entire Org", "Manager Team", "Individual Advisor"])
    if scope == "Entire Org":
        f_kpi, f_dsat = f_kpi_time, f_dsat_time
    elif scope == "Manager Team":
        mgr = st.sidebar.selectbox("Select Manager", team_db[team_db['Access Level'] == 'Manager']['Advisor Name'].unique())
        team_emails = team_db[team_db['Manager Name'] == mgr]['Email'].unique()
        f_kpi = f_kpi_time[f_kpi_time['Email'].isin(team_emails)]
        f_dsat = f_dsat_time[f_dsat_time['Email'].isin(team_emails)]
    else:
        adv = st.sidebar.selectbox("Select Advisor", sorted(kpi_raw['Advisor Name'].dropna().unique()))
        f_kpi = f_kpi_time[f_kpi_time['Advisor Name'] == adv]
        f_dsat = f_dsat_time[f_dsat_time['Advisor Name'] == adv]

elif level == "Manager":
    team_emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    mgr_view = st.sidebar.radio("Manager Scope", ["Team Summary", "Member Deep-dive"])
    if mgr_view == "Member Deep-dive":
        adv_name = st.sidebar.selectbox("Team Member", team_db[team_db['Email'].isin(team_emails)]['Advisor Name'])
        f_kpi = f_kpi_time[f_kpi_time['Advisor Name'] == adv_name]
        f_dsat = f_dsat_time[f_dsat_time['Advisor Name'] == adv_name]
    else:
        f_kpi = f_kpi_time[f_kpi_time['Email'].isin(team_emails)]
        f_dsat = f_dsat_time[f_dsat_time['Email'].isin(team_emails)]
else:
    f_kpi = f_kpi_time[f_kpi_time['Email'] == user['Email']]
    f_dsat = f_dsat_time[f_dsat_time['Email'] == user['Email']]

# --- 7. DASHBOARD HEADER ---
head1, head2 = st.columns([1, 6])
with head1: st.image(LOGO_URL, width=80)
with head2: st.header("HIGHLEVEL CS PERFORMANCE TRACKER")
st.caption(f"Welcome {user['Advisor Name']} | Access: {level} | Period: {sel}")

# --- 8. TABS ---
tab_titles = ["Performance Hub", "DSAT Analysis", "Detailed Logs"]
if level in ["Manager", "Admin"]:
    tab_titles.append("Leaderboards")
tab1, tab2, tab3, *tab4 = st.tabs(tab_titles)

with tab1:
    st.subheader(f"📊 Performance Overview ({freq})")
    st.info("Performance Narrative and Metric cards go here.")

with tab2:
    st.subheader("🚫 DSAT Analysis & Feedback")
    if not f_dsat.empty:
        dsat_cols = ['Timestamp', 'Advisor Name', 'DSAT chat link', 'Feedback']
        existing = [c for c in dsat_cols if c in f_dsat.columns]
        display_df = f_dsat[existing].copy()
        if 'Timestamp' in display_df.columns:
            display_df.rename(columns={'Timestamp': 'Date'}, inplace=True)
        
        if level in ["Manager", "Admin"]:
            st.data_editor(display_df, column_config={"DSAT chat link": st.column_config.LinkColumn("Chat Link")},
                           disabled=['Date', 'Advisor Name', 'DSAT chat link'], hide_index=True, use_container_width=True)
        else:
            st.dataframe(display_df, hide_index=True, use_container_width=True)
    else:
        st.write(f"No DSAT records found for the selected {freq} period.")

with tab3:
    st.subheader("📝 Detailed KPI Log")
    st.dataframe(f_kpi, hide_index=True, use_container_width=True)

if tab4:
    with tab4[0]:
        st.subheader("🏆 Organization Rankings & Audits")
        if level == "Admin":
            st.markdown("### 📈 Manager Feedback Completion Status")
            # Logic for audit chart based on filtered timeframe
            audit_df = f_dsat_time.merge(team_db[['Email', 'Manager Name']], on='Email', how='left')
            audit_df['Has Feedback'] = audit_df['Feedback'].fillna('').str.strip().astype(bool)
            stats = audit_df.groupby('Manager Name')['Has Feedback'].mean().reset_index()
            stats['Completion %'] = (stats['Has Feedback'] * 100).round(1)
            
            fig = px.bar(stats.sort_values('Completion %', ascending=False), x='Manager Name', y='Completion %', 
                         title=f"Coaching Status for {sel}", color='Completion %', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig, use_container_width=True)

st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
