import streamlit as st
import pandas as pd
import plotly.express as px
import urllib.parse

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

# REPLACE WITH YOUR ACTUAL GOOGLE FORM CONFIG
FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY = "entry.1" # RecordKey
ENTRY_FEEDBACK = "entry.2" # Feedback
ENTRY_TYPE = "entry.3" # Type (Controllable/Uncontrollable)

st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

# --- 2. HELPERS ---
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
    base = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url"
    params = {ENTRY_KEY: row.get('RecordKey',''), ENTRY_FEEDBACK: row.get('Feedback',''), ENTRY_TYPE: row.get('Type','')}
    return f"{base}&{urllib.parse.urlencode(params)}"

# --- 3. DATA LOADING ---
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
        if sheet_type in mappings: df.rename(columns=mappings[sheet_type], inplace=True)
        if 'Email' not in df.columns and 'Advisor Email' in df.columns: df['Email'] = df['Advisor Email']
        if 'Email' in df.columns: df['Email'] = df['Email'].astype(str).str.strip().str.lower()
            
        if sheet_type == "KPI":
            df['IA_Mins'] = df['IA'].apply(parse_time_to_minutes) if 'IA' in df.columns else df['IA_Hours'].apply(parse_time_to_minutes)
            df['Call_Mins'] = df['Advisor Call Time'].apply(parse_time_to_minutes)
            df['Shift_Score'] = (df['Call_Mins'] / df['IA_Mins'] * 100).fillna(0)
            for col in ['Sent Rate %', 'Satisfied Survey %', 'Total Survey']:
                if col in df.columns: df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Error loading {sheet_type}: {e}"); return pd.DataFrame()

# --- 4. AUTH & PREP ---
if 'auth' not in st.session_state: st.session_state.auth = None
if not st.session_state.auth:
    col1, col2 = st.columns([1, 5]); col1.image(LOGO_URL, width=100); col2.title("HIGHLEVEL CS PERFORMANCE TRACKER")
    with st.form("login"):
        e_in, p_in = st.text_input("Advisor Email").lower().strip(), st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            tdb = load_data(TEAM_URL, "TEAM")
            user = tdb[(tdb['Email'] == e_in) & (tdb['Password'].astype(str).str.strip() == str(p_in).strip())]
            if not user.empty: st.session_state.auth = user.iloc[0].to_dict(); st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

user, kpi_raw, dsat_raw, team_db = st.session_state.auth, load_data(KPI_URL, "KPI"), load_data(DSAT_URL, "DSAT"), load_data(TEAM_URL, "TEAM")
kpi_raw['Date_Parsed'] = pd.to_datetime(kpi_raw['Date'], format="%b'%d'%y", errors='coerce')
dsat_raw['Date_Parsed'] = pd.to_datetime(dsat_raw['Timestamp'], errors='coerce')
if 'Processed' in dsat_raw.columns: dsat_raw = dsat_raw[dsat_raw['Processed'] != 'DUPLICATE']

