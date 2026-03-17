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

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub")

# --- 2. THEME & BRANDING ---
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

# --- 3. DATA PROCESSING HELPERS ---
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
        df.columns = [str(c).strip().replace('\ufeff', '').replace('"', '') for c in df.columns]
        
        # Standardize email columns for join reliability
        for col in ['Email', 'Advisor Email']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.lower()
        
        if sheet_type == "KPI":
            df['Date_Parsed'] = pd.to_datetime(df['Date_level - AS'], format="%b'%d'%y", errors='coerce')
            df['ia_mins'] = df['IA'].apply(parse_time)
            df['call_mins'] = df['Advisor Call Time '].apply(parse_time)
            df['Shift_Score'] = np.where(df['ia_mins'] > 0, (df['call_mins']/df['ia_mins']*100), 0)
            for col in ['Sent Rate %', 'Satisfied Survey %', 'OB Calls', 'Q/A Calls', 'Total Survey']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if sheet_type == "DSAT":
            df['Timestamp_Parsed'] = pd.to_datetime(df['Timestamp'], errors='coerce')
            if 'Processed' in df.columns:
                df = df[df['Processed'] != 'DUPLICATE']
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
    fig.update_layout(height=210, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update Record", width="large")
def open_form_dialog(row):
    params = {ENTRY_KEY: row['RecordKey'], ENTRY_FEEDBACK: row.get('Feedback', ''), ENTRY_TYPE: row.get('Type', '')}
    url = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url&{urllib.parse.urlencode(params)}"
    iframe(url, height=700, scrolling=True)
    if st.button("Close & Sync Dashboard"): st.rerun()

# --- 4. AUTH & DATA LOAD ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_standardize(TEAM_URL, "TEAM")

if not st.session_state.auth:
    col1, col2 = st.columns([1, 4])
    with col1: st.image(LOGO_URL, width=150)
    with col2: st.title("Implementation Team Performance Hub")
    with st.form("login"):
        e_in, p_in = st.text_input("Work Email").lower().strip(), st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str) == str(p_in))]
            if not match.empty: st.session_state.auth = match.iloc[0].to_dict(); st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

user, kpi_raw, dsat_raw = st.session_state.auth, load_and_standardize(KPI_URL, "KPI"), load_and_standardize(DSAT_URL, "DSAT")

# --- 5. GLOBAL FILTERS (FREQUENCY & HIERARCHY) ---
st.sidebar.title("Navigation Filters")
freq = st.sidebar.radio("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

# Frequency Drill-down
if freq == "Daily":
    sel = st.sidebar.selectbox("Select Date", sorted(kpi_raw['Date_Parsed'].dropna().unique(), reverse=True), format_func=lambda x: x.strftime('%d-%m-%Y'))
    k_f, d_f = kpi_raw[kpi_raw['Date_Parsed'] == sel], dsat_raw[dsat_raw['Timestamp_Parsed'].dt.date == sel.date()]
elif freq == "Weekly":
    kpi_raw['W_Start'] = kpi_raw['Date_Parsed'].dt.to_period('W').apply(lambda r: r.start_time)
    sel = st.sidebar.selectbox("Select Week", sorted(kpi_raw['W_Start'].dropna().unique(), reverse=True), format_func=lambda x: x.strftime('%d-%m-%Y'))
    k_f, d_f = kpi_raw[kpi_raw['W_Start'] == sel], dsat_raw[(dsat_raw['Timestamp_Parsed'] >= sel) & (dsat_raw['Timestamp_Parsed'] < sel + pd.Timedelta(days=7))]
else:
    kpi_raw['Month'] = kpi_raw['Date_Parsed'].dt.strftime('%B %Y')
    sel = st.sidebar.selectbox("Select Period", kpi_raw.sort_values('Date_Parsed', ascending=False)['Month'].unique())
    k_f, d_f = kpi_raw[kpi_raw['Month'] == sel], dsat_raw[dsat_raw['Timestamp_Parsed'].dt.strftime('%B %Y') == sel]

# Hierarchy
level = str(user.get('Access level', 'IC')).strip()
emails = []

if level == "Admin":
    sr_mgrs = ["Entire Organisation", "Jarvis Sokolowich", "Sumit Ludhwani"]
    view = st.sidebar.selectbox("Sr. Manager View", sr_mgrs)
    if view == "Entire Organisation": emails = team_db['Email'].unique()
    else:
        mgr_list = team_db[team_db['Manager'] == view]['Advisor Name'].unique()
        mgr_sel = st.sidebar.selectbox(f"Managers under {view}", ["All Teams"] + list(mgr_list))
        if mgr_sel == "All Teams": emails = team_db[team_db['Manager'] == view]['Email'].unique()
        else:
            adv_list = team_db[team_db['Manager'] == mgr_sel]['Advisor Name'].unique()
            adv_sel = st.sidebar.selectbox(f"Advisors under {mgr_sel}", ["Full Team"] + list(adv_list))
            emails = [team_db[team_db['Advisor Name'] == adv_sel]['Email'].values[0]] if adv_sel != "Full Team" else team_db[team_db['Manager'] == mgr_sel]['Email'].unique()
elif level == "Manager":
    my_team = team_db[team_db['Manager'] == user['Advisor Name']]
    view = st.sidebar.selectbox("View Mode", ["Team Overview", "Individual Advisor View"])
    if view == "Team Overview": emails = my_team['Email'].unique()
    else: emails = [my_team[my_team['Advisor Name'] == st.sidebar.selectbox("Select Advisor", my_team['Advisor Name'].unique())]['Email'].values[0]]
else: emails = [user['Email']]

f_kpi = k_f[k_f['Email'].isin(emails)]
f_dsat = d_f[d_f['Advisor Email'].isin(emails)]

# --- 6. UI CONTENT ---
st.title("Implementation Team Performance Hub")
st.info(f"Welcome **{user['Advisor Name']}**!!, Access Level : **{level}**")

tabs = st.tabs(["Performance Overview", "DSAT Analysis"] + (["Leaderboard"] if level != "IC" else []))

with tabs[0]:
    avg_shift = f_kpi['Shift_Score'].mean() if not f_kpi.empty else 0
    st.markdown("### Performance Narrative")
    st.info(f"The group is performing with an average shift score of {avg_shift:.2f}%. Monitoring trends suggests maintaining high survey sent rates is key to meeting benchmarks.")
    
    g1, g2, g3 = st.columns(3)
    avg_sent = (f_kpi['Sent Rate %'].mean() * 100) if not f_kpi.empty else 0
    avg_sat = (f_kpi['Satisfied Survey %'].mean() * 100) if not f_kpi.empty else 0
    g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
    g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
    g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_shift, 85), use_container_width=True)
    
    m1, m2 = st.columns(2)
    m1.metric("Total OB Calls", int(f_kpi['OB Calls'].sum()))
    m2.metric("Total OH Calls (QA)", int(f_kpi['Q/A Calls'].sum()))

    st.markdown("### Performance Trends")
    trend = f_kpi.groupby('Date_Parsed').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Shift_Score':'mean', 'OB Calls':'sum', 'Q/A Calls':'sum'}).reset_index()
    t1, t2 = st.columns(2); t1.plotly_chart(px.line(trend, x='Date_Parsed', y='Sent Rate %', title="Survey Sent Trend"), use_container_width=True)
    t2.plotly_chart(px.line(trend, x='Date_Parsed', y='Satisfied Survey %', title="Satisfied Survey Trend"), use_container_width=True)
    t3, t4, t5 = st.columns(3); t3.plotly_chart(px.line(trend, x='Date_Parsed', y='Shift_Score', title="Shift Score Trend"), use_container_width=True)
    t4.plotly_chart(px.line(trend, x='Date_Parsed', y='OB Calls', title="Total OB Calls Trend"), use_container_width=True)
    t5.plotly_chart(px.line(trend, x='Date_Parsed', y='Q/A Calls', title="Total OH Calls Trend"), use_container_width=True)

