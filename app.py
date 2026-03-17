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

# PRE-FILLED FORM CONFIG
FORM_ID = "YOUR_FORM_ID" # Replace with your actual Form ID
ENTRY_FEEDBACK, ENTRY_TYPE, ENTRY_KEY = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub", page_icon="🚀")

# --- 2. SaaS/GHL THEME ENGINE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    :root { --ghl-blue: #0052FF; }
    .stMetric { background-color: var(--secondary-background-color); padding: 24px; border-radius: 15px; border: 1px solid rgba(0, 82, 255, 0.1); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
    [data-testid="stSidebarNav"]::before { content: ""; display: block; background-image: url('""" + LOGO_URL + """'); background-size: contain; background-repeat: no-repeat; width: 170px; height: 50px; margin: 25px 0 10px 25px; filter: brightness(0) invert(1); }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; border-radius: 8px; }
    div.stInfo { background-color: rgba(0, 82, 255, 0.05); border-left: 5px solid #0052FF; color: var(--text-color); border-radius: 10px; padding: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA PROCESSING ---
def parse_duration(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    try:
        h, m = 0, 0
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
        # 1. Clean Headers: Handle invisible symbols, tabs, and spaces
        df.columns = [re.sub(r'[^a-zA-Z0-9]', '', str(c)).lower() for c in df.columns]
        
        # 2. Strict Internal Mapping
        rmap = {
            "advisorname": "name", "agentname": "name", "email": "email", "advisoremail": "email",
            "manager": "mgr", "managername": "mgr", "accesslevel": "level", "password": "pass",
            "ia": "ia_raw", "advisorcalltime": "call_raw", "sentrate": "sent_rate", 
            "satisfiedsurvey": "sat_rate", "obcalls": "ob", "qacalls": "qa", 
            "totalsurvey": "surveys", "timestamp": "ts", "processed": "ts", "chatdsaturl": "link", "datelevelas": "date_raw"
        }
        df = df.rename(columns=rmap)
        if 'email' in df.columns: df['email'] = df['email'].astype(str).str.strip().str.lower()
        
        if sheet_type == "KPI":
            # Fix Percentage Overflow/Underflow
            for col in ['sent_rate', 'sat_rate']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
                    if df[col].max() <= 1.1: df[col] = df[col] * 100
            
            df['date_dt'] = pd.to_datetime(df['date_raw'], format="%b'%d'%y", errors='coerce')
            df['ia_min'] = df['ia_raw'].apply(parse_duration)
            df['call_min'] = df['call_raw'].apply(parse_duration)
            df['shift_score'] = np.where(df['ia_min'] > 0, (df['call_min']/df['ia_min']*100), 0)
        
        if sheet_type == "DSAT":
            # In your new file, 'ts' comes from 'processed' column if 'timestamp' is missing
            df['date_dt'] = pd.to_datetime(df['ts'], errors='coerce')
            df['feedback'] = df['feedback'].fillna("-")
            df['type'] = df['type'].fillna("-")
        return df
    except Exception as e:
        return pd.DataFrame()

def create_ghl_gauge(title, value, target):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = round(value, 2), domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number = {'suffix': "%", 'font': {'color': '#0052FF', 'size': 38}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"},
                 'steps': [{'range': [0, 70], 'color': "#FFEDEB"}, {'range': [70, 85], 'color': "#FFF9E6"}, {'range': [85, 100], 'color': "#E6F9ED"}],
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target}}
    ))
    fig.update_layout(height=230, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update DSAT Feedback", width="large")
def open_form(row):
    params = {ENTRY_KEY: row.get('recordkey',''), ENTRY_FEEDBACK: row.get('feedback',''), ENTRY_TYPE: row.get('type','')}
    url = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url&{urllib.parse.urlencode(params)}"
    iframe(url, height=600, scrolling=True)
    if st.button("Close & Sync Dashboard"): st.rerun()

# --- 4. AUTHENTICATION & DATA FETCH ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_standardize(TEAM_URL, "TEAM")

if not st.session_state.auth:
    col_l, col_r = st.columns([1, 4])
    with col_l: st.image(LOGO_URL, width=150)
    with col_r: st.title("Implementation Team Performance Hub")
    with st.form("login"):
        u_email = st.text_input("Work Email").lower().strip()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['email'] == u_email) & (team_db['pass'].astype(str) == str(u_pass))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict(); st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

