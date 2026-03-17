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

# --- 2. GHL DYNAMIC THEME ---
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
def load_and_standardize(url):
    try:
        df = pd.read_csv(url)
        # Standardize headers: Strip spaces, remove BOM, lowercase for internal mapping
        df.columns = [str(c).strip().replace('\ufeff', '').replace('"', '') for c in df.columns]
        return df
    except: return pd.DataFrame()

def create_ghl_gauge(title, value, target, is_percent=True):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number = {'suffix': "%" if is_percent else "", 'font': {'color': '#0052FF'}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0052FF"},
                 'steps': [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}],
                 'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target}}
    ))
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

# --- 4. DATA INITIALIZATION ---
team_db = load_and_standardize(TEAM_URL)
kpi_db = load_and_standardize(KPI_URL)
dsat_db = load_and_standardize(DSAT_URL)

# Normalize Emails to prevent case-sensitive login errors
for d in [team_db, kpi_db, dsat_db]:
    email_col = next((c for c in d.columns if 'email' in c.lower()), None)
    if email_col: d[email_col] = d[email_col].str.strip().str.lower()

# Process KPI data with fuzzy column matching
if not kpi_db.empty:
    # Fuzzy match headers to prevent KeyErrors
    ia_col = next((c for c in kpi_db.columns if c.strip() == 'IA'), 'IA')
    call_col = next((c for c in kpi_db.columns if 'Call Time' in c and 'Advisor' in c), 'Advisor Call Time ')
    date_col = next((c for c in kpi_db.columns if 'Date' in c), 'Date_level - AS')

    kpi_db['Date_Parsed'] = pd.to_datetime(kpi_db[date_col], format="%b'%d'%y", errors='coerce')
    kpi_db['IA_Mins'] = kpi_db[ia_col].apply(parse_time) if ia_col in kpi_db.columns else 0
    kpi_db['Call_Mins'] = kpi_db[call_col].apply(parse_time) if call_col in kpi_db.columns else 0
    kpi_db['Shift_Score'] = np.where(kpi_db['IA_Mins'] > 0, (kpi_db['Call_Mins']/kpi_db['IA_Mins']*100), 0)

