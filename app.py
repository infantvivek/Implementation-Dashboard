import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
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
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; }
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
def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    parts = str(time_str).lower().split()
    for p in parts:
        if 'h' in p: h = int(p.replace('h', ''))
        elif 'm' in p: m = int(p.replace('m', ''))
    return (h * 60) + m

@st.cache_data(ttl=60)
def load_and_clean_data(url, sheet_type):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '')
        if 'Email' in df.columns: df['Email'] = df['Email'].str.strip().str.lower()
        if 'Advisor Email' in df.columns: df['Advisor Email'] = df['Advisor Email'].str.strip().str.lower()
        
        if sheet_type == "KPI":
            df['IA_Mins'] = df['IA'].apply(parse_time)
            df['Call_Mins'] = df['Advisor Call Time '].apply(parse_time)
            df['Shift_Score'] = np.where(df['IA_Mins'] > 0, (df['Call_Mins']/df['IA_Mins']*100), 0)
            df['Date_Parsed'] = pd.to_datetime(df['Date_level - AS'], format="%b'%d'%y", errors='coerce')
        return df
    except: return pd.DataFrame()

# --- 4. GAUGE GENERATOR ---
def create_ghl_gauge(title, value, target=None, color_steps=True):
    steps = [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}] if color_steps else []
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 18, 'color': 'gray'}},
        number = {'suffix': "%", 'font': {'color': '#0052FF', 'size': 35}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"}, 'bgcolor': "white", 'steps': steps,
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target} if target else None}
    ))
    fig.update_layout(height=230, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update DSAT Record", width="large")
def open_form_dialog(row):
    params = {ENTRY_KEY: row['RecordKey'], ENTRY_FEEDBACK: row['Feedback'], ENTRY_TYPE: row['Type']}
    url = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url&{urllib.parse.urlencode(params)}"
    iframe(url, height=700, scrolling=True)
    if st.button("Close & Sync"): st.rerun()

# --- 5. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_clean_data(TEAM_URL, "TEAM")

if not st.session_state.auth:
    col1, col2 = st.columns([1, 4])
    with col1: st.image(LOGO_URL, width=150)
    with col2: st.title("Implementation Team Performance Hub")
    with st.form("login"):
        e_in, p_in = st.text_input("Work Email").lower().strip(), st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str) == str(p_in))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 6. DATA FETCHING ---
user = st.session_state.auth
kpi_raw = load_and_clean_data(KPI_URL, "KPI")
dsat_raw = load_and_clean_data(DSAT_URL, "DSAT")

# --- 7. SIDEBAR FILTERS & HIERARCHY ---
st.sidebar.title("Configuration")
freq = st.sidebar.selectbox("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"])
level = str(user.get('Access level', 'IC')).strip()
emails = []

if level == "Admin":
    directors = team_db[team_db['Advisor Name'].isin(team_db['Manager'].unique())]['Manager'].unique()
    view_mode = st.sidebar.selectbox("View Mode", ["Entire Organisation"] + list(directors))
    if view_mode == "Entire Organisation":
        emails = team_db['Email'].unique()
    else:
        mgrs = team_db[team_db['Manager'] == view_mode]['Advisor Name'].unique()
        mgr_sel = st.sidebar.selectbox("Select Manager", ["All Teams"] + list(mgrs))
        if mgr_sel == "All Teams":
            emails = team_db[team_db['Manager'].isin(mgrs)]['Email'].unique()
        else:
            advs = team_db[team_db['Manager'] == mgr_sel]['Advisor Name'].unique()
            adv_sel = st.sidebar.selectbox("Select Advisor", ["Full Team"] + list(advs))
            emails = [team_db[team_db['Advisor Name'] == adv_sel]['Email'].values[0]] if adv_sel != "Full Team" else team_db[team_db['Manager'] == mgr_sel]['Email'].unique()

elif level == "Manager":
    view_mode = st.sidebar.selectbox("View Mode", ["Team Overview", "Specific Advisor View"])
    if view_mode == "Team Overview":
        emails = team_db[team_db['Manager'] == user['Advisor Name']]['Email'].unique()
    else:
        advs = team_db[team_db['Manager'] == user['Advisor Name']]['Advisor Name'].unique()
        adv_sel = st.sidebar.selectbox("Select Advisor", list(advs))
        emails = [team_db[team_db['Advisor Name'] == adv_sel]['Email'].values[0]]

