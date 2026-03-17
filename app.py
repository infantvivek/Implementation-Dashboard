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
FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub", page_icon="🚀")

# --- 2. SaaS/GHL THEME ENGINE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    .stMetric { background-color: var(--secondary-background-color); padding: 24px; border-radius: 16px; border: 1px solid rgba(0, 82, 255, 0.1); }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat; width: 180px; height: 60px; 
        margin-left: 20px; margin-top: 20px; filter: brightness(0) invert(1);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; border-radius: 8px; }
    div.stInfo { background-color: rgba(0, 82, 255, 0.05); border-left: 5px solid #0052FF; border-radius: 8px; padding: 20px; color: var(--text-color); }
    </style>
""", unsafe_allow_html=True)

# --- 3. CORE DATA ENGINE ---
def parse_duration(time_str):
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
def load_all_data(url, sheet_type):
    try:
        df = pd.read_csv(url)
        # Standardize headers (strip whitespace and symbols)
        df.columns = [re.sub(r'[^a-zA-Z0-9]', '', str(c)).lower() for c in df.columns]
        
        # Consistent Mapping
        rmap = {
            "advisorname": "name", "agentname": "name", "email": "email", "advisoremail": "email",
            "manager": "mgr", "managername": "mgr", "accesslevel": "level", "password": "pass",
            "ia": "ia_raw", "advisorcalltime": "call_raw", "sentrate": "sent_rate", 
            "satisfiedsurvey": "sat_rate", "obcalls": "ob", "qacalls": "qa", 
            "totalsurvey": "surveys", "timestamp": "ts", "chatdsaturl": "link", "datelevelas": "date_raw"
        }
        df = df.rename(columns=rmap)
        if 'email' in df.columns: df['email'] = df['email'].astype(str).str.strip().str.lower()
        
        if sheet_type == "KPI":
            # Smart Scaling for Percentages
            for col in ['sent_rate', 'sat_rate']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
                    if df[col].max() <= 1.1: df[col] = df[col] * 100
            
            df['date_dt'] = pd.to_datetime(df['date_raw'], format="%b'%d'%y", errors='coerce')
            df['ia_min'] = df['ia_raw'].apply(parse_duration)
            df['call_min'] = df['call_raw'].apply(parse_duration)
            df['shift_score'] = np.where(df['ia_min'] > 0, (df['call_min']/df['ia_min']*100), 0)
        
        if sheet_type == "DSAT":
            df['date_dt'] = pd.to_datetime(df['ts'], errors='coerce')
            
        return df
    except Exception as e:
        return pd.DataFrame()

def create_ghl_gauge(title, value, target=None):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = round(value, 2), domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number = {'suffix': "%", 'font': {'color': '#0052FF', 'size': 38}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"},
                 'steps': [{'range': [0, 70], 'color': "#FFEDEB"}, {'range': [70, 85], 'color': "#FFF9E6"}, {'range': [85, 100], 'color': "#E6F9ED"}],
                 'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': target} if target else None}
    ))
    fig.update_layout(height=230, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update Record", width="large")
def open_form_dialog(row):
    params = {ENTRY_KEY: row.get('recordkey',''), ENTRY_FEEDBACK: row.get('feedback',''), ENTRY_TYPE: row.get('type','')}
    url = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url&{urllib.parse.urlencode(params)}"
    iframe(url, height=700, scrolling=True)
    if st.button("Close & Sync Data"): st.rerun()

# --- 4. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_all_data(TEAM_URL, "TEAM")

if not st.session_state.auth:
    st.title("Performance Hub Login")
    with st.form("login"):
        u_email = st.text_input("Work Email").lower().strip()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['email'] == u_email) & (team_db['pass'].astype(str) == str(u_pass))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. GLOBAL FILTERS ---
user = st.session_state.auth
kpi_raw = load_all_data(KPI_URL, "KPI")
dsat_raw = load_all_data(DSAT_URL, "DSAT")

st.sidebar.title("Configuration")
freq_mode = st.sidebar.radio("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

# Frequency Date Filtering
if freq_mode == "Daily":
    available = sorted(kpi_raw['date_dt'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Date", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    k_f, d_f = kpi_raw[kpi_raw['date_dt'] == sel], dsat_raw[dsat_raw['date_dt'].dt.date == sel.date()]
elif freq_mode == "Weekly":
    kpi_raw['week'] = kpi_raw['date_dt'].dt.to_period('W').apply(lambda r: r.start_time)
    available = sorted(kpi_raw['week'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Week", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    k_f, d_f = kpi_raw[kpi_raw['week'] == sel], dsat_raw[(dsat_raw['date_dt'] >= sel) & (dsat_raw['date_dt'] < sel + pd.Timedelta(days=7))]
else:
    kpi_raw['period'] = kpi_raw['date_dt'].dt.strftime('%B %Y') if freq_mode == "Monthly" else kpi_raw['date_dt'].dt.year
    available = kpi_raw.sort_values('date_dt', ascending=False)['period'].unique()
    sel = st.sidebar.selectbox(f"Select {freq_mode[:-2]}", available)
    k_f = kpi_raw[kpi_raw['period'] == sel]
    d_f = dsat_raw[dsat_raw['date_dt'].dt.strftime('%B %Y') == sel] if freq_mode == "Monthly" else dsat_raw[dsat_raw['date_dt'].dt.year == sel]

# Access Hierarchy
access = str(user.get('level', 'IC')).strip()
scoped_emails = []

if access == "Admin":
    sr_mgr = st.sidebar.selectbox("View Mode", ["Entire Organisation", "Jarvis Sokolowich", "Sumit Ludhwani"])
    if sr_mgr == "Entire Organisation": scoped_emails = team_db['email'].unique()
    else:
        mgrs = team_db[team_db['mgr'] == sr_mgr]['name'].unique()
        sel_mgr = st.sidebar.selectbox(f"Managers under {sr_mgr}", ["All Teams"] + list(mgrs))
        if sel_mgr == "All Teams": scoped_emails = team_db[team_db['mgr'] == sr_mgr]['email'].unique()
        else:
            advs = team_db[team_db['mgr'] == sel_mgr]['name'].unique()
            sel_adv = st.sidebar.selectbox("Select Advisor", ["Full Team"] + list(advs))
            scoped_emails = [team_db[team_db['name'] == sel_adv]['email'].values[0]] if sel_adv != "Full Team" else team_db[team_db['mgr'] == sel_mgr]['email'].unique()
elif access == "Manager":
    my_advs = team_db[team_db['mgr'] == user['name']]
    view = st.sidebar.selectbox("View Mode", ["Team Overview", "Specific Advisor"])
    if view == "Team Overview": scoped_emails = my_advs['email'].unique()
    else: scoped_emails = [my_advs[my_advs['name'] == st.sidebar.selectbox("Select Advisor", my_advs['name'].unique())]['email'].values[0]]
else: scoped_emails = [user['email']]

f_kpi = k_f[k_f['email'].isin(scoped_emails)]
f_dsat = d_f[d_f['email'].isin(scoped_emails)]

# --- 7. MAIN UI ---
st.title("Implementation Team Performance Hub")
st.success(f"Welcome {user['name']}!! | Access Level : {access}")

tabs = st.tabs(["Performance Overview", "DSAT Analysis"] + (["Leaderboard"] if access != "IC" else []))

with tabs[0]:
    avg_score = f_kpi['shift_score'].mean() if not f_kpi.empty else 0
    st.info(f"**Performance Narrative:** In the selected timeframe, the group achieved an average Shift Score of **{avg_score:.2f}%**. High Satisfied Survey rates indicate strong client sentiment.")
    
    st.markdown("### Performance Summary")
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

    st.markdown("### Performance Trends")
    if not f_kpi.empty:
        trend = f_kpi.groupby('date_dt').agg({'sent_rate':'mean', 'sat_rate':'mean', 'shift_score':'mean', 'ob':'sum', 'qa':'sum'}).reset_index().sort_values('date_dt')
        st.plotly_chart(px.line(trend, x='date_dt', y='sent_rate', title="Trend of Avg Survey Sent (%)", markers=True), use_container_width=True)
        st.plotly_chart(px.line(trend, x='date_dt', y='sat_rate', title="Trend of Avg Satisfied Survey (%)", markers=True), use_container_width=True)
        st.plotly_chart(px.line(trend, x='date_dt', y='shift_score', title="Trend of Avg Shift Score (%)", markers=True), use_container_width=True)
        st.plotly_chart(px.bar(trend, x='date_dt', y='ob', title="Trend of Total OB Calls"), use_container_width=True)
        st.plotly_chart(px.bar(trend, x='date_dt', y='qa', title="Trend of Total OH Calls"), use_container_width=True)

with tabs[1]:
    st.markdown("### DSAT Summary")
    pending = len(f_dsat[f_dsat['feedback'].isna() | (f_dsat['feedback'] == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", f"{len(f_dsat)}")
    s2.metric("Feedback Pending", f"{pending}")
    s3.metric("Controllable", f"{len(f_dsat[f_dsat['type'] == 'Controllable'])}")
    s4.metric("Uncontrollable", f"{len(f_dsat[f_dsat['type'] == 'Uncontrollable'])}")

    st.markdown("### DSAT Audit Log")
    if not f_dsat.empty:
        f_table = f_dsat.merge(team_db[['email', 'name', 'mgr']], on='email', how='left')
        df_view = f_table[['date_dt', 'name_y', 'mgr_y', 'link', 'type', 'feedback']].fillna("-")
        df_view.columns = ["Date", "Advisor", "Manager", "Chat Link", "Type", "Feedback"]
        st.dataframe(df_view, hide_index=True, use_container_width=True)

if access != "IC":
    with tabs[2]:
        st.markdown("### 🏆 Leadership Rankings")
        ldb = k_f.groupby('name').agg({'sent_rate':'mean', 'sat_rate':'mean', 'qa':'sum', 'ob':'sum'}).reset_index().round(2)
        st.write("**Success Champions (Sent Rate ≥ 85%, Sat ≥ 90%)**")
        champs = ldb[(ldb['sent_rate'] >= 85) & (ldb['sat_rate'] >= 90)].sort_values('sat_rate', ascending=False)
        st.dataframe(champs[['name', 'sat_rate', 'sent_rate']], hide_index=True, use_container_width=True)
        st.write("**Overall Rankings**")
        st.dataframe(ldb.sort_values('sat_rate', ascending=False), hide_index=True, use_container_width=True)

st.sidebar.divider()
if st.sidebar.button("Logout"): st.session_state.auth = None; st.rerun()
