import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
import re
from streamlit.components.v1 import iframe
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

# PRE-FILLED FORM CONFIG
FORM_ID = "YOUR_FORM_ID" # Replace with actual form ID
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub", page_icon="🚀")

# --- 2. SaaS/GHL THEME ENGINE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    
    :root { --ghl-blue: #0052FF; }

    /* Card Styling */
    .stMetric {
        background-color: var(--secondary-background-color);
        padding: 24px; border-radius: 16px; border: 1px solid rgba(0, 82, 255, 0.1);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    }
    
    /* GHL Sidebar Branding */
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 180px; height: 60px; margin-left: 20px; margin-top: 20px;
        filter: brightness(0) invert(1); /* Adaptive for Dark Mode */
    }
    
    /* Tab Styling */
    .stTabs [aria-selected="true"] { 
        background-color: var(--ghl-blue) !important; color: white !important; border-radius: 8px;
    }
    
    /* Insight Narrative Box */
    div.stInfo {
        background-color: rgba(0, 82, 255, 0.05); border: 1px solid rgba(0, 82, 255, 0.2);
        border-radius: 12px; padding: 20px; color: var(--text-color);
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA PROCESSING ---
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
def load_and_standardize(url, sheet_type):
    try:
        df = pd.read_csv(url)
        # Clean headers: Strip tabs/spaces, handle BOM, convert to predictable underscore format
        df.columns = [re.sub(r'\s+', '_', str(c).strip().replace('\ufeff', '').replace('"', '')).lower() for c in df.columns]
        
        # Field Normalization Mapping
        rmap = {
            "advisor_name": "name", "agent_name": "name",
            "advisor_email": "email", "email": "email",
            "manager": "mgr", "manager_name": "mgr",
            "access_level": "level", "password": "pass",
            "ia": "ia_raw", "advisor_call_time": "call_raw",
            "sent_rate_%": "sent_rate", "satisfied_survey_%": "sat_rate",
            "ob_calls": "ob", "q/a_calls": "qa", "total_survey": "surveys",
            "timestamp": "ts", "chat_dsat_url": "link"
        }
        df = df.rename(columns=rmap)
        if 'email' in df.columns: df['email'] = df['email'].astype(str).str.strip().str.lower()
        
        if sheet_type == "KPI":
            # Date Parsing: handles format Feb'27'26
            df['date_dt'] = pd.to_datetime(df['date_level_-_as'], format="%b'%d'%y", errors='coerce')
            # Duration conversions
            df['ia_min'] = df['ia_raw'].apply(parse_duration)
            df['call_min'] = df['call_raw'].apply(parse_duration)
            df['shift_score'] = np.where(df['ia_min'] > 0, (df['call_min']/df['ia_min']*100), 0)
            # Robust Percentage scaling
            for col in ['sent_rate', 'sat_rate']:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('%',''), errors='coerce').fillna(0)
                # If mean is low, it's likely decimal (0.85 -> 85)
                if df[col].max() <= 1.1: df[col] = df[col] * 100
        
        if sheet_type == "DSAT":
            df['ts_dt'] = pd.to_datetime(df['ts'], errors='coerce')
            
        return df
    except Exception as e:
        st.error(f"Error loading {sheet_type}: {e}")
        return pd.DataFrame()

def create_ghl_gauge(title, value, target=None):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = round(value, 2), domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number = {'suffix': "%", 'font': {'color': '#0052FF', 'size': 38}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"},
                 'steps': [{'range': [0, 70], 'color': "#FFEDEB"}, {'range': [70, 85], 'color': "#FFF9E6"}, {'range': [85, 100], 'color': "#E6F9ED"}],
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target} if target else None}
    ))
    fig.update_layout(height=220, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
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
    c_l1, c_l2 = st.columns([1, 4])
    with c_l1: st.image(LOGO_URL, width=150)
    with c_l2: st.title("Implementation Team Performance Hub")
    with st.form("login"):
        u_email = st.text_input("Work Email").lower().strip()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['email'] == u_email) & (team_db['pass'].astype(str) == str(u_pass))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict(); st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. DATA FETCHING ---
user = st.session_state.auth
kpi_raw = load_and_standardize(KPI_URL, "KPI")
dsat_raw = load_and_standardize(DSAT_URL, "DSAT")

