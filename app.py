import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import urllib.parse
from streamlit.components.v1 import iframe

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

# PRE-FILLED FORM CONFIG
FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY = "entry.1"
ENTRY_FEEDBACK = "entry.2"
ENTRY_TYPE = "entry.3"

st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

# --- 2. HELPERS & DIALOG ---
def parse_time_to_minutes(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    try:
        h, m = 0, 0
        parts = str(time_str).lower().split()
        for p in parts:
            if 'h' in p: h = int(p.replace('h', ''))
            elif 'm' in p: m = int(p.replace('m', ''))
        return (h * 60) + m
    except: return 0

def format_minutes_to_hours(total_minutes):
    if pd.isna(total_minutes) or total_minutes <= 0: return "0h 0m"
    return f"{int(total_minutes // 60)}h {int(total_minutes % 60)}m"

def generate_form_url(row):
    base = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?embedded=true&usp=pp_url"
    params = {
        ENTRY_KEY: row.get('RecordKey',''), 
        ENTRY_FEEDBACK: row.get('Feedback','') if pd.notna(row.get('Feedback')) else '', 
        ENTRY_TYPE: row.get('Type','') if pd.notna(row.get('Type')) else ''
    }
    return f"{base}&{urllib.parse.urlencode(params)}"

@st.dialog("Update DSAT Record", width="large")
def open_form_dialog(url):
    st.components.v1.iframe(url, height=700, scrolling=True)
    if st.button("Close & Refresh Dashboard"):
        st.rerun()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data(url, sheet_type=None):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '')
        mappings = {
            "KPI": {"Date_level - AS": "Date", "Agent Name": "Advisor Name", "IA": "IA_Hours", "Advisor Call Time ": "Advisor Call Time", "Manager": "Manager Name"},
            "TEAM": {"Manager": "Manager Name", "Access level": "Access Level", "Advisor Email": "Email"},
            "DSAT": {"Advisor Email": "Email", "Chat DSAT URL": "DSAT chat link", "Manager": "Manager Name"}
        }
        if sheet_type in mappings: df = df.rename(columns=mappings[sheet_type])
        if 'Email' in df.columns: df['Email'] = df['Email'].astype(str).str.strip().str.lower()
        
        if sheet_type == "KPI":
            df['IA_Mins'] = df['IA_Hours'].apply(parse_time_to_minutes) if 'IA_Hours' in df.columns else 0
            df['Call_Mins'] = df['Advisor Call Time'].apply(parse_time_to_minutes) if 'Advisor Call Time' in df.columns else 0
            # FIX: Prevent INF by checking for 0 IA Mins
            df['Shift_Score'] = np.where(df['IA_Mins'] > 0, (df['Call_Mins'] / df['IA_Mins'] * 100), 0)
            for col in ['Sent Rate %', 'Satisfied Survey %', 'Total Survey', 'Q/A Calls', 'OB Calls']:
                if col in df.columns: df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', '').str.strip(), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Error loading {sheet_type}: {e}"); return pd.DataFrame()

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
if not st.session_state.auth:
    c1, c2 = st.columns([1, 5]); c1.image(LOGO_URL, width=100); c2.title("HIGHLEVEL CS PERFORMANCE TRACKER")
    with st.form("login"):
        e_in, p_in = st.text_input("Work Email").lower().strip(), st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            team_db = load_data(TEAM_URL, "TEAM")
            user_match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str).str.strip() == str(p_in).strip())]
            if not user_match.empty: st.session_state.auth = user_match.iloc[0].to_dict(); st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. DATA PREP ---
user, kpi_raw, dsat_raw, team_db = st.session_state.auth, load_data(KPI_URL, "KPI"), load_data(DSAT_URL, "DSAT"), load_data(TEAM_URL, "TEAM")
level = user.get('Access Level', 'IC') 

