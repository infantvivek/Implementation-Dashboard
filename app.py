import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
import re
from streamlit.components.v1 import iframe

# --- 1. CONFIGURATION & URLS ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

# PRE-FILLED FORM CONFIG
FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub")

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

# --- 3. ROBUST DATA LOADER & NORMALIZER ---
def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    try:
        parts = str(time_str).lower().split()
        for p in parts:
            if 'h' in p: h = int(p.replace('h', ''))
            elif 'm' in p: m = int(p.replace('m', ''))
        return (h * 60) + m
    except: return 0

@st.cache_data(ttl=60)
def load_data(url, sheet_type):
    try:
        df = pd.read_csv(url)
        df.columns = [str(c).strip().replace('\ufeff', '').replace('"', '') for c in df.columns]
        
        # Consistent mapping for internal logic
        rmap = {
            "Advisor Name": "advisor_name", "Agent Name": "advisor_name",
            "Advisor Email": "email", "Email": "email",
            "Manager": "manager_name", "Access level": "access_level",
            "IA": "ia_time", "Advisor Call Time ": "call_time", "Advisor Call Time": "call_time",
            "OB Calls": "ob_calls", "Q/A Calls": "oh_calls",
            "Chat DSAT URL": "chat_url", "Timestamp": "timestamp", "Feedback": "feedback", "Type": "type"
        }
        df = df.rename(columns=rmap)
        if 'email' in df.columns: df['email'] = df['email'].str.strip().str.lower()
        
        if sheet_type == "KPI":
            df['ia_mins'] = df['ia_time'].apply(parse_time)
            df['call_mins'] = df['call_time'].apply(parse_time)
            df['shift_score'] = np.where(df['ia_mins'] > 0, (df['call_mins']/df['ia_mins']*100), 0)
            df['date_parsed'] = pd.to_datetime(df['Date_level - AS'], format="%b'%d'%y", errors='coerce')
            for col in ['Sent Rate %', 'Satisfied Survey %', 'ob_calls', 'oh_calls']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def create_ghl_gauge(title, value, target):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number = {'suffix': "%", 'font': {'color': '#0052FF', 'size': 35}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"},
                 'steps': [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}],
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target}}
    ))
    fig.update_layout(height=200, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update Record", width="large")
def open_form_dialog(row):
    params = {ENTRY_KEY: row['RecordKey'], ENTRY_FEEDBACK: row.get('feedback', ''), ENTRY_TYPE: row.get('type', '')}
    url = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url&{urllib.parse.urlencode(params)}"
    iframe(url, height=700, scrolling=True)
    if st.button("Close & Sync"): st.rerun()

# --- 4. DATA INITIALIZATION & AUTH ---
team_db = load_data(TEAM_URL, "TEAM")
if 'auth' not in st.session_state: st.session_state.auth = None

if not st.session_state.auth:
    col_l1, col_l2 = st.columns([1, 4])
    with col_l1: st.image(LOGO_URL, width=150)
    with col_l2: st.title("Implementation Team Performance Hub")
    with st.form("login"):
        e_in, p_in = st.text_input("Work Email").lower().strip(), st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['email'] == e_in) & (team_db['Password'].astype(str) == str(p_in))]
            if not match.empty: st.session_state.auth = match.iloc[0].to_dict(); st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. HIERARCHY & DATE NAVIGATION ---
user = st.session_state.auth
kpi_db = load_data(KPI_URL, "KPI")
dsat_db = load_data(DSAT_URL, "DSAT")