# --- 6. FREQUENCY & HIERARCHY LOGIC ---
st.sidebar.title("Navigation Filters")
freq = st.sidebar.radio("Select Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

# Select Time Range
if freq == "Daily":
    available = sorted(kpi_raw['date_dt'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Date", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    k_f = kpi_raw[kpi_raw['date_dt'] == sel]
    d_f = dsat_raw[dsat_raw['ts_dt'].dt.date == sel.date()]
elif freq == "Weekly":
    kpi_raw['wk'] = kpi_raw['date_dt'].dt.to_period('W').apply(lambda r: r.start_time)
    available = sorted(kpi_raw['wk'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Week", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    k_f = kpi_raw[kpi_raw['wk'] == sel]
    d_f = dsat_raw[(dsat_raw['ts_dt'] >= sel) & (dsat_raw['ts_dt'] < sel + pd.Timedelta(days=7))]
else:
    kpi_raw['mo'] = kpi_raw['date_dt'].dt.strftime('%B %Y')
    available = kpi_raw.sort_values('date_dt', ascending=False)['mo'].unique()
    sel = st.sidebar.selectbox("Select Month", available)
    k_f = kpi_raw[kpi_raw['mo'] == sel]
    d_f = dsat_raw[dsat_raw['ts_dt'].dt.strftime('%B %Y') == sel]

# Access Control Drill-down
access = str(user.get('level', 'IC')).strip()
scoped_emails = []

if access == "Admin":
    mode = st.sidebar.selectbox("Organization Scoping", ["Entire Organisation", "Jarvis Sokolowich", "Sumit Ludhwani"])
    if mode == "Entire Organisation": scoped_emails = team_db['email'].unique()
    else:
        mgrs = team_db[team_db['mgr'] == mode]['name'].unique()
        sel_mgr = st.sidebar.selectbox(f"Managers under {mode}", ["All Teams"] + list(mgrs))
        if sel_mgr == "All Teams": scoped_emails = team_db[team_db['mgr'] == mode]['email'].unique()
        else:
            advs = team_db[team_db['mgr'] == sel_mgr]['name'].unique()
            sel_adv = st.sidebar.selectbox(f"Advisors under {sel_mgr}", ["Full Team"] + list(advs))
            scoped_emails = [team_db[team_db['name'] == sel_adv]['email'].values[0]] if sel_adv != "Full Team" else team_db[team_db['mgr'] == sel_mgr]['email'].unique()

elif access == "Manager":
    mode = st.sidebar.selectbox("View Mode", ["Team Overview", "Specific Advisor"])
    my_advs = team_db[team_db['mgr'] == user['name']]
    if mode == "Team Overview": scoped_emails = my_advs['email'].unique()
    else: scoped_emails = [my_advs[my_advs['name'] == st.sidebar.selectbox("Select Advisor", my_advs['name'].unique())]['email'].values[0]]
else: scoped_emails = [user['email']]

# Final Data Apply
f_kpi = k_f[k_f['email'].isin(scoped_emails)]
f_dsat = d_f[d_f['email'].isin(scoped_emails)]

# --- 7. MAIN UI ---
st.title("Implementation Team Performance Hub")
st.success(f"Welcome {user['name']}!! | Access Level : {access}")

tabs = st.tabs(["Performance Overview", "DSAT Analysis"] + (["Leaderboard"] if access != "IC" else []))

with tabs[0]:
    # a. Narrative Logic
    avg_score = f_kpi['shift_score'].mean() if not f_kpi.empty else 0
    st.info(f"**Performance Narrative:** For the period ({sel}), the group is maintaining a Shift Score of **{avg_score:.2f}%**. High Sent Rates in recent days suggest proactive client engagement.")
    
    # b. Gauges
    st.markdown("### Performance Summary")
    g1, g2, g3 = st.columns(3)
    active_kpi = f_kpi[f_kpi['surveys'] > 0]
    avg_sent = active_kpi['sent_rate'].mean() if not active_kpi.empty else 0
    avg_sat = active_kpi['sat_rate'].mean() if not active_kpi.empty else 0
    
    g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
    g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
    g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_score, 85), use_container_width=True)
    
    m1, m2 = st.columns(2)
    m1.metric("Total OB Calls", f"{int(f_kpi['ob'].sum()):,}")
    m2.metric("Total OH Calls (QA)", f"{int(f_kpi['qa'].sum()):,}")

    # c. Trends
    st.markdown("### Performance Trends")
    if not f_kpi.empty:
        trend = f_kpi.groupby('date_dt').agg({'sent_rate':'mean', 'sat_rate':'mean', 'shift_score':'mean', 'ob':'sum', 'qa':'sum'}).reset_index()
        t1, t2 = st.columns(2)
        t1.plotly_chart(px.line(trend, x='date_dt', y=['sent_rate', 'sat_rate'], title="Survey & Satisfaction Trend (%)", markers=True), use_container_width=True)
        t2.plotly_chart(px.line(trend, x='date_dt', y='shift_score', title="Shift Score Trend (%)", markers=True), use_container_width=True)
        t3, t4 = st.columns(2)
        t3.plotly_chart(px.bar(trend, x='date_dt', y='ob', title="Total OB Calls"), use_container_width=True)
        t4.plotly_chart(px.bar(trend, x='date_dt', y='qa', title="Total OH Calls"), use_container_width=True)

with tabs[1]:
    # a. Summary
    st.markdown("### DSAT Summary")
    pending = len(f_dsat[f_dsat['feedback'].isna() | (f_dsat['feedback'] == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", f"{len(f_dsat)}")
    s2.metric("Pending Feedback", f"{pending}")
    s3.metric("Controllable", f"{len(f_dsat[f_dsat['type'] == 'Controllable'])}")
    s4.metric("Uncontrollable", f"{len(f_dsat[f_dsat['type'] == 'Uncontrollable'])}")

    # b. Table
    st.markdown("### DSAT Audit Log")
    if not f_dsat.empty:
        # Re-merge for table details
        f_table = f_dsat.merge(team_db[['email', 'name', 'mgr']], on='email', how='left')
        f_table['feedback'] = f_table['feedback'].fillna("-")
        f_table['type'] = f_table['type'].fillna("-")
        
        col_w = [1.5, 2, 1.5, 1, 1.2, 2.5] + ([1] if access != "IC" else [])
        headers = ["Date", "Advisor", "Manager", "Chat", "Type", "Feedback"] + (["Action"] if access != "IC" else [])
        cols = st.columns(col_w)
        for i, h in enumerate(headers): cols[i].write(f"**{h}**")
        
        for idx, row in f_table.reset_index().iterrows():
            r = st.columns(col_w)
            r[0].write(str(row['ts'])[:10])
            r[1].write(row['name_y'])
            r[2].write(row['mgr_y'])
            r[3].markdown(f"[🔗 Link]({row['link']})")
            r[4].write(row['type'])
            r[5].write(row['feedback'])
            if access != "IC" and r[6].button("Update", key=f"upd_{idx}"): open_form_dialog(row)

if access != "IC":
    with tabs[2]:
        st.markdown("### 🏆 Leadership Rankings")
        ldb = k_f.groupby('name').agg({'sent_rate':'mean', 'sat_rate':'mean', 'qa':'sum', 'ob':'sum'}).reset_index().round(2)
        
        st.write("**✨ Success Champions**")
        st.caption("Criteria: Avg Survey Sent ≥ 85.00% and Avg Satisfied ≥ 90.00%")
        champs = ldb[(ldb['sent_rate'] >= 85) & (ldb['sat_rate'] >= 90)].sort_values('sat_rate', ascending=False)
        st.dataframe(champs[['name', 'sat_rate', 'sent_rate']], hide_index=True, use_container_width=True)
        
        l1, l2 = st.columns(2)
        with l1:
            st.write("**Top QA Call Volume**")
            st.dataframe(ldb.sort_values('qa', ascending=False)[['name', 'qa']], hide_index=True, use_container_width=True)
        with l2:
            st.write("**Top OB Outreach**")
            st.dataframe(ldb.sort_values('ob', ascending=False)[['name', 'ob']], hide_index=True, use_container_width=True)

st.sidebar.divider()
if st.sidebar.button("Logout"): st.session_state.auth = None; st.rerun()
