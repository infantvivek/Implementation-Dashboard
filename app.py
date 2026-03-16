import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

# --- 2. HELPER FUNCTIONS ---
def parse_time_to_minutes(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    try:
        h, m = 0, 0
        parts = time_str.split()
        for p in parts:
            if 'h' in p: h = int(p.replace('h', ''))
            elif 'm' in p: m = int(p.replace('m', ''))
        return (h * 60) + m
    except: return 0

def format_minutes_to_hours(total_minutes):
    if pd.isna(total_minutes) or total_minutes <= 0: return "0h 0m"
    return f"{int(total_minutes // 60)}h {int(total_minutes % 60)}m"

# --- 3. DATA LOADING & CLEANING ---
@st.cache_data(ttl=60)
def load_data(url, sheet_type=None):
    try:
        df = pd.read_csv(url)
        # Aggressive header cleaning to fix KeyError
        df.columns = df.columns.str.strip().str.replace('\ufeff', '').str.replace('"', '')
        
        if 'Advisor Email' in df.columns:
            df['Email'] = df['Advisor Email'].astype(str).str.strip().str.lower()
        elif 'Email' in df.columns:
            df['Email'] = df['Email'].astype(str).str.strip().str.lower()
            
        # Specific KPI numeric parsing
        if sheet_type == "KPI":
            df['IA_Mins'] = df['IA_Hours'].apply(parse_time_to_minutes)
            df['Call_Mins'] = df['Advisor Call Time'].apply(parse_time_to_minutes)
            df['Shift_Score'] = (df['Call_Mins'] / df['IA_Mins'] * 100).fillna(0)
            for col in ['Sent Rate %', 'Satisfied Survey %', 'Total Survey']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', '').str.strip(), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Error loading {sheet_type}: {e}")
        return pd.DataFrame()

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None

if not st.session_state.auth:
    col1, col2 = st.columns([1, 5])
    with col1: st.image(LOGO_URL, width=100)
    with col2: st.title("HIGHLEVEL CS PERFORMANCE TRACKER")
    with st.form("login"):
        e_in = st.text_input("Advisor Email").lower().strip()
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            team_db = load_data(TEAM_URL, "TEAM")
            if not team_db.empty:
                user_match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str).str.strip() == p_in)]
                if not user_match.empty:
                    st.session_state.auth = user_match.iloc[0].to_dict()
                    st.rerun()
            st.error("Invalid credentials.")
    st.stop()

# --- 5. DATA PREP ---
user = st.session_state.auth
level = user.get('Access Level', 'IC') 
kpi_raw = load_data(KPI_URL, "KPI")
dsat_raw = load_data(DSAT_URL, "DSAT")
team_db = load_data(TEAM_URL, "TEAM")

# Standardize Dates
kpi_raw['Date_Parsed'] = pd.to_datetime(kpi_raw['Date'], format="%b'%d'%y", errors='coerce')
dsat_raw['Date_Parsed'] = pd.to_datetime(dsat_raw['Timestamp'], errors='coerce')

if 'Processed' in dsat_raw.columns:
    dsat_raw = dsat_raw[dsat_raw['Processed'] != 'DUPLICATE']

# --- 6. GLOBAL FILTERS ---
st.sidebar.header("Filter Settings")
freq = st.sidebar.radio("Frequency:", ["Daily", "Weekly", "Monthly"], horizontal=True)