# --- 5. FILTERS & PERMISSIONS ---
freq = st.sidebar.radio("Frequency:", ["Daily", "Weekly", "Monthly"], horizontal=True)
if freq == "Daily":
    available = sorted(kpi_raw['Date_Parsed'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Date:", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_t, f_dsat_t = kpi_raw[kpi_raw['Date_Parsed'] == sel], dsat_raw[dsat_raw['Date_Parsed'].dt.normalize() == sel]
elif freq == "Weekly":
    kpi_raw['W_Start'] = kpi_raw['Date_Parsed'] - pd.to_timedelta((kpi_raw['Date_Parsed'].dt.dayofweek + 1) % 7, unit='d')
    sel = st.sidebar.selectbox("Week Starting:", sorted(kpi_raw['W_Start'].dropna().unique(), reverse=True), format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_t, f_dsat_t = kpi_raw[kpi_raw['W_Start'] == sel], dsat_raw[(dsat_raw['Date_Parsed'] >= sel) & (dsat_raw['Date_Parsed'] < sel + pd.Timedelta(days=7))]
else:
    kpi_raw['Month_Label'] = kpi_raw['Date_Parsed'].dt.strftime('%B %Y')
    sel = st.sidebar.selectbox("Month:", kpi_raw.sort_values('Date_Parsed', ascending=False)['Month_Label'].dropna().unique())
    f_kpi_t, f_dsat_t = kpi_raw[kpi_raw['Month_Label'] == sel], dsat_raw[dsat_raw['Date_Parsed'].dt.strftime('%B %Y') == sel]

# Access Logic
level = user['Access Level']
if level == "Admin":
    sc = st.sidebar.radio("Scope", ["Global", "Manager", "Advisor"])
    if sc == "Global": f_kpi, f_dsat = f_kpi_t, f_dsat_t
    elif sc == "Manager":
        m = st.sidebar.selectbox("Manager", team_db[team_db['Access Level'] == 'Manager']['Advisor Name'].unique())
        ems = team_db[team_db['Manager Name'] == m]['Email'].unique()
        f_kpi, f_dsat = f_kpi_t[f_kpi_t['Email'].isin(ems)], f_dsat_t[f_dsat_t['Email'].isin(ems)]
    else:
        a = st.sidebar.selectbox("Advisor", sorted(kpi_raw['Advisor Name'].dropna().unique()))
        f_kpi, f_dsat = f_kpi_t[f_kpi_t['Advisor Name'] == a], f_dsat_t[f_dsat_t['Email'].isin(team_db[team_db['Advisor Name']==a]['Email'])]
elif level == "Manager":
    ems = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    sub = st.sidebar.radio("View", ["Team", "Drill-down"])
    if sub == "Drill-down":
        a = st.sidebar.selectbox("Member", team_db[team_db['Email'].isin(ems)]['Advisor Name'])
        f_kpi, f_dsat = f_kpi_t[f_kpi_t['Advisor Name'] == a], f_dsat_t[f_dsat_t['Email'].isin(team_db[team_db['Advisor Name']==a]['Email'])]
    else: f_kpi, f_dsat = f_kpi_t[f_kpi_t['Email'].isin(ems)], f_dsat_t[f_dsat_t['Email'].isin(ems)]
else: f_kpi, f_dsat = f_kpi_t[f_kpi_t['Email'] == user['Email']], f_dsat_t[f_dsat_t['Email'] == user['Email']]

# --- 6. TABS & UI ---
st.header("HIGHLEVEL CS PERFORMANCE TRACKER")
st.caption(f"Welcome {user['Advisor Name']} | Access: {level} | Period: {sel}")
tabs = st.tabs(["Performance Hub", "DSAT Analysis"] + (["Leaderboards"] if level in ["Manager", "Admin"] else []))

with tabs[0]:
    avg_score, avg_ia = f_kpi['Shift_Score'].mean() if not f_kpi.empty else 0, f_kpi['IA_Mins'].mean() if not f_kpi.empty else 0
    avg_sent = f_kpi[f_kpi['Total Survey'] > 0]['Sent Rate %'].mean() if not f_kpi.empty else 0
    avg_sat = f_kpi[f_kpi['Total Survey'] > 0]['Satisfied Survey %'].mean() if not f_kpi.empty else 0
    
    st.markdown("### 📝 Performance Narrative")
    st.info(f"1. Quality: Satisfaction at **{avg_sat:.2f}%** with **{avg_sent:.2f}%** sent rate.\n2. Efficiency: IA availability **{format_minutes_to_hours(avg_ia)}** (Shift Score: **{avg_score:.2f}%**).\n3. Alert: **{len(f_dsat)}** DSAT records recorded.")
    
    m = st.columns(5)
    m[0].metric("Avg Shift Score", f"{avg_score:.2f}%")
    m[1].metric("Avg IA Hours", format_minutes_to_hours(avg_ia))
    m[2].metric("Avg Sent Rate %", f"{avg_sent:.2f}%")
    m[3].metric("Avg Satisfied Survey", f"{avg_sat:.2f}%")
    m[4].metric("Total Survey", int(f_kpi['Total Survey'].sum()))

    c_a, c_b = st.columns(2)
    chart_d = f_kpi.groupby('Date_Parsed').mean(numeric_only=True).reset_index() if not f_kpi.empty else pd.DataFrame()
    with c_a:
        st.plotly_chart(px.line(chart_d, x='Date_Parsed', y='Shift_Score', title="Shift Score Trend", markers=True), use_container_width=True)
        st.plotly_chart(px.line(chart_d, x='Date_Parsed', y='Satisfied Survey %', title="Satisfied Survey Trend", markers=True), use_container_width=True)
    with c_b:
        st.plotly_chart(px.line(chart_d, x='Date_Parsed', y='IA_Mins', title="IA Minutes Trend", markers=True), use_container_width=True)
        st.plotly_chart(px.line(chart_d, x='Date_Parsed', y='Sent Rate %', title="Survey Sent Trend", markers=True), use_container_width=True)

with tabs[1]:
    st.markdown("### 🚫 DSAT Analysis")
    # Summary Section
    s1, s2, s3 = st.columns(3)
    s1.metric("Total Received", len(f_dsat))
    s2.metric("Controllable", len(f_dsat[f_dsat['Type'] == 'Controllable']))
    s3.metric("Uncontrollable", len(f_dsat[f_dsat['Type'] == 'Uncontrollable']))
    
    if not f_dsat.empty:
        if level in ["Manager", "Admin"]: f_dsat['Update Action'] = f_dsat.apply(generate_form_url, axis=1)
        # Safe column subsetting
        disp_cols = ['Timestamp', 'DSAT chat link', 'Feedback', 'Type'] + (['Update Action'] if level in ["Manager", "Admin"] else [])
        f_disp = f_dsat[[c for c in disp_cols if c in f_dsat.columns]].copy()
        f_disp.rename(columns={'Timestamp': 'Date'}, inplace=True)
        
        st.dataframe(f_disp, column_config={
            "DSAT chat link": st.column_config.LinkColumn("View Chat"),
            "Update Action": st.column_config.LinkColumn("Submit Feedback/Type")
        }, hide_index=True, use_container_width=True)

if level in ["Manager", "Admin"] and len(tabs) > 2:
    with tabs[2]:
        st.markdown("#### 🏆 Leaderboards")
        st.caption("Criteria: Survey Sent Rate ≥ 85% and Satisfied Survey > 90% (Excludes 0-survey days)")
        ldb = f_kpi.groupby('Advisor Name').agg({'Sent Rate %':'mean','Satisfied Survey %':'mean','Q/A Calls':'sum','OB Calls':'sum'}).reset_index()
        l1, l2, l3 = st.columns(3)
        with l1:
            st.write("**Success Champions**")
            sc = ldb[(ldb['Sent Rate %'] >= 85) & (ldb['Satisfied Survey %'] > 90)].sort_values(['Satisfied Survey %','Sent Rate %'], ascending=False)
            st.dataframe(sc[['Advisor Name', 'Satisfied Survey %', 'Sent Rate %']].round(2), hide_index=True)
        with l2:
            st.write("**Avg Satisfied Survey %**")
            st.dataframe(ldb.sort_values('Satisfied Survey %', ascending=False)[['Advisor Name', 'Satisfied Survey %']].round(2), hide_index=True)
            st.write("**Avg Survey Sent %**")
            st.dataframe(ldb.sort_values('Sent Rate %', ascending=False)[['Advisor Name', 'Sent Rate %']].round(2), hide_index=True)
        with l3:
            st.write("**Total QA Calls**")
            st.dataframe(ldb.sort_values('Q/A Calls', ascending=False)[['Advisor Name', 'Q/A Calls']], hide_index=True)
            st.write("**Total OB Calls**")
            st.dataframe(ldb.sort_values('OB Calls', ascending=False)[['Advisor Name', 'OB Calls']], hide_index=True)

st.sidebar.divider(); st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'auth': None}))
