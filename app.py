import streamlit as st
import pandas as pd
import plotly.express as px
import urllib.parse

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

# REPLACE THESE WITH YOUR GOOGLE FORM DETAILS
FORM_ID = "YOUR_FORM_ID_HERE"
ENTRY_ID_KEY = "entry.1111111"    # RecordKey ID
ENTRY_ID_FEEDBACK = "entry.2222222" # Feedback ID
ENTRY_ID_TYPE = "entry.3333333"     # Type ID

st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

# --- 2. HELPER FUNCTIONS ---
def parse_time_to_minutes(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    try:
        h, m = 0, 0
        parts = time_str.lower().split()
        for p in parts:
            if 'h' in p: h = int(p.replace('h', ''))
            elif 'm' in p: m = int(p.replace('m', ''))
        return (h * 60) + m
    except: return 0

def format_minutes_to_hours(total_minutes):
    if pd.isna(total_minutes) or total_minutes <= 0: return "0h 0m"
    return f"{int(total_minutes // 60)}h {int(total_minutes % 60)}m"

def generate_form_url(row):
    # Generates a pre-filled Google Form URL for feedback updates
    base = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url"
    params = {
        ENTRY_ID_KEY: row.get('RecordKey', ''),
        ENTRY_ID_FEEDBACK: row.get('Feedback', ''),
        ENTRY_ID_TYPE: row.get('Type', '')
    }
    return f"{base}&{urllib.parse.urlencode(params)}"

# --- 3. DATA LOADING & ROBUST MAPPING ---
@st.cache_data(ttl=60)
def load_data(url, sheet_type=None):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.replace('\ufeff', '').str.replace('"', '')
        
        mappings = {
            "KPI": {"Date_level - AS": "Date", "Agent Name": "Advisor Name", "IA": "IA_Hours", "Advisor Call Time ": "Advisor Call Time"},
            "TEAM": {"Manager": "Manager Name", "Access level": "Access Level", "Advisor Email": "Email"},
            "DSAT": {"Advisor Email": "Email", "Chat DSAT URL": "DSAT chat link", "Type": "Type"}
        }
        
        if sheet_type in mappings:
            df.rename(columns=mappings[sheet_type], inplace=True)
        
        if 'Email' not in df.columns and 'Advisor Email' in df.columns:
            df['Email'] = df['Advisor Email']
        
        if 'Email' in df.columns:
            df['Email'] = df['Email'].astype(str).str.strip().str.lower()
            
        if sheet_type == "KPI":
            df['IA_Mins'] = df['IA_Hours'].apply(parse_time_to_minutes) if 'IA_Hours' in df.columns else df['IA'].apply(parse_time_to_minutes)
            df['Call_Mins'] = df['Advisor Call Time'].apply(parse_time_to_minutes) if 'Advisor Call Time' in df.columns else 0
            df['Shift_Score'] = (df['Call_Mins'] / df['IA_Mins'] * 100).fillna(0)
            for col in ['Sent Rate %', 'Satisfied Survey %', 'Total Survey']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', '').str.strip(), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Error processing {sheet_type}: {e}")
        return pd.DataFrame()

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
if not st.session_state.auth:
    col1, col2 = st.columns([1, 5]); col1.image(LOGO_URL, width=100); col2.title("HIGHLEVEL CS PERFORMANCE TRACKER")
    with st.form("login"):
        e_in, p_in = st.text_input("Advisor Email").lower().strip(), st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            team_db = load_data(TEAM_URL, "TEAM")
            if not team_db.empty:
                user_match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str).str.strip() == str(p_in).strip())]
                if not user_match.empty: st.session_state.auth = user_match.iloc[0].to_dict(); st.rerun()
            st.error("Invalid credentials.")
    st.stop()

# --- 5. DATA PREP ---
user, kpi_raw, dsat_raw, team_db = st.session_state.auth, load_data(KPI_URL, "KPI"), load_data(DSAT_URL, "DSAT"), load_data(TEAM_URL, "TEAM")
level = user.get('Access Level', 'IC') 
kpi_raw['Date_Parsed'] = pd.to_datetime(kpi_raw['Date'], format="%b'%d'%y", errors='coerce')
dsat_raw['Date_Parsed'] = pd.to_datetime(dsat_raw['Timestamp'], errors='coerce')
if 'Processed' in dsat_raw.columns: dsat_raw = dsat_raw[dsat_raw['Processed'] != 'DUPLICATE']

