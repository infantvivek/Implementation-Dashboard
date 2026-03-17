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

# PRE-FILLED FORM CONFIG
FORM_ID = "YOUR_FORM_ID"
ENTRY_KEY, ENTRY_FEEDBACK, ENTRY_TYPE = "entry.1", "entry.2", "entry.3"

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub")

# --- 2. GHL DYNAMIC THEME (LIGHT/DARK) ---
st.markdown("""
    <style>
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; }
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 160px; height: 50px; margin-left: 20px; margin-top: 20px; filter: invert(1) brightness(2);
    }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; }
    div.stInfo { background-color: rgba(0, 82, 255, 0.08); border-left: 5px solid #0052FF; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA PROCESSING ---
def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    h, m = 0, 0
    parts = str(time_str).lower().split()
    for p in parts:
        if 'h' in p: h = int(p.replace('h', ''))
        elif 'm' in p: m = int(p.replace('m', ''))
    return (h * 60) + m

@st.cache_data(ttl=60)
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '')
        return df
    except: return pd.DataFrame()

def create_ghl_gauge(title, value, target):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number = {'suffix': "%", 'font': {'color': '#0052FF'}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"},
                 'steps': [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}],
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target}}
    ))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update DSAT Record", width="large")
def open_form_dialog(row):
    params = {ENTRY_KEY: row['RecordKey'], ENTRY_FEEDBACK: row.get('Feedback', ''), ENTRY_TYPE: row.get('Type', '')}
    url = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url&{urllib.parse.urlencode(params)}"
    iframe(url, height=700, scrolling=True)
    if st.button("Close & Sync"): st.rerun()

# --- 4. DATA INITIALIZATION ---
team_db = load_data(TEAM_URL)
kpi_db = load_data(KPI_URL)
dsat_db = load_data(DSAT_URL)

# Normalize Emails
for d in [team_db, kpi_db, dsat_db]:
    email_col = 'Email' if 'Email' in d.columns else 'Advisor Email'
    if email_col in d.columns: d[email_col] = d[email_col].str.strip().str.lower()

# Date Conversion Logic
if not kpi_db.empty:
    kpi_db['Date_Parsed'] = pd.to_datetime(kpi_db['Date_level - AS'], format="%b'%d'%y", errors='coerce')
    kpi_db['IA_Mins'] = kpi_db['IA'].apply(parse_time)
    kpi_db['Call_Mins'] = kpi_db['Advisor Call Time '].apply(parse_time)
    kpi_db['Shift_Score'] = np.where(kpi_db['IA_Mins'] > 0, (kpi_db['Call_Mins']/kpi_db['IA_Mins']*100), 0)

# --- 5. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
if not st.session_state.auth:
    c1, c2 = st.columns([1, 4])
    with c1: st.image(LOGO_URL, width=150)
    with c2: st.title("Implementation Team Performance Hub")
    with st.form("login"):
        e_in, p_in = st.text_input("Work Email").lower().strip(), st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str) == str(p_in))]
            if not match.empty: st.session_state.auth = match.iloc[0].to_dict(); st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 6. HIERARCHY & DATE FILTERS ---
user = st.session_state.auth
st.sidebar.title("Navigation")
freq = st.sidebar.radio("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

# Frequency Date Drill-down
if freq == "Daily":
    sel_date = st.sidebar.selectbox("Select Date", sorted(kpi_db['Date_Parsed'].dropna().unique(), reverse=True), format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_t, f_dsat_t = kpi_db[kpi_db['Date_Parsed'] == sel_date], dsat_db[pd.to_datetime(dsat_db['Timestamp']).dt.date == sel_date.date()]
elif freq == "Weekly":
    kpi_db['Week'] = kpi_db['Date_Parsed'].dt.to_period('W').apply(lambda r: r.start_time)
    sel_date = st.sidebar.selectbox("Select Week Starting", sorted(kpi_db['Week'].dropna().unique(), reverse=True), format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_t, f_dsat_t = kpi_db[kpi_db['Week'] == sel_date], dsat_db[(pd.to_datetime(dsat_db['Timestamp']) >= sel_date) & (pd.to_datetime(dsat_db['Timestamp']) < sel_date + pd.Timedelta(days=7))]
elif freq == "Monthly":
    kpi_db['Month'] = kpi_db['Date_Parsed'].dt.strftime('%B %Y')
    sel_date = st.sidebar.selectbox("Select Month", kpi_db.sort_values('Date_Parsed', ascending=False)['Month'].unique())
    f_kpi_t, f_dsat_t = kpi_raw = kpi_db[kpi_db['Month'] == sel_date], dsat_db[pd.to_datetime(dsat_db['Timestamp']).dt.strftime('%B %Y') == sel_date]
else:
    kpi_db['Year'] = kpi_db['Date_Parsed'].dt.year
    sel_date = st.sidebar.selectbox("Select Year", sorted(kpi_db['Year'].dropna().unique(), reverse=True))
    f_kpi_t, f_dsat_t = kpi_db[kpi_db['Year'] == sel_date], dsat_db[pd.to_datetime(dsat_db['Timestamp']).dt.year == sel_date]

# Hierarchy Filtering
level = str(user.get('Access level', 'IC')).strip()
emails = []

if level == "Admin":
    directors = team_db[team_db['Advisor Name'].isin(team_db['Manager'].unique())]['Manager'].unique()
    view_mode = st.sidebar.selectbox("View Mode", ["Entire Organisation"] + list(directors))
    if view_mode == "Entire Organisation": emails = team_db['Email'].unique()
    else:
        mgrs = team_db[team_db['Manager'] == view_mode]['Advisor Name'].unique()
        mgr_sel = st.sidebar.selectbox("Select Manager Team", ["All Teams"] + list(mgrs))
        if mgr_sel == "All Teams": emails = team_db[team_db['Manager'].isin(mgrs)]['Email'].unique()
        else:
            advs = team_db[team_db['Manager'] == mgr_sel]['Advisor Name'].unique()
            adv_sel = st.sidebar.selectbox("Advisor Drill-down", ["Full Team"] + list(advs))
            emails = [team_db[team_db['Advisor Name'] == adv_sel]['Email'].values[0]] if adv_sel != "Full Team" else team_db[team_db['Manager'] == mgr_sel]['Email'].unique()

elif level == "Manager":
    view_mode = st.sidebar.selectbox("View Mode", ["Team Overview", "Specific Advisor View"])
    if view_mode == "Team Overview": emails = team_db[team_db['Manager'] == user['Advisor Name']]['Email'].unique()
    else:
        adv_sel = st.sidebar.selectbox("Select Advisor", list(team_db[team_db['Manager'] == user['Advisor Name']]['Advisor Name'].unique()))
        emails = [team_db[team_db['Advisor Name'] == adv_sel]['Email'].values[0]]

else: emails = [user['Email']]

f_kpi = f_kpi_t[f_kpi_t['Email'].isin(emails)]
f_dsat = f_dsat_t[f_dsat_t['Advisor Email'].isin(emails)]

# --- 7. MAIN UI ---
st.title("Implementation Team Performance Hub")
st.info(f"Welcome **{user['Advisor Name']}**!!, Access Level : **{level}**")

tabs_list = ["Performance Overview", "DSAT Analysis"]
if level in ["Admin", "Manager"]: tabs_list.append("Leaderboard")
tabs = st.tabs(tabs_list)

with tabs[0]:
    # a. Narrative
    avg_shift = f_kpi['Shift_Score'].mean() if not f_kpi.empty else 0
    st.markdown("#### Performance Narrative")
    st.write(f"In the selected period, the average efficiency is **{avg_shift:.2f}%**. The team shows consistent engagement. Ensure 'Shift Score' remains above 85% to optimize resources.")
    
    # b. Summary
    st.markdown("#### Performance Summary")
    g1, g2, g3 = st.columns(3)
    avg_sent = (f_kpi['Sent Rate %'].mean() * 100) if not f_kpi.empty else 0
    avg_sat = (f_kpi['Satisfied Survey %'].mean() * 100) if not f_kpi.empty else 0
    g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
    g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
    g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_shift, 85), use_container_width=True)
    
    n1, n2 = st.columns(2)
    n1.metric("Total OB Calls", int(f_kpi['OB Calls'].sum()))
    n2.metric("Total OH Calls", int(f_kpi['Q/A Calls'].sum()))

    # c. Trends
    st.markdown("#### Performance Trends")
    trend = f_kpi.groupby('Date_Parsed').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Shift_Score':'mean', 'OB Calls':'sum', 'Q/A Calls':'sum'}).reset_index()
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.line(trend, x='Date_Parsed', y=['Sent Rate %', 'Satisfied Survey %'], title="Survey Trends"), use_container_width=True)
    with c2:
        st.plotly_chart(px.line(trend, x='Date_Parsed', y='Shift_Score', title="Efficiency Trend"), use_container_width=True)

with tabs[1]:
    # a. DSAT Summary
    st.markdown("#### DSAT Summary")
    pending = len(f_dsat[f_dsat['Feedback'].isna() | (f_dsat['Feedback'] == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", len(f_dsat))
    s2.metric("Feedback Pending", pending)
    s3.metric("Controllable", len(f_dsat[f_dsat['Type'] == 'Controllable']))
    s4.metric("Uncontrollable", len(f_dsat[f_dsat['Type'] == 'Uncontrollable']))

    # b. Table
    st.markdown("#### DSAT Details")
    if not f_dsat.empty:
        col_w = [1.5, 2.5, 1.5, 3] + ([1] if level != "IC" else [])
        headers = ["Date", "Chat Link", "Type", "Feedback"] + (["Action"] if level != "IC" else [])
        cols = st.columns(col_w)
        for idx, row in f_dsat.reset_index().iterrows():
            r = st.columns(col_w)
            r[0].write(str(row['Timestamp'])[:10])
            r[1].markdown(f"[Chat Link]({row['Chat DSAT URL']})")
            r[2].write(row['Type'])
            r[3].write(row['Feedback'] if pd.notna(row['Feedback']) else "-")
            if level != "IC":
                if r[4].button("Update", key=f"upd_{idx}"): open_form_dialog(row)

if len(tabs) > 2:
    with tabs[2]:
        st.markdown("#### 🏆 Success Champions")
        st.caption("Criteria: Sent Rate ≥ 85% and Satisfied Survey % > 90%")
        ldb = f_kpi_t.groupby('Agent Name').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'}).reset_index()
        ldb['Sent Rate %'] *= 100; ldb['Satisfied Survey %'] *= 100
        champs = ldb[(ldb['Sent Rate %'] >= 85) & (ldb['Satisfied Survey %'] > 90)].sort_values('Satisfied Survey %', ascending=False)
        st.dataframe(champs[['Agent Name', 'Satisfied Survey %', 'Sent Rate %']], hide_index=True, use_container_width=True)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.subheader("Total QA"); c1.dataframe(ldb.sort_values('Q/A Calls', ascending=False)[['Agent Name', 'Q/A Calls']], hide_index=True)
        c2.subheader("Total OB"); c2.dataframe(ldb.sort_values('OB Calls', ascending=False)[['Agent Name', 'OB Calls']], hide_index=True)
        c3.subheader("Survey Sent"); c3.dataframe(ldb.sort_values('Sent Rate %', ascending=False)[['Agent Name', 'Sent Rate %']], hide_index=True)
        c4.subheader("Satisfied %"); c4.dataframe(ldb.sort_values('Satisfied Survey %', ascending=False)[['Agent Name', 'Satisfied Survey %']], hide_index=True)

st.sidebar.divider()
if st.sidebar.button("Logout"): st.session_state.auth = None; st.rerun()