# --- 5. AUTHENTICATION ---
if 'auth' not in st.session_state: st.session_state.auth = None
if not st.session_state.auth:
    col_log1, col_log2 = st.columns([1, 4])
    with col_log1: st.image(LOGO_URL, width=150)
    with col_log2: st.title("Performance Hub Login")
    with st.form("login"):
        e_in = st.text_input("Work Email").lower().strip()
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            email_col = next((c for c in team_db.columns if 'email' in c.lower()), 'Email')
            pass_col = next((c for c in team_db.columns if 'password' in c.lower()), 'Password')
            match = team_db[(team_db[email_col] == e_in) & (team_db[pass_col].astype(str) == str(p_in))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 6. HIERARCHY & DATE FILTERS ---
user = st.session_state.auth
st.sidebar.title("Navigation")
freq = st.sidebar.radio("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

# Date Selection Logic
if freq == "Daily":
    sel = st.sidebar.selectbox("Date", sorted(kpi_db['Date_Parsed'].dropna().unique(), reverse=True), format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_t = kpi_db[kpi_db['Date_Parsed'] == sel]
elif freq == "Weekly":
    kpi_db['Week'] = kpi_db['Date_Parsed'].dt.to_period('W').apply(lambda r: r.start_time)
    sel = st.sidebar.selectbox("Week Starting", sorted(kpi_db['Week'].dropna().unique(), reverse=True), format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_t = kpi_db[kpi_db['Week'] == sel]
else: # Monthly/Yearly
    kpi_db['Month'] = kpi_db['Date_Parsed'].dt.strftime('%B %Y')
    sel = st.sidebar.selectbox("Month/Year", kpi_db.sort_values('Date_Parsed', ascending=False)['Month'].unique())
    f_kpi_t = kpi_db[kpi_db['Month'] == sel]

# Hierarchy Filtering
acc_lvl = str(user.get('Access level', 'IC')).strip()
emails = []

if acc_lvl == "Admin":
    directors = team_db[team_db['Advisor Name'].isin(team_db['Manager'].unique())]['Manager'].unique()
    view = st.sidebar.selectbox("View Mode", ["Entire Organisation"] + list(directors))
    if view == "Entire Organisation": emails = team_db['Email'].unique()
    else:
        mgrs = team_db[team_db['Manager'] == view]['Advisor Name'].unique()
        mgr_sel = st.sidebar.selectbox("Select Manager", ["All Teams"] + list(mgrs))
        if mgr_sel == "All Teams": emails = team_db[team_db['Manager'].isin(mgrs)]['Email'].unique()
        else:
            advs = team_db[team_db['Manager'] == mgr_sel]['Advisor Name'].unique()
            adv_sel = st.sidebar.selectbox("Select Advisor", ["Full Team"] + list(advs))
            emails = [team_db[team_db['Advisor Name'] == adv_sel]['Email'].values[0]] if adv_sel != "Full Team" else team_db[team_db['Manager'] == mgr_sel]['Email'].unique()

elif acc_lvl == "Manager":
    view = st.sidebar.selectbox("View Mode", ["Team Overview", "Specific Advisor View"])
    if view == "Team Overview": emails = team_db[team_db['Manager'] == user['Advisor Name']]['Email'].unique()
    else:
        adv_sel = st.sidebar.selectbox("Select Advisor", list(team_db[team_db['Manager'] == user['Advisor Name']]['Advisor Name'].unique()))
        emails = [team_db[team_db['Advisor Name'] == adv_sel]['Email'].values[0]]

else: emails = [user['Email']]

f_kpi = f_kpi_t[f_kpi_t['Email'].isin(emails)]
f_dsat = dsat_db[dsat_db['Advisor Email'].isin(emails)]

# --- 7. MAIN UI ---
st.title("Implementation Team Performance Hub")
st.success(f"Welcome **{user['Advisor Name']}**!!, Access Level : **{acc_lvl}**")

tabs = st.tabs(["Performance Overview", "DSAT Analysis"] + (["Leaderboard"] if acc_lvl != "IC" else []))

with tabs[0]:
    # a. Narrative
    avg_shift = f_kpi['Shift_Score'].mean() if not f_kpi.empty else 0
    st.info(f"Performance Narrative: Average Shift Score is {avg_shift:.2f}%. Monitoring call activity against IA time is essential for high efficiency.")
    
    # b. Summary
    st.markdown("### Performance Summary")
    g1, g2, g3 = st.columns(3)
    # Scale percentages if needed (assumes stored as 0.85 for 85%)
    avg_sent = f_kpi['Sent Rate %'].mean() * 100 if not f_kpi.empty else 0
    avg_sat = f_kpi['Satisfied Survey %'].mean() * 100 if not f_kpi.empty else 0
    g1.plotly_chart(create_ghl_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
    g2.plotly_chart(create_ghl_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
    g3.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_shift, 85), use_container_width=True)
    
    n1, n2 = st.columns(2)
    n1.metric("Total OB Calls", int(f_kpi['OB Calls'].sum()))
    n2.metric("Total OH Calls", int(f_kpi['Q/A Calls'].sum()))

    # c. Trends
    st.markdown("### Performance Trends")
    trend = f_kpi.groupby('Date_Parsed').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Shift_Score':'mean', 'OB Calls':'sum', 'Q/A Calls':'sum'}).reset_index()
    st.plotly_chart(px.line(trend, x='Date_Parsed', y=['Sent Rate %', 'Satisfied Survey %', 'Shift_Score'], title="KPI Trends"), use_container_width=True)

with tabs[1]:
    st.markdown("### DSAT Summary")
    pending = len(f_dsat[f_dsat['Feedback'].isna() | (f_dsat['Feedback'] == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", len(f_dsat))
    s2.metric("Feedback Pending", pending)
    s3.metric("Controllable", len(f_dsat[f_dsat['Type'] == 'Controllable']))
    s4.metric("Uncontrollable", len(f_dsat[f_dsat['Type'] == 'Uncontrollable']))

    st.markdown("### DSAT Details")
    st.dataframe(f_dsat[['Timestamp', 'Chat DSAT URL', 'Type', 'Feedback']], hide_index=True, use_container_width=True)

if acc_lvl != "IC":
    with tabs[2]:
        st.markdown("### 🏆 Leaderboards")
        ldb = f_kpi_t.groupby('Agent Name').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'}).reset_index()
        st.dataframe(ldb.sort_values('Satisfied Survey %', ascending=False), hide_index=True)

st.sidebar.divider()
if st.sidebar.button("Logout"): st.session_state.auth = None; st.rerun()