kpi_raw['Date_Parsed'] = pd.to_datetime(kpi_raw['Date'], format="%b'%d'%y", errors='coerce')
dsat_raw['Date_Parsed'] = pd.to_datetime(dsat_raw['Timestamp'], errors='coerce')
if 'Processed' in dsat_raw.columns: dsat_raw = dsat_raw[dsat_raw['Processed'] != 'DUPLICATE']

# Ensure Manager/Advisor links are available for Sr. Manager Filtering
if 'Advisor Name' not in dsat_raw.columns:
    dsat_raw = dsat_raw.merge(team_db[['Email', 'Advisor Name', 'Manager Name']], on='Email', how='left')

# --- 6. HIERARCHY FILTERS ---
st.sidebar.header("Hierarchy & Time")
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

# 1. Sr. Manager Filter for Admins
if level == "Admin":
    sr_mgr = st.sidebar.selectbox("Sr. Manager Team", ["All Teams", "Jarvis Sokolowich", "Sumit Ludhwani"])
    if sr_mgr != "All Teams":
        managers = team_db[team_db['Manager Name'] == sr_mgr]['Advisor Name'].unique()
        m_filter = st.sidebar.selectbox(f"Managers under {sr_mgr}", ["All"] + list(managers))
        if m_filter == "All":
            emails = team_db[team_db['Manager Name'] == sr_mgr]['Email'].unique()
        else:
            emails = team_db[team_db['Manager Name'] == m_filter]['Email'].unique()
        f_kpi, f_dsat = f_kpi_t[f_kpi_t['Email'].isin(emails)], f_dsat_t[f_dsat_t['Email'].isin(emails)]
    else:
        f_kpi, f_dsat = f_kpi_t, f_dsat_t

elif level == "Manager":
    emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    f_kpi, f_dsat = f_kpi_t[f_kpi_t['Email'].isin(emails)], f_dsat_t[f_dsat_t['Email'].isin(emails)]
else:
    f_kpi, f_dsat = f_kpi_t[f_kpi_t['Email'] == user['Email']], f_dsat_t[f_dsat_t['Email'] == user['Email']]

# --- 7. TABS ---
head1, head2 = st.columns([1, 6]); head1.image(LOGO_URL, width=80); head2.header("HIGHLEVEL CS PERFORMANCE TRACKER")
st.caption(f"Logged in as: {user['Advisor Name']} | Period: {sel}")

tabs = st.tabs(["Performance Hub", "DSAT Analysis"] + (["Leaderboards"] if level in ["Manager", "Admin"] else []))

with tabs[0]:
    # Exclude 0 IA mins from averages to prevent skewed data
    active_kpi = f_kpi[f_kpi['IA_Mins'] > 0]
    avg_score = active_kpi['Shift_Score'].mean() if not active_kpi.empty else 0
    avg_sent = f_kpi[f_kpi['Total Survey'] > 0]['Sent Rate %'].mean() if not f_kpi.empty else 0
    avg_sat = f_kpi[f_kpi['Total Survey'] > 0]['Satisfied Survey %'].mean() if not f_kpi.empty else 0
    
    st.info(f"Summary: Quality is at **{avg_sat:.2f}%** with **{avg_sent:.2f}%** survey sent rate. Average Shift Score: **{avg_score:.2f}%**.")
    m = st.columns(4)
    m[0].metric("Avg Shift Score", f"{avg_score:.2f}%"); m[1].metric("Avg Sent Rate", f"{avg_sent:.2f}%")
    m[2].metric("Avg Satisfied Survey", f"{avg_sat:.2f}%"); m[3].metric("Total Survey", int(f_kpi['Total Survey'].sum()))

    st.markdown("### 📈 Performance Trends")
    # 2. Performance Trends Graphs
    trend_data = f_kpi.groupby('Date_Parsed').mean(numeric_only=True).reset_index()
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.line(trend_data, x='Date_Parsed', y='Shift_Score', title="Shift Score Trend", markers=True), use_container_width=True)
        st.plotly_chart(px.line(trend_data, x='Date_Parsed', y='Satisfied Survey %', title="Satisfied Survey Trend", markers=True), use_container_width=True)
    with c2:
        st.plotly_chart(px.line(trend_data, x='Date_Parsed', y='IA_Mins', title="IA Minutes Trend", markers=True), use_container_width=True)
        st.plotly_chart(px.line(trend_data, x='Date_Parsed', y='Sent Rate %', title="Survey Sent Trend", markers=True), use_container_width=True)