# --- 6. GLOBAL FILTERS ---
st.sidebar.header("Filter Settings")
freq = st.sidebar.radio("Frequency:", ["Daily", "Weekly", "Monthly"], horizontal=True)
if freq == "Daily":
    available = sorted(kpi_raw['Date_Parsed'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Date:", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_time, f_dsat_time = kpi_raw[kpi_raw['Date_Parsed'] == sel], dsat_raw[dsat_raw['Date_Parsed'].dt.normalize() == sel]
elif freq == "Weekly":
    kpi_raw['W_Start'] = kpi_raw['Date_Parsed'] - pd.to_timedelta((kpi_raw['Date_Parsed'].dt.dayofweek + 1) % 7, unit='d')
    weeks = sorted(kpi_raw['W_Start'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Week Starting:", weeks, format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_time, f_dsat_time = kpi_raw[kpi_raw['W_Start'] == sel], dsat_raw[(dsat_raw['Date_Parsed'] >= sel) & (dsat_raw['Date_Parsed'] < sel + pd.Timedelta(days=7))]
else:
    kpi_raw['Month_Label'] = kpi_raw['Date_Parsed'].dt.strftime('%B %Y')
    months = kpi_raw.sort_values('Date_Parsed', ascending=False)['Month_Label'].dropna().unique()
    sel = st.sidebar.selectbox("Month:", months)
    f_kpi_time, f_dsat_time = kpi_raw[kpi_raw['Month_Label'] == sel], dsat_raw[dsat_raw['Date_Parsed'].dt.strftime('%B %Y') == sel]

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
        f_kpi, f_dsat = f_kpi_time[f_kpi_time['Advisor Name'] == adv], f_dsat_time[f_dsat_time['Email'].isin(team_db[team_db['Advisor Name']==adv]['Email'])]
elif level == "Manager":
    emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    sub = st.sidebar.radio("View", ["Team", "Drill-down"])
    if sub == "Drill-down":
        adv = st.sidebar.selectbox("Member", team_db[team_db['Email'].isin(emails)]['Advisor Name'])
        f_kpi, f_dsat = f_kpi_time[f_kpi_time['Advisor Name'] == adv], f_dsat_time[f_dsat_time['Email'].isin(team_db[team_db['Advisor Name']==adv]['Email'])]
    else: f_kpi, f_dsat = f_kpi_time[f_kpi_time['Email'].isin(emails)], f_dsat_time[f_dsat_time['Email'].isin(emails)]
else: f_kpi, f_dsat = f_kpi_time[f_kpi_time['Email'] == user['Email']], f_dsat_time[f_dsat_time['Email'] == user['Email']]

# --- 8. HEADER ---
c1, c2 = st.columns([1, 6]); c1.image(LOGO_URL, width=80); c2.header("HIGHLEVEL CS PERFORMANCE TRACKER")
st.caption(f"Welcome {user['Advisor Name']} | Access: {level} | Period: {sel}")

# --- 9. TABS ---
tabs = st.tabs(["Performance Hub", "DSAT Analysis"] + (["Leaderboards"] if level in ["Manager", "Admin"] else []))

with tabs[0]:
    avg_score, avg_ia = f_kpi['Shift_Score'].mean() if not f_kpi.empty else 0, f_kpi['IA_Mins'].mean() if not f_kpi.empty else 0
    avg_sent = f_kpi[f_kpi['Total Survey'] > 0]['Sent Rate %'].mean() if not f_kpi.empty else 0
    avg_sat = f_kpi[f_kpi['Total Survey'] > 0]['Satisfied Survey %'].mean() if not f_kpi.empty else 0
    st.markdown("### 📝 Performance Narrative")
    st.info(f"1. Overall Quality: Satisfaction rate is **{avg_sat:.1f}%** with a Survey Sent rate of **{avg_sent:.1f}%**.\n2. Productivity: Average IA was **{format_minutes_to_hours(avg_ia)}** (Shift Score: **{avg_score:.1f}%**).\n3. Alerts: You have **{len(f_dsat)}** DSAT records pending review.")
    
    m = st.columns(5)
    m[0].metric("Avg Shift Score", f"{avg_score:.1f}%"); m[1].metric("Avg IA Hours", format_minutes_to_hours(avg_ia))
    m[2].metric("Avg Sent Rate %", f"{avg_sent:.1f}%"); m[3].metric("Avg Satisfied Survey", f"{avg_sat:.1f}%")
    m[4].metric("Total Survey", int(f_kpi['Total Survey'].sum()) if not f_kpi.empty else 0)

    st.markdown("### 📈 Performance Trends")
    chart_data = f_kpi.groupby('Date_Parsed').mean(numeric_only=True).reset_index() if not f_kpi.empty else pd.DataFrame()
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(px.line(chart_data, x='Date_Parsed', y='Shift_Score', title="Shift Score Trend", markers=True), use_container_width=True)
        st.plotly_chart(px.line(chart_data, x='Date_Parsed', y='Satisfied Survey %', title="Satisfied Survey Trend", markers=True), use_container_width=True)
    with col_b:
        st.plotly_chart(px.line(chart_data, x='Date_Parsed', y='IA_Mins', title="IA Minutes Trend", markers=True), use_container_width=True)
        st.plotly_chart(px.line(chart_data, x='Date_Parsed', y='Sent Rate %', title="Survey Sent Trend", markers=True), use_container_width=True)

with tabs[1]:
    # DSAT SUMMARY
    total_d, con_d, uncon_d = len(f_dsat), len(f_dsat[f_dsat['Type'] == 'Controllable']), len(f_dsat[f_dsat['Type'] == 'Uncontrollable'])
    ds_1, ds_2, ds_3 = st.columns(3)
    ds_1.metric("Total DSATs", total_d); ds_2.metric("Controllable", con_d); ds_3.metric("Uncontrollable", uncon_d)
    
    if not f_dsat.empty:
        # Create Update Column
        if level in ["Manager", "Admin"]:
            f_dsat['Update Feedback'] = f_dsat.apply(generate_form_url, axis=1)
        
        cols = ['Timestamp', 'Advisor Name', 'DSAT chat link', 'Type', 'Feedback'] + (['Update Feedback'] if level in ["Manager", "Admin"] else [])
        df_view = f_dsat[[c for c in cols if c in f_dsat.columns]].copy()
        df_view.rename(columns={'Timestamp': 'Date'}, inplace=True)
        st.dataframe(df_view, column_config={"DSAT chat link": st.column_config.LinkColumn("View Chat"), "Update Feedback": st.column_config.LinkColumn("Update Form")}, hide_index=True, use_container_width=True)

if level in ["Manager", "Admin"] and len(tabs) > 2:
    with tabs[2]:
        st.subheader("🏆 Team Leaderboards")
        # Aggregations for Leaderboard
        ldb = f_kpi.groupby('Advisor Name').agg({'Sent Rate %':'mean','Satisfied Survey %':'mean','Q/A Calls':'sum','OB Calls':'sum','Total Survey':'sum'}).reset_index()
        
        c_l1, c_l2, c_l3 = st.columns(3)
        with c_l1:
            st.markdown("#### 🏆 Success Champions")
            sc = ldb[(ldb['Sent Rate %'] >= 85) & (ldb['Satisfied Survey %'] > 90)].sort_values(['Satisfied Survey %','Sent Rate %'], ascending=False)
            st.dataframe(sc[['Advisor Name', 'Satisfied Survey %', 'Sent Rate %']], hide_index=True)
            st.markdown("#### Avg Satisfied Survey%")
            st.dataframe(ldb.sort_values('Satisfied Survey %', ascending=False)[['Advisor Name', 'Satisfied Survey %']], hide_index=True)
        with c_l2:
            st.markdown("#### Total QA Calls")
            st.dataframe(ldb.sort_values('Q/A Calls', ascending=False)[['Advisor Name', 'Q/A Calls']], hide_index=True)
            st.markdown("#### Avg Survey Sent %")
            st.dataframe(ldb.sort_values('Sent Rate %', ascending=False)[['Advisor Name', 'Sent Rate %']], hide_index=True)
        with c_l3:
            st.markdown("#### Total OB Calls")
            st.dataframe(ldb.sort_values('OB Calls', ascending=False)[['Advisor Name', 'OB Calls']], hide_index=True)

st.sidebar.divider(); st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'auth': None}))
