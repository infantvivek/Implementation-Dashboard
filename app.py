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
ENTRY_KEY = "entry.1"
ENTRY_FEEDBACK = "entry.2"
ENTRY_TYPE = "entry.3"

st.set_page_config(layout="wide", page_title="HighLevel CS Performance Tracker")

# --- 2. GHL DYNAMIC THEME ---
st.markdown("""
    <style>
    .stMetric { 
        background-color: var(--secondary-background-color); 
        padding: 20px; border-radius: 12px; border-left: 5px solid #0052FF; 
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); 
    }
    [data-testid="stMetricValue"] { color: var(--text-color); font-weight: 700; }
    .stTabs [aria-selected="true"] { background-color: #0052FF !important; color: white !important; }
    div.stInfo { background-color: rgba(0, 82, 255, 0.08); border-left: 5px solid #0052FF; color: var(--text-color); border-radius: 10px; }
    
    /* SIDEBAR LOGO INVERT FOR DARK MODE */
    [data-testid="stSidebarNav"]::before {
        content: "";
        display: block;
        background-image: url('""" + LOGO_URL + """');
        background-size: contain;
        background-repeat: no-repeat;
        width: 180px;
        height: 60px;
        margin-left: 20px;
        margin-top: 20px;
        filter: invert(1) brightness(2);
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. HELPERS & DIALOG ---
def parse_time_to_minutes(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    try:
        h, m = 0, 0
        parts = str(time_str).lower().split()
        for p in parts:
            if 'h' in p: h = int(p.replace('h', ''))
            elif 'm' in p: m = int(p.replace('m', ''))
        return (h * 60) + m
    except: return 0

def create_ghl_gauge(title, value, target=None, is_percent=True, color_steps=False):
    steps = []
    if color_steps:
        steps = [{'range': [0, 70], 'color': "#ff4b4b"}, {'range': [70, 85], 'color': "#ffa500"}, {'range': [85, 100], 'color': "#00c853"}]
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 18, 'color': 'gray'}},
        number = {'suffix': "%" if is_percent else "", 'font': {'color': '#0052FF', 'size': 35}},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "gray"},
            'bar': {'color': "#0052FF"},
            'bgcolor': "white", 'borderwidth': 1, 'bordercolor': "#E2E8F0",
            'steps': steps,
            'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target} if target else None
        }
    ))
    fig.update_layout(height=220, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

@st.dialog("Update DSAT Record", width="large")
def open_form_dialog(url):
    iframe(url, height=700, scrolling=True)
    if st.button("Close & Sync Dashboard"): st.rerun()

# --- 4. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data(url, sheet_type=None):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '').str.replace('"', '')
        mappings = {
            "KPI": {"Date_level - AS": "Date", "Agent Name": "Advisor Name", "IA": "IA_Hours", "Advisor Call Time ": "Advisor Call Time", "Manager": "Manager Name"},
            "TEAM": {"Manager": "Manager Name", "Access level": "Access Level", "Advisor Email": "Email"},
            "DSAT": {"Advisor Email": "Email", "Chat DSAT URL": "DSAT chat link", "Manager": "Manager Name"}
        }
        if sheet_type in mappings: df = df.rename(columns=mappings[sheet_type])
        if 'Email' in df.columns: df['Email'] = df['Email'].astype(str).str.strip().str.lower()
        if sheet_type == "KPI":
            df['IA_Mins'] = df['IA_Hours'].apply(parse_time_to_minutes) if 'IA_Hours' in df.columns else 0
            df['Call_Mins'] = df['Advisor Call Time'].apply(parse_time_to_minutes) if 'Advisor Call Time' in df.columns else 0
            df['Shift_Score'] = np.where(df['IA_Mins'] > 0, (df['Call_Mins'] / df['IA_Mins'] * 100), 0)
            for col in ['Sent Rate %', 'Satisfied Survey %', 'Total Survey', 'Q/A Calls', 'OB Calls']:
                if col in df.columns: df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', '').str.strip(), errors='coerce').fillna(0)
        return df
    except Exception as e: return pd.DataFrame()

# --- 5. AUTH ---
if 'auth' not in st.session_state: st.session_state.auth = None
if not st.session_state.auth:
    col_l1, col_l2 = st.columns([1, 4])
    with col_l1: st.image(LOGO_URL, width=150)
    with col_l2: st.title("HIGHLEVEL PERFORMANCE HUB")
    with st.form("login"):
        e_in, p_in = st.text_input("Work Email").lower().strip(), st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            tdb = load_data(TEAM_URL, "TEAM")
            user_match = tdb[(tdb['Email'] == e_in) & (tdb['Password'].astype(str).str.strip() == str(p_in).strip())]
            if not user_match.empty: st.session_state.auth = user_match.iloc[0].to_dict(); st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 6. DATA PREP ---
user, kpi_raw, dsat_raw, team_db = st.session_state.auth, load_data(KPI_URL, "KPI"), load_data(DSAT_URL, "DSAT"), load_data(TEAM_URL, "TEAM")
level = user.get('Access Level', 'IC') 

kpi_raw['Date_Parsed'] = pd.to_datetime(kpi_raw['Date'], format="%b'%d'%y", errors='coerce')
dsat_raw['Date_Parsed'] = pd.to_datetime(dsat_raw['Timestamp'], errors='coerce')
if 'Processed' in dsat_raw.columns: dsat_raw = dsat_raw[dsat_raw['Processed'] != 'DUPLICATE']
if 'Advisor Name' not in dsat_raw.columns: dsat_raw = dsat_raw.merge(team_db[['Email', 'Advisor Name', 'Manager Name']], on='Email', how='left')

# --- 7. FILTERS ---
freq = st.sidebar.radio("View Frequency:", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

if freq == "Daily":
    available = sorted(kpi_raw['Date_Parsed'].dropna().unique(), reverse=True)
    sel = st.sidebar.selectbox("Select Date:", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_t, f_dsat_t = kpi_raw[kpi_raw['Date_Parsed'] == sel], dsat_raw[dsat_raw['Date_Parsed'].dt.normalize() == sel]
elif freq == "Weekly":
    kpi_raw['W_Start'] = kpi_raw['Date_Parsed'] - pd.to_timedelta((kpi_raw['Date_Parsed'].dt.dayofweek + 1) % 7, unit='d')
    sel = st.sidebar.selectbox("Select Week Starting:", sorted(kpi_raw['W_Start'].dropna().unique(), reverse=True), format_func=lambda x: x.strftime('%d-%m-%Y'))
    f_kpi_t, f_dsat_t = kpi_raw[kpi_raw['W_Start'] == sel], dsat_raw[(dsat_raw['Date_Parsed'] >= sel) & (dsat_raw['Date_Parsed'] < sel + pd.Timedelta(days=7))]
elif freq == "Monthly":
    kpi_raw['Month_Label'] = kpi_raw['Date_Parsed'].dt.strftime('%B %Y')
    sel = st.sidebar.selectbox("Select Month:", kpi_raw.sort_values('Date_Parsed', ascending=False)['Month_Label'].dropna().unique())
    f_kpi_t, f_dsat_t = kpi_raw[kpi_raw['Month_Label'] == sel], dsat_raw[dsat_raw['Date_Parsed'].dt.strftime('%B %Y') == sel]
else:
    kpi_raw['Year_Label'] = kpi_raw['Date_Parsed'].dt.year
    sel = st.sidebar.selectbox("Select Year:", sorted(kpi_raw['Year_Label'].dropna().unique(), reverse=True))
    f_kpi_t, f_dsat_t = kpi_raw[kpi_raw['Year_Label'] == sel], dsat_raw[kpi_raw['Date_Parsed'].dt.year == sel]

# Scoping
if level == "Admin":
    sr_mgr = st.sidebar.selectbox("Sr. Manager Team", ["Entire Organization", "Jarvis Sokolowich", "Sumit Ludhwani"])
    if sr_mgr != "Entire Organization":
        m_list = team_db[team_db['Manager Name'] == sr_mgr]['Advisor Name'].unique()
        target_emails = team_db[team_db['Manager Name'].isin(m_list)]['Email'].unique()
        f_kpi, f_dsat = f_kpi_t[f_kpi_t['Email'].isin(target_emails)], f_dsat_t[f_dsat_t['Email'].isin(target_emails)]
    else: f_kpi, f_dsat = f_kpi_t, f_dsat_t
elif level == "Manager":
    target_emails = team_db[team_db['Manager Name'] == user['Advisor Name']]['Email'].unique()
    f_kpi, f_dsat = f_kpi_t[f_kpi_t['Email'].isin(target_emails)], f_dsat_t[f_dsat_t['Email'].isin(target_emails)]
else: f_kpi, f_dsat = f_kpi_t[f_kpi_t['Email'] == user['Email']], f_dsat_t[f_dsat_t['Email'] == user['Email']]

# --- 8. UI ---
st.title("PERFORMANCE HUB")
st.caption(f"Member: {user['Advisor Name']} | Access: {level} | Period: {sel}")

tabs = st.tabs(["Overview", "DSAT Audit", "Leaderboards"])

with tabs[0]:
    active_kpi = f_kpi[f_kpi['IA_Mins'] > 0]
    avg_score = active_kpi['Shift_Score'].mean() if not active_kpi.empty else 0
    avg_sent = f_kpi[f_kpi['Total Survey'] > 0]['Sent Rate %'].mean() if not f_kpi.empty else 0
    avg_sat = f_kpi[f_kpi['Total Survey'] > 0]['Satisfied Survey %'].mean() if not f_kpi.empty else 0
    total_ob, total_qa = f_kpi['OB Calls'].sum() if not f_kpi.empty else 0, f_kpi['Q/A Calls'].sum() if not f_kpi.empty else 0
    
    # Hero Gauges
    c1, c2, c3 = st.columns(3)
    c1.plotly_chart(create_ghl_gauge("Avg Shift Score", avg_score, 85, color_steps=True), use_container_width=True)
    c2.plotly_chart(create_ghl_gauge("Avg Sent Rate %", avg_sent, 85, color_steps=True), use_container_width=True)
    c3.plotly_chart(create_ghl_gauge("Avg Satisfied %", avg_sat, 90, color_steps=True), use_container_width=True)

    # Exact Value Gauges
    v1, v2 = st.columns(2)
    v1.plotly_chart(create_ghl_gauge("Total OB Calls", int(total_ob), is_percent=False), use_container_width=True)
    v2.plotly_chart(create_ghl_gauge("Total QA Calls", int(total_qa), is_percent=False), use_container_width=True)

    st.markdown("### 📈 Trend Analysis")
    trend_data = f_kpi.groupby('Date_Parsed').agg({'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'}).reset_index()
    tc1, tc2 = st.columns(2)
    with tc1:
        st.plotly_chart(px.line(trend_data, x='Date_Parsed', y='Sent Rate %', title="Survey Sent Trend", markers=True, color_discrete_sequence=['#f59e0b']), use_container_width=True)
        st.plotly_chart(px.line(trend_data, x='Date_Parsed', y='Q/A Calls', title="Total QA Calls Trend", markers=True, color_discrete_sequence=['#0F172A']), use_container_width=True)
    with tc2:
        st.plotly_chart(px.line(trend_data, x='Date_Parsed', y='Satisfied Survey %', title="Satisfied Survey Trend", markers=True, color_discrete_sequence=['#22c55e']), use_container_width=True)
        st.plotly_chart(px.line(trend_data, x='Date_Parsed', y='OB Calls', title="Total OB Calls Trend", markers=True, color_discrete_sequence=['#0052FF']), use_container_width=True)

with tabs[1]:
    st.markdown("### DSAT Audit")
    pending = len(f_dsat[f_dsat['Feedback'].isna() | (f_dsat['Feedback'].astype(str).str.strip() == "")])
    st.metric("Feedback Pending", pending, delta=f"{pending} Unactioned", delta_color="inverse")
    if not f_dsat.empty:
        col_w = [1.5, 2, 2, 1, 1.2, 3, 1]
        headers = ["Date", "Advisor", "Manager", "Link", "Type", "Feedback", "Action"]
        h_cols = st.columns(col_w)
        for i, h in enumerate(headers): h_cols[i].write(f"**{h}**")

        # FIXED: Enumerate to provide a unique index for the key
        for idx, row in f_dsat.reset_index().iterrows():
            fb = row['Feedback'] if pd.notna(row['Feedback']) and str(row['Feedback']).strip() != "" else "-"
            tp = row['Type'] if pd.notna(row['Type']) and str(row['Type']).strip() != "" else "-"
            r = st.columns(col_w)
            r[0].write(str(row['Timestamp'])[:10]); r[1].write(row['Advisor Name']); r[2].write(row.get('Manager Name', 'N/A'))
            r[3].markdown(f"[Chat]({row['DSAT chat link']})"); r[4].write(tp); r[5].write(fb)
            
            # UNIQUE KEY FIX: Added idx to the button key string
            if r[6].button("Update", key=f"btn_{idx}_{row['RecordKey']}"): 
                open_form_dialog(generate_form_url(row))

with tabs[2]:
    st.markdown("### 🏆 Team Leaderboards")
    ldb = f_kpi[f_kpi['Total Survey'] > 0].groupby('Advisor Name').agg({
        'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'
    }).reset_index().round(2)
    l1, l2, l3 = st.columns(3)
    with l1:
        st.write("**Top Success Champions**")
        sc = ldb[(ldb['Sent Rate %'] >= 85) & (ldb['Satisfied Survey %'] > 90)].sort_values('Satisfied Survey %', ascending=False)
        st.dataframe(sc[['Advisor Name', 'Satisfied Survey %', 'Sent Rate %']], hide_index=True, use_container_width=True)
    with l2:
        st.write("**Total QA Calls**"); st.dataframe(ldb.sort_values('Q/A Calls', ascending=False)[['Advisor Name', 'Q/A Calls']], hide_index=True, use_container_width=True)
        st.write("**Avg Satisfied %**"); st.dataframe(ldb.sort_values('Satisfied Survey %', ascending=False)[['Advisor Name', 'Satisfied Survey %']], hide_index=True, use_container_width=True)
    with l3:
        st.write("**Total OB Calls**"); st.dataframe(ldb.sort_values('OB Calls', ascending=False)[['Advisor Name', 'OB Calls']], hide_index=True, use_container_width=True)
        st.write("**Avg Sent %**"); st.dataframe(ldb.sort_values('Sent Rate %', ascending=False)[['Advisor Name', 'Sent Rate %']], hide_index=True, use_container_width=True)

st.sidebar.divider(); st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'auth': None}))