st.sidebar.title("Configuration")
freq = st.sidebar.radio("Select Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

if freq == "Daily":
    sel = st.sidebar.selectbox("Select Date", sorted(kpi_db['date_parsed'].dropna().unique(), reverse=True), format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_t = kpi_db[kpi_db['date_parsed'] == sel]
elif freq == "Weekly":
    kpi_db['week_start'] = kpi_db['date_parsed'].dt.to_period('W').apply(lambda r: r.start_time)
    sel = st.sidebar.selectbox("Select Week Starting", sorted(kpi_db['week_start'].dropna().unique(), reverse=True), format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_t = kpi_db[kpi_db['week_start'] == sel]
elif freq == "Monthly":
    kpi_db['month_year'] = kpi_db['date_parsed'].dt.strftime('%B %Y')
    sel = st.sidebar.selectbox("Select Month", kpi_db.sort_values('date_parsed', ascending=False)['month_year'].unique())
    f_kpi_t = kpi_db[kpi_db['month_year'] == sel]
else:
    sel = st.sidebar.selectbox("Select Year", sorted(kpi_db['date_parsed'].dt.year.dropna().unique(), reverse=True))
    f_kpi_t = kpi_db[kpi_db['date_parsed'].dt.year == sel]

# Access Scoping
level = str(user.get('access_level', 'IC')).strip()
emails = []

if level == "Admin":
    directors = ["Entire Organisation", "Jarvis Sokolowich", "Sumit Ludhwani"]
    view_mode = st.sidebar.selectbox("View Mode", directors)
    if view_mode == "Entire Organisation": emails = team_db['email'].unique()
    else:
        mgr_list = team_db[team_db['manager_name'] == view_mode]['advisor_name'].unique()
        mgr_sel = st.sidebar.selectbox(f"Managers under {view_mode}", ["All Teams"] + list(mgr_list))
        if mgr_sel == "All Teams": emails = team_db[team_db['manager_name'] == view_mode]['email'].unique()
        else:
            adv_list = team_db[team_db['manager_name'] == mgr_sel]['advisor_name'].unique()
            adv_sel = st.sidebar.selectbox(f"Advisors under {mgr_sel}", ["Full Team"] + list(adv_list))
            emails = [team_db[team_db['advisor_name'] == adv_sel]['email'].values[0]] if adv_sel != "Full Team" else team_db[team_db['manager_name'] == mgr_sel]['email'].unique()

elif level == "Manager":
    view_mode = st.sidebar.selectbox("View Mode", ["Team Overview", "Specific Advisor View"])
    if view_mode == "Team Overview": emails = team_db[team_db['manager_name'] == user['advisor_name']]['email'].unique()
    else:
        adv_sel = st.sidebar.selectbox("Select Advisor", list(team_db[team_db['manager_name'] == user['advisor_name']]['advisor_name'].unique()))
        emails = [team_db[team_db['advisor_name'] == adv_sel]['email'].values[0]]

else: emails = [user['email']]

f_kpi = f_kpi_t[f_kpi_t['email'].isin(emails)]
f_dsat = dsat_db[dsat_db['email'].isin(emails)]

# --- 6. UI TABS ---
st.title("Implementation Team Performance Hub")
st.success(f"Welcome **{user['advisor_name']}**!!, Access Level : **{level}**")

tabs = st.tabs(["Performance Overview", "DSAT Analysis"] + (["Leaderboard"] if level != "IC" else []))

with tabs[0]:
    avg_score = f_kpi['shift_score'].mean() if not f_kpi.empty else 0
    st.markdown("### Performance Narrative")
    st.info(f"The selected group is performing with an efficiency score of {avg_score:.2f}%. Monitoring trends suggests maintaining high survey sent rates is key to meeting current KPI benchmarks.")
    
    st.markdown("### Performance Summary")
    g1, g2, g3 = st.columns(3)
    avg_sent = (f_kpi['Sent Rate %'].mean() * 100) if not f_kpi.empty else 0
    avg_sat = (f_kpi['Satisfied Survey %'].mean() * 100) if not f_kpi.empty else 0
    g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
    g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
    g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_score, 85), use_container_width=True)
    
    m1, m2 = st.columns(2)
    m1.metric("Total OB Calls", int(f_kpi['ob_calls'].sum()))
    m2.metric("Total OH Calls", int(f_kpi['oh_calls'].sum()))

    st.markdown("### Performance Trends")
    trend = f_kpi.groupby('date_parsed').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'shift_score':'mean', 'ob_calls':'sum', 'oh_calls':'sum'}).reset_index()
    t1, t2 = st.columns(2)
    t1.plotly_chart(px.line(trend, x='date_parsed', y='Sent Rate %', title="Survey Sent Trend", markers=True), use_container_width=True)
    t2.plotly_chart(px.line(trend, x='date_parsed', y='Satisfied Survey %', title="Satisfied Survey Trend", markers=True), use_container_width=True)
    t3, t4, t5 = st.columns(3)
    t3.plotly_chart(px.line(trend, x='date_parsed', y='shift_score', title="Avg Shift Score Trend", markers=True), use_container_width=True)
    t4.plotly_chart(px.line(trend, x='date_parsed', y='ob_calls', title="Total OB Calls Trend", markers=True), use_container_width=True)
    t5.plotly_chart(px.line(trend, x='date_parsed', y='oh_calls', title="Total OH Calls Trend", markers=True), use_container_width=True)