with tabs[1]:
    st.markdown("### 🚫 DSAT Analysis & Audit")
    # 2. Summary with Pending Count
    pending = len(f_dsat[f_dsat['Feedback'].isna() | (f_dsat['Feedback'].astype(str).str.strip() == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSATs", len(f_dsat))
    s2.metric("Feedback Pending", pending, delta=f"{pending} items", delta_color="inverse")
    s3.metric("Controllable", len(f_dsat[f_dsat['Type'] == 'Controllable']))
    s4.metric("Uncontrollable", len(f_dsat[f_dsat['Type'] == 'Uncontrollable']))
    
    st.write("---")
    if not f_dsat.empty:
        # 3. Enhanced Table View
        col_w = [1.5, 2, 2, 1.5, 1.5, 3, 1.2]
        h = st.columns(col_w)
        h[0].write("**Date**"); h[1].write("**Advisor**"); h[2].write("**Manager**")
        h[3].write("**Link**"); h[4].write("**Type**"); h[5].write("**Feedback**"); h[6].write("**Action**")

        for _, row in f_dsat.iterrows():
            fb = row['Feedback'] if pd.notna(row['Feedback']) and str(row['Feedback']).strip() != "" else "-"
            tp = row['Type'] if pd.notna(row['Type']) and str(row['Type']).strip() != "" else "-"
            mgr = row['Manager Name'] if 'Manager Name' in row else "N/A"
            r = st.columns(col_w)
            r[0].write(str(row['Timestamp'])[:10]); r[1].write(row['Advisor Name']); r[2].write(mgr)
            r[3].markdown(f"[Chat]({row['DSAT chat link']})"); r[4].write(tp); r[5].write(fb)
            if r[6].button("Update", key=f"btn_{row['RecordKey']}"):
                open_form_dialog(generate_form_url(row))
    else: st.write("No DSAT records found.")

if level in ["Manager", "Admin"] and len(tabs) > 2:
    with tabs[2]:
        st.markdown("#### 🏆 Leaderboards")
        st.write("**Criteria: Survey Sent Rate ≥ 85% and Satisfied Survey > 90% (Excluding 0-survey days)**")
        ldb = f_kpi[f_kpi['Total Survey'] > 0].groupby('Advisor Name').agg({
            'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'
        }).reset_index().round(2)
        
        c_l1, c_l2, c_l3 = st.columns(3)
        with c_l1:
            st.write("**Success Champions**")
            sc = ldb[(ldb['Sent Rate %'] >= 85) & (ldb['Satisfied Survey %'] > 90)].sort_values('Satisfied Survey %', ascending=False)
            st.dataframe(sc[['Advisor Name', 'Satisfied Survey %', 'Sent Rate %']], hide_index=True)
        with c_l2:
            st.write("**Avg Satisfied %**"); st.dataframe(ldb.sort_values('Satisfied Survey %', ascending=False)[['Advisor Name', 'Satisfied Survey %']], hide_index=True)
            st.write("**Total QA Calls**"); st.dataframe(ldb.sort_values('Q/A Calls', ascending=False)[['Advisor Name', 'Q/A Calls']], hide_index=True)
        with c_l3:
            st.write("**Avg Sent %**"); st.dataframe(ldb.sort_values('Sent Rate %', ascending=False)[['Advisor Name', 'Sent Rate %']], hide_index=True)
            st.write("**Total OB Calls**"); st.dataframe(ldb.sort_values('OB Calls', ascending=False)[['Advisor Name', 'OB Calls']], hide_index=True)

st.sidebar.divider(); st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'auth': None}))
