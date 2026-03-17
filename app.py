import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
from streamlit.components.v1 import iframe

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

# --- 2. GHL DYNAMIC THEME ---
st.markdown("""
    <style>
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 180px; height: 60px; margin-left: 20px; margin-top: 20px; filter: invert(1) brightness(2);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; }
    div.stInfo { background-color: rgba(0, 82, 255, 0.08); border-left: 5px solid #0052FF; color: var(--text-color); border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA LOADER ---
@st.cache_data(ttl=60)
def load_and_clean_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '')
        if 'Email' in df.columns:
            df['Email'] = df['Email'].astype(str).str.strip().str.lower()
        if 'Advisor Email' in df.columns:
            df['Advisor Email'] = df['Advisor Email'].astype(str).str.strip().str.lower()
        return df
    except:
        return pd.DataFrame()

def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    parts = time_str.lower().split()
    for p in parts:
        if 'h' in p: h = int(p.replace('h', ''))
        elif 'm' in p: m = int(p.replace('m', ''))
    return (h * 60) + m

# --- 4. GAUGE GENERATOR ---
def create_ghl_gauge(title, value, target=None, is_percent=True, color_steps=False):
    steps = [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}] if color_steps else []
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number = {'suffix': "%" if is_percent else "", 'font': {'color': '#0052FF', 'size': 35}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"}, 'bgcolor': "white", 'steps': steps,
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target} if target else None}
    ))
    fig.update_layout(height=220, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update DSAT Record", width="large")
def open_form_dialog(url):
    iframe(url, height=700, scrolling=True)
    if st.button("Close & Sync"): st.rerun()

# --- 5. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_clean_data(TEAM_URL)

if not st.session_state.auth:
    col_l1, col_l2 = st.columns([1, 4])
    with col_l1: st.image(LOGO_URL, width=150)
    with col_l2: st.title("HIGHLEVEL PERFORMANCE HUB")
    with st.form("login"):
        e_in, p_in = st.text_input("Work Email").lower().strip(), st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            user_match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str).str.strip() == str(p_in).strip())]
            if not user_match.empty:
                st.session_state.auth = user_match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 6. DATA FETCHING ---
user = st.session_state.auth
kpi_raw = load_and_clean_data(KPI_URL)
dsat_raw = load_and_clean_data(DSAT_URL)

# Basic KPI Prep
if not kpi_raw.empty:
    kpi_raw['IA_Mins'] = kpi_raw['IA'].apply(parse_time)
    kpi_raw['Call_Mins'] = kpi_raw['Advisor Call Time '].apply(parse_time)
    kpi_raw['Shift_Score'] = np.where(kpi_raw['IA_Mins'] > 0, (kpi_raw['Call_Mins'] / kpi_raw['IA_Mins'] * 100), 0)
    kpi_raw['Date_Parsed'] = pd.to_datetime(kpi_raw['Date_level - AS'], format="%b'%d'%y", errors='coerce')
    for col in ['Sent Rate %', 'Satisfied Survey %', 'Q/A Calls', 'OB Calls', 'Total Survey']:
        kpi_raw[col] = pd.to_numeric(kpi_raw[col], errors='coerce').fillna(0)

# --- 7. DYNAMIC HIERARCHY FILTERING ---
level = user.get('Access level', 'IC')
st.sidebar.title("Navigation Filters")
freq = st.sidebar.radio("Frequency:", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

# Scoping
if level == "Admin":
    directors = team_db[team_db['Advisor Name'].isin(team_db['Manager'].unique())]['Manager'].unique()
    dir_sel = st.sidebar.selectbox("Organization Overview", ["Entire Org"] + list(directors))
    if dir_sel == "Entire Org":
        emails = team_db['Email'].unique()
    else:
        managers = team_db[team_db['Manager'] == dir_sel]['Advisor Name'].unique()
        mgr_sel = st.sidebar.selectbox("Manager Team", ["All Depts"] + list(managers))
        if mgr_sel == "All Depts":
            emails = team_db[team_db['Manager'] == dir_sel]['Email'].unique()
        else:
            advisors = team_db[team_db['Manager'] == mgr_sel]['Advisor Name'].unique()
            adv_sel = st.sidebar.selectbox("Advisor", ["Entire Team"] + list(advisors))
            emails = team_db[team_db['Advisor Name'] == adv_sel]['Email'].unique() if adv_sel != "Entire Team" else team_db[team_db['Manager'] == mgr_sel]['Email'].unique()
elif level == "Manager":
    advisors = team_db[team_db['Manager'] == user['Advisor Name']]['Advisor Name'].unique()
    adv_sel = st.sidebar.selectbox("Team View", ["Full Team"] + list(advisors))
    emails = team_db[team_db['Advisor Name'] == adv_sel]['Email'].unique() if adv_sel != "Full Team" else team_db[team_db['Manager'] == user['Advisor Name']]['Email'].unique()
else:
    emails = [user['Email']]

f_kpi = kpi_raw[kpi_raw['Email'].isin(emails)]
f_dsat = dsat_raw[dsat_raw['Advisor Email'].isin(emails)]

# --- 8. DASHBOARD UI ---
st.title("🚀 PERFORMANCE HUB")
st.caption(f"Member: {user['Advisor Name']} | Access: {level}")

tabs = st.tabs(["Performance Overview", "DSAT Analysis", "Leaderboards"])

with tabs[0]:
    active = f_kpi[f_kpi['IA_Mins'] > 0]
    avg_score = active['Shift_Score'].mean() if not active.empty else 0
    avg_sent = f_kpi[f_kpi['Total Survey'] > 0]['Sent Rate %'].mean() * 100 if not f_kpi.empty else 0
    avg_sat = f_kpi[f_kpi['Total Survey'] > 0]['Satisfied Survey %'].mean() * 100 if not f_kpi.empty else 0
    total_ob, total_qa = f_kpi['OB Calls'].sum(), f_kpi['Q/A Calls'].sum()

    st.info(f"Summary: Quality: **{avg_sat:.2f}%** | Sent Rate: **{avg_sent:.2f}%** | Shift Score: **{avg_score:.2f}%**")
    
    g1, g2, g3 = st.columns(3)
    g1.plotly_chart(create_ghl_gauge("Shift Score", avg_score, 85, color_steps=True), use_container_width=True)
    g2.plotly_chart(create_ghl_gauge("Survey Sent %", avg_sent, 85, color_steps=True), use_container_width=True)
    g3.plotly_chart(create_ghl_gauge("Satisfied Survey %", avg_sat, 90, color_steps=True), use_container_width=True)

    v1, v2 = st.columns(2)
    v1.plotly_chart(create_ghl_gauge("Total OB Calls", total_ob, is_percent=False), use_container_width=True)
    v2.plotly_chart(create_ghl_gauge("Total QA Calls", total_qa, is_percent=False), use_container_width=True)

    st.markdown("### 📈 Trend Analysis")
    if not f_kpi.empty:
        trend = f_kpi.groupby('Date_Parsed').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'}).reset_index()
        tc1, tc2 = st.columns(2)
        with tc1:
            st.plotly_chart(px.line(trend, x='Date_Parsed', y='Sent Rate %', title="Survey Sent Trend", markers=True), use_container_width=True)
            st.plotly_chart(px.line(trend, x='Date_Parsed', y='Q/A Calls', title="Total QA Calls Trend", markers=True), use_container_width=True)
        with tc2:
            st.plotly_chart(px.line(trend, x='Date_Parsed', y='Satisfied Survey %', title="Satisfied Survey Trend", markers=True), use_container_width=True)
            st.plotly_chart(px.line(trend, x='Date_Parsed', y='OB Calls', title="Total OB Calls Trend", markers=True), use_container_width=True)

with tabs[1]:
    st.markdown("### 🚫 DSAT Analysis")
    total_dsats = len(f_dsat)
    controllable = len(f_dsat[f_dsat['Type'] == 'Controllable'])
    uncontrollable = len(f_dsat[f_dsat['Type'] == 'Uncontrollable'])
    pending = len(f_dsat[f_dsat['Feedback'].isna() | (f_dsat['Feedback'] == "")])
    
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSATs", total_dsats)
    s2.metric("Controllable", controllable)
    s3.metric("Uncontrollable", uncontrollable)
    s4.metric("Feedback Pending", pending, delta=f"{pending} Unactioned", delta_color="inverse")
    
    st.write("---")
    if not f_dsat.empty:
        col_w = [1.5, 2, 2, 1.5, 1.5, 3, 1]
        for idx, row in f_dsat.reset_index().iterrows():
            r = st.columns(col_w)
            r[0].write(str(row['Timestamp'])[:10]); r[1].write(row['Advisor Email']); r[2].write(row.get('Manager', 'N/A'))
            r[3].markdown(f"[Chat]({row['Chat DSAT URL']})"); r[4].write(row['Type']); r[5].write(row['Feedback'] if pd.notna(row['Feedback']) else "-")
            if r[6].button("Update", key=f"btn_{idx}"):
                st.write("Dialog trigger placeholder")

with tabs[2]:
    st.markdown("### 🏆 Team Leaderboards")
    ldb = f_kpi[f_kpi['Total Survey'] > 0].groupby('Agent Name').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'}).reset_index().round(2)
    l1, l2, l3 = st.columns(3)
    with l1:
        st.write("**Top Success Champions**")
        sc = ldb[(ldb['Sent Rate %'] >= 0.85) & (ldb['Satisfied Survey %'] > 0.90)]
        st.dataframe(sc[['Agent Name', 'Satisfied Survey %', 'Sent Rate %']], hide_index=True)
    with l2:
        st.write("**Total QA Calls**"); st.dataframe(ldb.sort_values('Q/A Calls', ascending=False)[['Agent Name', 'Q/A Calls']], hide_index=True)
    with l3:
        st.write("**Total OB Calls**"); st.dataframe(ldb.sort_values('OB Calls', ascending=False)[['Agent Name', 'OB Calls']], hide_index=True)

st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