with tabs[1]:
    st.markdown("### DSAT Summary")
    pending = len(f_dsat[f_dsat['Feedback'].isna() | (f_dsat['Feedback'] == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", len(f_dsat))
    s2.metric("Feedback Pending", pending)
    s3.metric("Controllable", len(f_dsat[f_dsat['Type'] == 'Controllable']))
    s4.metric("Uncontrollable", len(f_dsat[f_dsat['Type'] == 'Uncontrollable']))

    st.markdown("### DSAT Analysis Table")
    if not f_dsat.empty:
        display_dsat = f_dsat.merge(team_db[['Email', 'Advisor Name', 'Manager']], left_on='Advisor Email', right_on='Email', how='left')
        col_w = [1.5, 2, 2, 1, 1.2, 3] + ([1] if level != "IC" else [])
        headers = ["Date", "Advisor", "Manager", "Link", "Type", "Feedback"] + (["Action"] if level != "IC" else [])
        cols = st.columns(col_w)
        for idx, row in display_dsat.reset_index().iterrows():
            r = st.columns(col_w)
            r[0].write(str(row['Timestamp'])[:10]); r[1].write(row['Advisor Name']); r[2].write(row['Manager_y'])
            r[3].markdown(f"[Link]({row['Chat DSAT URL']})"); r[4].write(row['Type'] if pd.notna(row['Type']) else "-")
            r[5].write(row['Feedback'] if pd.notna(row['Feedback']) else "-")
            if level != "IC" and r[6].button("Update", key=f"upd_{idx}"): open_form_dialog(row)

if level != "IC":
    with tabs[2]:
        st.markdown("### 🏆 Leaderboards")
        ldb = k_f.groupby('Agent Name').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'}).reset_index()
        ldb['Satisfied Survey %'] *= 100
        st.write("**Success Champions**"); st.dataframe(ldb[(ldb['Sent Rate %'] >= 0.85) & (ldb['Satisfied Survey %'] >= 90)], hide_index=True, use_container_width=True)
        c1, c2 = st.columns(2); c1.subheader("Total QA"); c1.dataframe(ldb.sort_values('Q/A Calls', ascending=False)[['Agent Name', 'Q/A Calls']], hide_index=True)
        c2.subheader("Total OB"); c2.dataframe(ldb.sort_values('OB Calls', ascending=False)[['Agent Name', 'OB Calls']], hide_index=True)

st.sidebar.divider()
if st.sidebar.button("Logout"): st.session_state.auth = None; st.rerun()
