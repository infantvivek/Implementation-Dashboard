import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
import re
from streamlit.components.v1 import iframe

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub", page_icon="🚀")

# --- 2. SaaS/GHL THEME ENGINE ---
st.markdown("""
    <style>
    /* Global SaaS Typography & Colors */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    
    :root {
        --ghl-blue: #0052FF;
        --ghl-bg-light: #F4F7FA;
    }

    /* Professional Metric Cards */
    .stMetric {
        background-color: var(--secondary-background-color);
        padding: 24px;
        border-radius: 16px;
        border: 1px solid rgba(0, 82, 255, 0.1);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease;
    }
    .stMetric:hover { transform: translateY(-2px); border-color: var(--ghl-blue); }
    
    /* GHL Sidebar Branding */
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 180px; height: 60px; margin-left: 20px; margin-top: 20px;
        filter: brightness(0) invert(1); /* Adaptive for Dark Sidebar */
    }
    
    /* Centered Tabs & Alignment */
    .stTabs [aria-selected="true"] { 
        background-color: var(--ghl-blue) !important; 
        color: white !important; 
        border-radius: 8px;
    }
    
    /* Narrative Box Styling */
    div.stInfo {
        background-color: rgba(0, 82, 255, 0.05);
        border: 1px solid rgba(0, 82, 255, 0.2);
        color: var(--text-color);
        border-radius: 12px;
        padding: 20px;
        font-size: 1.1rem;
    }
    
    /* Table Styling */
    .stDataFrame { border-radius: 12px; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CORE LOGIC & PROCESSING ---
def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    try:
        parts = str(time_str).lower().split()
        for p in parts:
            if 'h' in p: h = int(re.sub(r'\D', '', p))
            elif 'm' in p: m = int(re.sub(r'\D', '', p))
        return (h * 60) + m
    except: return 0

@st.cache_data(ttl=60)
def load_and_standardize(url, sheet_type):
    try:
        df = pd.read_csv(url)
        df.columns = [re.sub(r'\s+', '_', str(c).strip().replace('\ufeff', '').replace('"', '')).lower() for c in df.columns]
        
        rmap = {
            "advisor_name": "advisor_name", "agent_name": "advisor_name",
            "advisor_email": "email", "email": "email",
            "manager": "manager_name", "access_level": "access_level",
            "ia": "ia_time", "advisor_call_time": "call_time",
            "q/a_calls": "qa_calls", "ob_calls": "ob_calls",
            "chat_dsat_url": "chat_url", "timestamp": "timestamp"
        }
        df = df.rename(columns=rmap)
        if 'email' in df.columns: df['email'] = df['email'].astype(str).str.strip().str.lower()
        
        if sheet_type == "KPI":
            metric_cols = ['sent_rate_%', 'satisfied_survey_%', 'qa_calls', 'ob_calls', 'total_survey']
            for col in metric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
            df['ia_mins'] = df['ia_time'].apply(parse_time) if 'ia_time' in df.columns else 0
            df['call_mins'] = df['call_time'].apply(parse_time) if 'call_time' in df.columns else 0
            df['shift_score'] = np.where(df['ia_mins'] > 0, (df['call_mins']/df['ia_mins']*100), 0)
            if 'date_level_-_as' in df.columns:
                df['date_parsed'] = pd.to_datetime(df['date_level_-_as'], format="%b'%d'%y", errors='coerce')
        
        if sheet_type == "DSAT":
            df['timestamp_parsed'] = pd.to_datetime(df['timestamp'], errors='coerce')
            
        return df
    except: return pd.DataFrame()

def create_ghl_gauge(title, value, target=None):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = round(value, 2), domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 18, 'color': 'gray', 'family': 'Inter'}},
        number = {'suffix': "%", 'font': {'color': '#0052FF', 'size': 40, 'family': 'Inter'}},
        gauge = {'axis': {'range': [0, 100], 'tickwidth': 1}, 'bar': {'color': "#0052FF"},
                 'bgcolor': "white", 'steps': [{'range': [0, 70], 'color': "#FFEDEB"}, {'range': [70, 85], 'color': "#FFF9E6"}, {'range': [85, 100], 'color': "#E6F9ED"}],
                 'threshold': {'line': {'color': "#0F172A", 'width': 4}, 'thickness': 0.75, 'value': target} if target else None}
    ))
    fig.update_layout(height=240, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update DSAT Record", width="large")
def open_form_dialog(row):
    params = {ENTRY_KEY: row.get('recordkey',''), ENTRY_FEEDBACK: row.get('feedback',''), ENTRY_TYPE: row.get('type','')}
    url = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url&{urllib.parse.urlencode(params)}"
    iframe(url, height=700, scrolling=True)
    if st.button("Close & Sync Data"): st.rerun()

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_standardize(TEAM_URL, "TEAM")

if not st.session_state.auth:
    col_log1, col_log2 = st.columns([1, 4])
    with col_log1: st.image(LOGO_URL, width=150)
    with col_log2: st.title("Performance Hub Login")
    with st.form("login"):
        u_email = st.text_input("Work Email").lower().strip()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['email'] == u_email) & (team_db['password'].astype(str) == str(u_pass))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. DATA FETCHING & FREQUENCY LOGIC ---
user = st.session_state.auth
kpi_raw = load_and_standardize(KPI_URL, "KPI")
dsat_raw = load_and_standardize(DSAT_URL, "DSAT")

st.sidebar.title("Data Selection")
freq_mode = st.sidebar.radio("Frequency Mode", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

if freq_mode == "Daily":
    available = sorted(kpi_raw['date_parsed'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Date", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    kpi_f = kpi_raw[kpi_raw['date_parsed'] == sel]
    dsat_f = dsat_raw[dsat_raw['timestamp_parsed'].dt.date == sel.date()]
elif freq_mode == "Weekly":
    kpi_raw['week_start'] = kpi_raw['date_parsed'].dt.to_period('W').apply(lambda r: r.start_time)
    available = sorted(kpi_raw['week_start'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Week", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    kpi_f = kpi_raw[kpi_raw['week_start'] == sel]
    dsat_f = dsat_raw[(dsat_raw['timestamp_parsed'] >= sel) & (dsat_raw['timestamp_parsed'] < sel + pd.Timedelta(days=7))]
elif freq_mode == "Monthly":
    kpi_raw['month_label'] = kpi_raw['date_parsed'].dt.strftime('%B %Y')
    available = kpi_raw.sort_values('date_parsed', ascending=False)['month_label'].unique()
    sel = st.sidebar.selectbox("Select Month", available)
    kpi_f = kpi_raw[kpi_raw['month_label'] == sel]
    dsat_f = dsat_raw[dsat_raw['timestamp_parsed'].dt.strftime('%B %Y') == sel]
else:
    kpi_raw['year_label'] = kpi_raw['date_parsed'].dt.year
    available = sorted(kpi_raw['year_label'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Year", available)
    kpi_f = kpi_raw[kpi_raw['year_label'] == sel]
    dsat_f = dsat_raw[dsat_raw['timestamp_parsed'].dt.year == sel]

# --- 6. HIERARCHY SCOPING ---
access = str(user.get('access_level', 'IC')).strip()
emails_to_scope = []

if access == "Admin":
    view_mode = st.sidebar.selectbox("Org Hierarchy", ["Entire Organisation", "Jarvis Sokolowich", "Sumit Ludhwani"])
    if view_mode == "Entire Organisation":
        emails_to_scope = team_db['email'].unique()
    else:
        mgrs_list = team_db[team_db['manager_name'] == view_mode]['advisor_name'].unique()
        mgr_sel = st.sidebar.selectbox(f"Managers Under {view_mode}", ["All Teams"] + list(mgrs_list))
        if mgr_sel == "All Teams":
            emails_to_scope = team_db[team_db['manager_name'] == view_mode]['email'].unique()
        else:
            advs_list = team_db[team_db['manager_name'] == mgr_sel]['advisor_name'].unique()
            adv_sel = st.sidebar.selectbox(f"Advisors Under {mgr_sel}", ["Full Team"] + list(advs_list))
            emails_to_scope = [team_db[team_db['advisor_name'] == adv_sel]['email'].values[0]] if adv_sel != "Full Team" else team_db[team_db['manager_name'] == mgr_sel]['email'].unique()
elif access == "Manager":
    view_mode = st.sidebar.selectbox("Team View", ["Team Overview", "Individual Advisor View"])
    if view_mode == "Team Overview":
        emails_to_scope = team_db[team_db['manager_name'] == user['advisor_name']]['email'].unique()
    else:
        my_team = team_db[team_db['manager_name'] == user['advisor_name']]['advisor_name'].unique()
        adv_sel = st.sidebar.selectbox("Select Advisor", list(my_team))
        emails_to_scope = [team_db[team_db['advisor_name'] == adv_sel]['email'].values[0]]
else:
    emails_to_scope = [user['email']]

f_kpi = kpi_f[kpi_f['email'].isin(emails_to_scope)]
f_dsat = dsat_f[dsat_f['email'].isin(emails_to_scope)]

# --- 7. UI TABS ---
st.title("Implementation Team Performance Hub")
st.markdown(f"**Welcome {user['advisor_name']}!** | Access Level: `{access}`")

tabs = st.tabs(["📊 Performance Overview", "🚫 DSAT Analysis"] + (["🏆 Leaderboard"] if access != "IC" else []))

with tabs[0]:
    # a. Narrative Logic
    avg_shift = f_kpi['shift_score'].mean() if not f_kpi.empty else 0
    st.info(f"**Performance Narrative:** In this period ({sel}), the group achieved an average Shift Score of **{avg_shift:.2f}%**. High OB activity suggests proactive customer outreach is driving engagement.")
    
    # b. Gauges & Averages (Calculated for 2 decimal points)
    st.markdown("### Performance Summary")
    g1, g2, g3 = st.columns(3)
    # Calculate means only from records with activity
    active_surveys = f_kpi[f_kpi['total_survey'] > 0]
    avg_sent = (active_surveys['sent_rate_%'].mean() * 100) if not active_surveys.empty else 0
    avg_sat = (active_surveys['satisfied_survey_%'].mean() * 100) if not active_surveys.empty else 0
    
    g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
    g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
    g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_shift, 85), use_container_width=True)
    
    m1, m2 = st.columns(2)
    m1.metric("Total OB Calls", f"{int(f_kpi['ob_calls'].sum()):,}")
    m2.metric("Total OH Calls (QA)", f"{int(f_kpi['qa_calls'].sum()):,}")

    # c. Trends
    st.markdown("### Performance Trends")
    if not f_kpi.empty:
        trend = f_kpi.groupby('date_parsed').agg({'sent_rate_%':'mean', 'satisfied_survey_%':'mean', 'shift_score':'mean', 'ob_calls':'sum', 'qa_calls':'sum'}).reset_index()
        t1, t2 = st.columns(2)
        t1.plotly_chart(px.line(trend, x='date_parsed', y=['sent_rate_%', 'satisfied_survey_%'], title="Survey Trends (Sent vs Satisfied)", color_discrete_map={"sent_rate_%":"#0052FF", "satisfied_survey_%":"#22C55E"}), use_container_width=True)
        t2.plotly_chart(px.line(trend, x='date_parsed', y='shift_score', title="Shift Score Trend", color_discrete_sequence=["#F59E0B"]), use_container_width=True)
        
        t3, t4 = st.columns(2)
        t3.plotly_chart(px.bar(trend, x='date_parsed', y='ob_calls', title="Daily OB Calls", color_discrete_sequence=["#0052FF"]), use_container_width=True)
        t4.plotly_chart(px.bar(trend, x='date_parsed', y='qa_calls', title="Daily OH Calls", color_discrete_sequence=["#6366F1"]), use_container_width=True)

with tabs[1]:
    st.markdown("### DSAT Summary")
    pending = len(f_dsat[f_dsat['feedback'].isna() | (f_dsat['feedback'] == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", f"{len(f_dsat)}")
    s2.metric("Pending Feedback", f"{pending}")
    s3.metric("Controllable", f"{len(f_dsat[f_dsat['type'] == 'Controllable'])}")
    s4.metric("Uncontrollable", f"{len(f_dsat[f_dsat['type'] == 'Uncontrollable'])}")

    st.markdown("### DSAT Audit Log")
    if not f_dsat.empty:
        # Re-merge to ensure full advisor names appear in the table
        f_table = f_dsat.merge(team_db[['email', 'advisor_name', 'manager_name']], on='email', how='left')
        f_table['feedback'] = f_table['feedback'].fillna("-")
        f_table['type'] = f_table['type'].fillna("-")
        
        col_w = [1.5, 2, 1.5, 1, 1.2, 2.5] + ([1] if access != "IC" else [])
        headers = ["Date", "Advisor", "Manager", "Chat", "Type", "Feedback"] + (["Action"] if access != "IC" else [])
        cols = st.columns(col_w)
        for i, h in enumerate(headers): cols[i].write(f"**{h}**")
        
        for idx, row in f_table.reset_index().iterrows():
            r = st.columns(col_w)
            r[0].write(str(row['timestamp'])[:10])
            r[1].write(row['advisor_name_x'])
            r[2].write(row['manager_name_x'])
            r[3].markdown(f"[🔗 Link]({row['chat_url']})")
            r[4].write(row['type'])
            r[5].write(row['feedback'])
            if access != "IC":
                if r[6].button("Update", key=f"upd_{idx}"): open_form_dialog(row)

if access != "IC":
    with tabs[2]:
        st.markdown("### 🏆 Leadership Rankings")
        # Calc leaderboard metrics with 2-dec precision
        ldb = kpi_f.groupby('advisor_name').agg({'sent_rate_%':'mean', 'satisfied_survey_%':'mean', 'qa_calls':'sum', 'ob_calls':'sum'}).reset_index()
        ldb['sent_rate_%'] = (ldb['sent_rate_%'] * 100).round(2)
        ldb['satisfied_survey_%'] = (ldb['satisfied_survey_%'] * 100).round(2)
        
        st.write("**✨ Success Champions**")
        st.caption("Criteria: Avg Survey Sent ≥ 85.00% and Avg Satisfied ≥ 90.00%")
        champs = ldb[(ldb['sent_rate_%'] >= 85) & (ldb['satisfied_survey_%'] >= 90)].sort_values('satisfied_survey_%', ascending=False)
        st.dataframe(champs[['advisor_name', 'satisfied_survey_%', 'sent_rate_%']], hide_index=True, use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Top Satisfied Surveys**")
            st.dataframe(ldb.sort_values('satisfied_survey_%', ascending=False)[['advisor_name', 'satisfied_survey_%']], hide_index=True, use_container_width=True)
        with c2:
            st.write("**Top Survey Sent Rate**")
            st.dataframe(ldb.sort_values('sent_rate_%', ascending=False)[['advisor_name', 'sent_rate_%']], hide_index=True, use_container_width=True)
        
        c3, c4 = st.columns(2)
        with c3:
            st.write("**Top QA Call Volume**")
            st.dataframe(ldb.sort_values('qa_calls', ascending=False)[['advisor_name', 'qa_calls']], hide_index=True, use_container_width=True)
        with c4:
            st.write("**Top OB Outreach**")
            st.dataframe(ldb.sort_values('ob_calls', ascending=False)[['advisor_name', 'ob_calls']], hide_index=True, use_container_width=True)

st.sidebar.divider()
if st.sidebar.button("Logout"): 
    st.session_state.auth = None
    st.rerun()