if freq == "Daily":
    available = sorted(kpi_raw['Date_Parsed'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Date:", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_time = kpi_raw[kpi_raw['Date_Parsed'] == sel]
    f_dsat_time = dsat_raw[dsat_raw['Date_Parsed'].dt.normalize() == sel]
elif freq == "Weekly":
    kpi_raw['W_Start'] = kpi_raw['Date_Parsed'] - pd.to_timedelta((kpi_raw['Date_Parsed'].dt.dayofweek + 1) % 7, unit='d')
    weeks = sorted(kpi_raw['W_Start'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Week Starting:", weeks, format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_time = kpi_raw[kpi_raw['W_Start'] == sel]
    dsat_raw['W_Start'] = dsat_raw['Date_Parsed'] - pd.to_timedelta((dsat_raw['Date_Parsed'].dt.dayofweek + 1) % 7, unit='d')
    f_dsat_time = dsat_raw[dsat_raw['W_Start'] == sel]
else:
    kpi_raw['Month_Label'] = kpi_raw['Date_Parsed'].dt.strftime('%B %Y')
    months = kpi_raw.sort_values('Date_Parsed', ascending=False)['Month_Label'].dropna().unique()
    sel = st.sidebar.selectbox("Month:", months)
    f_kpi_time = kpi_raw[kpi_raw['Month_Label'] == sel]
    dsat_raw['Month_Label'] = dsat_raw['Date_Parsed'].dt.strftime('%B %Y')
    f_dsat_time = dsat_raw[dsat_raw['Month_Label'] == sel]

# --- 7. PERMISSIONS FILTER ---
if level == "Admin":
    scope = st.sidebar.radio("Scope", ["Global", "Manager Team", "Individual"])
    if scope == "Global": f_kpi, f_dsat = f_kpi_time, f_dsat_time
    elif scope == "Manager Team":
        mgr = st.sidebar.selectbox("Manager", team_db[team_db['Access Level'] == 'Manager']['Advisor Name'].unique())
        emails = team_db[team_db['Manager Name'] == mgr]['Email'].unique()
        f_kpi, f_dsat = f_kpi_time[f_kpi_time['Email'].isin(emails)], f_dsat_time[f_dsat_time['Email'].isin(emails)]
    else:
        adv = st.sidebar.selectbox("Advisor", sorted(kpi_raw['Advisor Name'].dropna().unique()))
        f_kpi, f_dsat = f_kpi_time[f_kpi_time['Advisor Name'] == adv], f_dsat_time[f_dsat_time['Advisor Name'] == adv]
elif level == "Manager":
    emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    sub = st.sidebar.radio("View", ["Team", "Drill-down"])
    if sub == "Drill-down":
        adv = st.sidebar.selectbox("Member", team_db[team_db['Email'].isin(emails)]['Advisor Name'])
        f_kpi, f_dsat = f_kpi_time[f_kpi_time['Advisor Name'] == adv], f_dsat_time[f_dsat_time['Advisor Name'] == adv]
    else:
        f_kpi, f_dsat = f_kpi_time[f_kpi_time['Email'].isin(emails)], f_dsat_time[f_dsat_time['Email'].isin(emails)]
else:
    f_kpi, f_dsat = f_kpi_time[f_kpi_time['Email'] == user['Email']], f_dsat_time[f_dsat_time['Email'] == user['Email']]

# --- 8. TABS ---
head1, head2 = st.columns([1, 6])
with head1: st.image(LOGO_URL, width=80)
with head2: st.header("HIGHLEVEL CS PERFORMANCE TRACKER")
st.caption(f"Welcome {user['Advisor Name']} | Access: {level} | Period: {sel}")

tabs = st.tabs(["Performance Hub", "DSAT Analysis", "Detailed Logs"] + (["Leaderboards"] if level in ["Manager", "Admin"] else []))

with tabs[0]:
    # --- PERFORMANCE SUMMARY ---
    avg_score = f_kpi['Shift_Score'].mean()
    avg_ia = f_kpi['IA_Mins'].mean()
    avg_sent = f_kpi[f_kpi['Total Survey'] > 0]['Sent Rate %'].mean()
    avg_sat = f_kpi[f_kpi['Total Survey'] > 0]['Satisfied Survey %'].mean()
    
    m = st.columns(5)
    m[0].metric("Avg Shift Score", f"{avg_score:.1f}%", delta="Goal: >80%")
    m[1].metric("Avg IA Hours", format_minutes_to_hours(avg_ia), delta="Goal: >6h")
    m[2].metric("Avg Sent Rate %", f"{avg_sent:.1f}%", delta="Goal: >=85%")
    m[3].metric("Avg Satisfied Survey", f"{avg_sat:.1f}%", delta="Goal: >90%")
    m[4].metric("Total Survey", int(f_kpi['Total Survey'].sum()))
    
    # Trends
    chart_data = f_kpi.groupby('Date_Parsed').mean(numeric_only=True).reset_index() if level in ["Admin", "Manager"] else f_kpi
    st.plotly_chart(px.line(chart_data, x='Date_Parsed', y='Shift_Score', title="Shift Score Trend", markers=True), use_container_width=True)

with tabs[1]:
    if not f_dsat.empty:
        df_view = f_dsat[['Timestamp', 'Advisor Name', 'DSAT chat link', 'Feedback']].copy()
        df_view.rename(columns={'Timestamp': 'Date'}, inplace=True)
        if level in ["Manager", "Admin"]:
            st.data_editor(df_view, column_config={"DSAT chat link": st.column_config.LinkColumn("Chat Link")}, hide_index=True, use_container_width=True)
        else:
            st.dataframe(df_view, hide_index=True, use_container_width=True)
    else: st.write("No DSAT records found.")

with tabs[2]:
    st.dataframe(f_kpi, hide_index=True, use_container_width=True)

if level in ["Manager", "Admin"]:
    with tabs[3]:
        if level == "Admin":
            audit = f_dsat_time.merge(team_db[['Email', 'Manager Name']], on='Email', how='left')
            audit['Coached'] = audit['Feedback'].fillna('').str.strip().astype(bool)
            stats = audit.groupby('Manager Name')['Coached'].mean().reset_index()
            st.plotly_chart(px.bar(stats, x='Manager Name', y='Coached', title="Coaching Completion %", range_y=[0, 1]), use_container_width=True)

st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
    