with tabs[1]:
    st.markdown("### DSAT Summary")
    pending = len(f_dsat[f_dsat['feedback'].isna() | (f_dsat['feedback'] == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", len(f_dsat))
    s2.metric("Feedback Yet to be Provided", pending)
    s3.metric("Controllable", len(f_dsat[f_dsat['type'] == 'Controllable']))
    s4.metric("Uncontrollable", len(f_dsat[f_dsat['type'] == 'Uncontrollable']))

    st.markdown("### DSAT Analysis Table")
    if not f_dsat.empty:
        df_display = f_dsat.copy().fillna("-")
        col_widths = [1.5, 2, 2, 1, 1.2, 3] + ([1] if level != "IC" else [])
        headers = ["Date", "Advisor Name", "Manager", "Chat Link", "Type", "Feedback"] + (["Action"] if level != "IC" else [])
        cols = st.columns(col_widths)
        for i, h in enumerate(headers): cols[i].write(f"**{h}**")
        for idx, row in df_display.reset_index().iterrows():
            r = st.columns(col_widths)
            r[0].write(str(row['timestamp'])[:10])
            # Getting Advisor name from Team DB via Email
            adv_name = team_db[team_db['email'] == row['email']]['advisor_name'].values[0] if row['email'] in team_db['email'].values else "-"
            r[1].write(adv_name); r[2].write(row['manager_name'])
            r[3].markdown(f"[Chat Link]({row['chat_url']})")
            r[4].write(row['type']); r[5].write(row['feedback'])
            if level != "IC":
                if r[6].button("Update", key=f"btn_{idx}"): open_form_dialog(row)

if len(tabs) > 2:
    with tabs[2]:
        st.markdown("### 🏆 Leaderboards")
        ldb = f_kpi_t.groupby('advisor_name').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'oh_calls':'sum', 'ob_calls':'sum'}).reset_index()
        st.write("**Success Champions**")
        st.caption("Criteria: Avg Sent Rate ≥ 85% and Avg Satisfied Survey ≥ 90%")
        champs = ldb[(ldb['Sent Rate %'] >= 0.85) & (ldb['Satisfied Survey %'] >= 0.90)].sort_values('Satisfied Survey %', ascending=False)
        st.dataframe(champs[['advisor_name', 'Satisfied Survey %', 'Sent Rate %']], hide_index=True, use_container_width=True)
        
        c1, c2 = st.columns(2)
        c1.subheader("Total QA Calls"); c1.dataframe(ldb.sort_values('oh_calls', ascending=False)[['advisor_name', 'oh_calls']], hide_index=True)
        c2.subheader("Total OB Calls"); c2.dataframe(ldb.sort_values('ob_calls', ascending=False)[['advisor_name', 'ob_calls']], hide_index=True)
        c3, c4 = st.columns(2)
        c3.subheader("Avg Satisfied Survey"); c3.dataframe(ldb.sort_values('Satisfied Survey %', ascending=False)[['advisor_name', 'Satisfied Survey %']], hide_index=True)
        c4.subheader("Avg Survey Sent"); c4.dataframe(ldb.sort_values('Sent Rate %', ascending=False)[['advisor_name', 'Sent Rate %']], hide_index=True)

st.sidebar.divider()
if st.sidebar.button("Logout"): st.session_state.auth = None; st.rerun()