else: emails = [user['Email']]

f_kpi = kpi_raw[kpi_raw['Email'].isin(emails)]
f_dsat = dsat_raw[dsat_raw['Advisor Email'].isin(emails)]

# --- 8. MAIN UI ---
st.title("Implementation Team Performance Hub")
st.success(f"Welcome {user['Advisor Name']}!!, Access Level : {level}")

tabs_list = ["Performance Overview", "DSAT Analysis"]
if level in ["Admin", "Manager"]: tabs_list.append("Leaderboard")
tabs = st.tabs(tabs_list)

with tabs[0]:
    st.markdown("### Performance Narrative")
    avg_shift = f_kpi['Shift_Score'].mean() if not f_kpi.empty else 0
    st.info(f"The selected group is performing with an average shift score of {avg_shift:.2f}%. Ensure advisors are maximizing IA time relative to call duration to maintain efficiency targets.")
    
    st.markdown("### Performance Summary")
    g1, g2, g3 = st.columns(3)
    avg_sent = f_kpi['Sent Rate %'].mean() * 100 if not f_kpi.empty else 0
    avg_sat = f_kpi['Satisfied Survey %'].mean() * 100 if not f_kpi.empty else 0
    g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
    g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
    g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_shift, 85), use_container_width=True)
    
    b1, b2 = st.columns(2)
    b1.metric("Total OB Calls", int(f_kpi['OB Calls'].sum()))
    b2.metric("Total OH Calls", int(f_kpi['Q/A Calls'].sum())) # Mapped Q/A to OH as per prompt

    st.markdown("### Performance Trends")
    trend = f_kpi.groupby('Date_Parsed').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Shift_Score':'mean', 'OB Calls':'sum', 'Q/A Calls':'sum'}).reset_index()
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.line(trend, x='Date_Parsed', y=['Sent Rate %', 'Satisfied Survey %'], title="Survey Trends"), use_container_width=True)
    with c2:
        st.plotly_chart(px.line(trend, x='Date_Parsed', y='Shift_Score', title="Shift Score Trend"), use_container_width=True)

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
        col_w = [1.5, 2.5, 1.5, 3] + ([1] if level != "IC" else [])
        headers = ["Date", "Chat Link", "Type", "Feedback"] + (["Action"] if level != "IC" else [])
        cols = st.columns(col_w)
        for i, h in enumerate(headers): cols[i].write(f"**{h}**")
        for idx, row in f_dsat.reset_index().iterrows():
            r = st.columns(col_w)
            r[0].write(str(row['Timestamp'])[:10])
            r[1].markdown(f"[Chat Link]({row['Chat DSAT URL']})")
            r[2].write(row['Type'])
            r[3].write(row['Feedback'] if pd.notna(row['Feedback']) else "-")
            if level != "IC":
                if r[4].button("Update", key=f"dsat_{idx}"): open_form_dialog(row)

if len(tabs) > 2:
    with tabs[2]:
        st.markdown("### 🏆 Success Champions")
        st.caption("Criteria: Sent Rate ≥ 85% and Satisfied Survey % > 90%")
        ldb = f_kpi.groupby('Agent Name').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'}).reset_index()
        champs = ldb[(ldb['Sent Rate %'] >= 0.85) & (ldb['Satisfied Survey %'] > 0.90)]
        st.dataframe(champs[['Agent Name', 'Satisfied Survey %', 'Sent Rate %']], hide_index=True, use_container_width=True)
        
        l1, l2 = st.columns(2)
        l1.subheader("Total QA Calls"); l1.dataframe(ldb.sort_values('Q/A Calls', ascending=False)[['Agent Name', 'Q/A Calls']], hide_index=True)
        l2.subheader("Total OB Calls"); l2.dataframe(ldb.sort_values('OB Calls', ascending=False)[['Agent Name', 'OB Calls']], hide_index=True)