user = st.session_state.auth
kpi_raw = load_and_standardize(KPI_URL, "KPI")
dsat_raw = load_and_standardize(DSAT_URL, "DSAT")

# --- 5. FREQUENCY & HIERARCHY FILTERS ---
st.sidebar.title("Navigation Filters")
freq = st.sidebar.radio("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

# Select Time Range
if freq == "Daily":
    available = sorted(kpi_raw['date_dt'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Date", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    k_f, d_f = kpi_raw[kpi_raw['date_dt'] == sel], dsat_raw[dsat_raw['date_dt'].dt.date == sel.date()]
elif freq == "Weekly":
    kpi_raw['wk'] = kpi_raw['date_dt'].dt.to_period('W').apply(lambda r: r.start_time)
    available = sorted(kpi_raw['wk'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Week", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    k_f, d_f = kpi_raw[kpi_raw['wk'] == sel], dsat_raw[(dsat_raw['date_dt'] >= sel) & (dsat_raw['date_dt'] < sel + pd.Timedelta(days=7))]
else:
    kpi_raw['mo'] = kpi_raw['date_dt'].dt.strftime('%B %Y')
    sel = st.sidebar.selectbox("Select Month", kpi_raw.sort_values('date_dt', ascending=False)['mo'].unique())
    k_f, d_f = kpi_raw[kpi_raw['mo'] == sel], dsat_raw[dsat_raw['date_dt'].dt.strftime('%B %Y') == sel]

# Drill-down Scoping
access = str(user.get('level', 'IC')).strip()
scoped_emails = []

if access == "Admin":
    view_mode = st.sidebar.selectbox("Organization View", ["Entire Organisation", "Jarvis Sokolowich", "Sumit Ludhwani"])
    if view_mode == "Entire Organisation": scoped_emails = team_db['email'].unique()
    else:
        mgrs = team_db[team_db['mgr'] == view_mode]['name'].unique()
        mgr_sel = st.sidebar.selectbox(f"Managers under {view_mode}", ["All Teams"] + list(mgrs))
        if mgr_sel == "All Teams": scoped_emails = team_db[team_db['mgr'] == view_mode]['email'].unique()
        else:
            advs = team_db[team_db['mgr'] == mgr_sel]['name'].unique()
            adv_sel = st.sidebar.selectbox(f"Advisors under {mgr_sel}", ["Full Team"] + list(advs))
            scoped_emails = [team_db[team_db['name'] == adv_sel]['email'].values[0]] if adv_sel != "Full Team" else team_db[team_db['mgr'] == mgr_sel]['email'].unique()
elif access == "Manager":
    mode = st.sidebar.selectbox("View Mode", ["Team Overview", "Specific Advisor"])
    my_advs = team_db[team_db['mgr'] == user['name']]
    if mode == "Team Overview": scoped_emails = my_advs['email'].unique()
    else: scoped_emails = [my_advs[my_advs['name'] == st.sidebar.selectbox("Select Advisor", my_advs['name'].unique())]['email'].values[0]]
else: scoped_emails = [user['email']]

f_kpi, f_dsat = k_f[k_f['email'].isin(scoped_emails)], d_f[d_f['email'].isin(scoped_emails)]

# --- 6. MAIN UI ---
st.title("Performance Hub Dashboard")
st.success(f"Welcome **{user['name']}**!! | Access Level : **{access}**")

tabs = st.tabs(["📊 Performance Overview", "🚫 DSAT Analysis"] + (["🏆 Leaderboard"] if access != "IC" else []))

with tabs[0]:
    avg_score = f_kpi['shift_score'].mean() if not f_kpi.empty else 0
    st.info(f"**Performance Narrative:** In the selected period, the average Shift Score is **{avg_score:.2f}%**. Monitoring trends suggest consistent engagement across outbound activities.")
    
    g1, g2, g3 = st.columns(3)
    active_surveys = f_kpi[f_kpi['surveys'] > 0]
    avg_sent = active_surveys['sent_rate'].mean() if not active_surveys.empty else 0
    avg_sat = active_surveys['sat_rate'].mean() if not active_surveys.empty else 0
    
    g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
    g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
    g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_score, 85), use_container_width=True)
    
    m1, m2 = st.columns(2)
    m1.metric("Total OB Calls", f"{int(f_kpi['ob'].sum()):,}")
    m2.metric("Total OH Calls (QA)", f"{int(f_kpi['qa'].sum()):,}")

    if not f_kpi.empty:
        trend = f_kpi.groupby('date_dt').agg({'sent_rate':'mean', 'sat_rate':'mean', 'shift_score':'mean', 'ob':'sum', 'qa':'sum'}).reset_index().sort_values('date_dt')
        st.plotly_chart(px.line(trend, x='date_dt', y=['sent_rate', 'sat_rate'], title="Survey Trends (%)", markers=True), use_container_width=True)
        st.plotly_chart(px.bar(trend, x='date_dt', y=['ob', 'qa'], title="Call Volume (OB vs OH)", barmode='group'), use_container_width=True)

with tabs[1]:
    st.markdown("### DSAT Summary")
    pending = len(f_dsat[f_dsat['feedback'].isin(["", "-", np.nan])])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", f"{len(f_dsat)}")
    s2.metric("Pending Feedback", f"{pending}")
    s3.metric("Controllable", f"{len(f_dsat[f_dsat['type'] == 'Controllable'])}")
    s4.metric("Uncontrollable", f"{len(f_dsat[f_dsat['type'] == 'Uncontrollable'])}")

    st.markdown("### DSAT Audit Log")
    if not f_dsat.empty:
        f_view = f_dsat.merge(team_db[['email', 'name', 'mgr']], on='email', how='left')
        col_w = [1.5, 2, 1.5, 1, 1.2, 2.5] + ([1] if access != "IC" else [])
        headers = ["Date", "Advisor", "Manager", "Chat", "Type", "Feedback"] + (["Action"] if access != "IC" else [])
        cols = st.columns(col_w)
        for i, h in enumerate(headers): cols[i].write(f"**{h}**")
        for idx, row in f_view.reset_index().iterrows():
            r = st.columns(col_w)
            r[0].write(str(row['ts'])[:10]); r[1].write(row['name_y']); r[2].write(row['mgr_y'])
            r[3].markdown(f"[Link]({row['link']})"); r[4].write(row['type']); r[5].write(row['feedback'])
            if access != "IC" and r[6].button("Update", key=f"upd_{idx}"): open_form(row)

if access != "IC":
    with tabs[2]:
        st.markdown("### 🏆 Leadership Rankings")
        ldb = k_f.groupby('name').agg({'sent_rate':'mean', 'sat_rate':'mean', 'qa':'sum', 'ob':'sum'}).reset_index().round(2)
        st.write("**✨ Success Champions (Sent ≥ 85%, Sat ≥ 90%)**")
        st.dataframe(ldb[(ldb['sent_rate'] >= 85) & (ldb['sat_rate'] >= 90)].sort_values('sat_rate', ascending=False), hide_index=True, use_container_width=True)
        st.dataframe(ldb.sort_values('sat_rate', ascending=False), hide_index=True, use_container_width=True)

st.sidebar.divider()
if st.sidebar.button("Logout"): st.session_state.auth = None; st.rerun()
