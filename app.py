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

# PRE-FILLED FORM ID (Replace with yours)
FORM_ID = "YOUR_FORM_ID"

st.set_page_config(layout="wide", page_title="Implementation Team Performance Hub", page_icon="🚀")

# --- 2. SaaS/GHL STYLING ENGINE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    
    /* GHL SaaS Branding */
    :root { --ghl-blue: #0052FF; }
    
    .stMetric {
        background-color: var(--secondary-background-color);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid rgba(0, 82, 255, 0.1);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    
    /* Logo Visibility in both modes */
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 170px; height: 50px; margin-left: 25px; margin-top: 25px;
        filter: brightness(0) invert(1); /* Ensures visibility in dark sidebar */
    }
    
    .stTabs [aria-selected="true"] { 
        background-color: var(--ghl-blue) !important; 
        color: white !important; 
        border-radius: 8px;
    }
    
    div.stInfo {
        background-color: rgba(0, 82, 255, 0.05);
        border-left: 5px solid var(--ghl-blue);
        color: var(--text-color);
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA PROCESSING ---
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
def load_all_data():
    # Load and clean headers (handle trailing spaces and BOM)
    def clean_df(url):
        df = pd.read_csv(url)
        df.columns = [c.strip().replace('\ufeff', '') for c in df.columns]
        return df

    team = clean_df(TEAM_URL)
    kpi = clean_df(KPI_URL)
    dsat = clean_df(DSAT_URL)

    # Standardize Emails
    team['Email'] = team['Email'].str.lower().str.strip()
    kpi['Email'] = kpi['Email'].str.lower().str.strip()
    dsat['Advisor Email'] = dsat['Advisor Email'].str.lower().str.strip()

    # KPI Feature Engineering
    kpi['Date_Parsed'] = pd.to_datetime(kpi['Date_level - AS'], format="%b'%d'%y", errors='coerce')
    kpi['IA_Mins'] = kpi['IA'].apply(parse_time)
    kpi['Call_Mins'] = kpi['Advisor Call Time '].apply(parse_time)
    # Proper Shift Score Calculation
    kpi['Shift_Score'] = np.where(kpi['IA_Mins'] > 0, (kpi['Call_Mins']/kpi['IA_Mins']*100), 0)
    
    # Correct percentages (handle if source is 0.85 instead of 85)
    for col in ['Sent Rate %', 'Satisfied Survey %']:
        kpi[col] = pd.to_numeric(kpi[col], errors='coerce').fillna(0)
        if kpi[col].max() <= 1.1: kpi[col] = kpi[col] * 100

    return team, kpi, dsat

def create_gauge(title, value, target):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(value, 2),
        title={'text': title, 'font': {'size': 16, 'color': 'gray'}},
        number={'suffix': "%", 'font': {'color': '#0052FF', 'size': 38}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "#0052FF"},
            'bgcolor': "rgba(0,0,0,0)",
            'steps': [
                {'range': [0, 70], 'color': "rgba(255, 75, 75, 0.1)"},
                {'range': [70, 85], 'color': "rgba(255, 165, 0, 0.1)"},
                {'range': [85, 100], 'color': "rgba(0, 200, 83, 0.1)"}
            ],
            'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': target}
        }
    ))
    fig.update_layout(height=240, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

# --- 4. AUTH & SESSION ---
team_db, kpi_raw, dsat_raw = load_all_data()

if 'auth' not in st.session_state: st.session_state.auth = None

if not st.session_state.auth:
    st.title("Implementation Team Performance Hub")
    with st.form("login_form"):
        u_email = st.text_input("Work Email").lower().strip()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['Email'] == u_email) & (team_db['Password'].astype(str) == str(u_pass))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. NAVIGATION & FILTERING ---
user = st.session_state.auth
st.sidebar.title("Configuration")
freq = st.sidebar.selectbox("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"])

# Recursive Access Control Logic
access = user['Access level']
emails_scope = []

if access == "Admin":
    sr_mgr = st.sidebar.selectbox("Org View", ["Entire Organisation", "Jarvis Sokolowich", "Sumit Ludhwani"])
    if sr_mgr == "Entire Organisation":
        emails_scope = team_db['Email'].unique()
    else:
        mgrs = team_db[team_db['Manager'] == sr_mgr]['Advisor Name'].unique()
        sel_mgr = st.sidebar.selectbox("Select Manager Team", ["All Teams"] + list(mgrs))
        if sel_mgr == "All Teams":
            emails_scope = team_db[team_db['Manager'] == sr_mgr]['Email'].unique()
        else:
            advs = team_db[team_db['Manager'] == sel_mgr]['Advisor Name'].unique()
            sel_adv = st.sidebar.selectbox("Advisor Drill-down", ["Full Team"] + list(advs))
            if sel_adv == "Full Team":
                emails_scope = team_db[team_db['Manager'] == sel_mgr]['Email'].unique()
            else:
                emails_scope = [team_db[team_db['Advisor Name'] == sel_adv]['Email'].values[0]]

elif access == "Manager":
    mode = st.sidebar.selectbox("View Mode", ["Team Overview", "Specific Advisor View"])
    my_advisors = team_db[team_db['Manager'] == user['Advisor Name']]
    if mode == "Team Overview":
        emails_scope = my_advisors['Email'].unique()
    else:
        sel_adv = st.sidebar.selectbox("Select Advisor", my_advisors['Advisor Name'].unique())
        emails_scope = [my_advisors[my_advisors['Advisor Name'] == sel_adv]['Email'].values[0]]
else:
    emails_scope = [user['Email']]

# Apply Scoped Filters
f_kpi = kpi_raw[kpi_raw['Email'].isin(emails_scope)]
f_dsat = dsat_raw[dsat_raw['Advisor Email'].isin(emails_scope)]

# --- 6. UI CONTENT ---
st.title("Implementation Team Performance Hub")
st.markdown(f"**Welcome {user['Advisor Name']}!** | Access Level: `{access}`")

tabs = st.tabs(["Performance Overview", "DSAT Analysis"] + (["Leaderboard"] if access != "IC" else []))

with tabs[0]:
    # a. Narrative
    avg_score = f_kpi['Shift_Score'].mean() if not f_kpi.empty else 0
    st.info(f"**Performance Narrative:** In the selected timeframe, the group maintained an average Shift Score of **{avg_score:.2f}%**. High Satisfied Survey rates indicate strong customer sentiment despite varying call volumes.")
    
    # b. Summary
    st.markdown("### Performance Summary")
    c1, c2, c3 = st.columns(3)
    avg_sent = f_kpi[f_kpi['Total Survey'] > 0]['Sent Rate %'].mean() if not f_kpi.empty else 0
    avg_sat = f_kpi[f_kpi['Total Survey'] > 0]['Satisfied Survey %'].mean() if not f_kpi.empty else 0
    
    c1.plotly_chart(create_gauge("Avg Survey Sent", avg_sent, 85), use_container_width=True)
    c2.plotly_chart(create_gauge("Avg Satisfied Survey", avg_sat, 90), use_container_width=True)
    c3.plotly_chart(create_gauge("Avg Shift Score", avg_score, 85), use_container_width=True)
    
    m1, m2 = st.columns(2)
    m1.metric("Total OB Calls", f"{int(f_kpi['OB Calls'].sum()):,}")
    m2.metric("Total OH Calls (QA)", f"{int(f_kpi['Q/A Calls'].sum()):,}")

    # c. Trends
    st.markdown("### Performance Trends")
    trend = f_kpi.groupby('Date_Parsed').agg({
        'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Shift_Score':'mean', 
        'OB Calls':'sum', 'Q/A Calls':'sum'
    }).reset_index().sort_values('Date_Parsed')
    
    t_tab1, t_tab2 = st.columns(2)
    with t_tab1:
        st.plotly_chart(px.line(trend, x='Date_Parsed', y=['Sent Rate %', 'Satisfied Survey %'], 
                                title="Survey Rate Trends", color_discrete_map={"Sent Rate %":"#0052FF", "Satisfied Survey %":"#22C55E"}), use_container_width=True)
    with t_tab2:
        st.plotly_chart(px.line(trend, x='Date_Parsed', y='Shift_Score', title="Efficiency Trend", color_discrete_sequence=["#F59E0B"]), use_container_width=True)

with tabs[1]:
    st.markdown("### DSAT Summary")
    pending = len(f_dsat[f_dsat['Feedback'].isna() | (f_dsat['Feedback'] == "")])
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSAT", len(f_dsat))
    s2.metric("Pending Feedback", pending)
    s3.metric("Controllable", len(f_dsat[f_dsat['Type'] == 'Controllable']))
    s4.metric("Uncontrollable", len(f_dsat[f_dsat['Type'] == 'Uncontrollable']))

    st.markdown("### Audit Log")
    if not f_dsat.empty:
        # Proper table merging to get Advisor Name in DSAT view
        f_dsat_ext = f_dsat.merge(team_db[['Email', 'Advisor Name']], left_on='Advisor Email', right_on='Email', how='left')
        
        col_w = [1.5, 2, 1, 1, 1.2, 3] + ([1] if access != "IC" else [])
        headers = ["Date", "Advisor", "Manager", "Chat", "Type", "Feedback"] + (["Action"] if access != "IC" else [])
        
        grid = st.columns(col_w)
        for i, h in enumerate(headers): grid[i].write(f"**{h}**")
        
        for idx, row in f_dsat_ext.iterrows():
            r = st.columns(col_w)
            r[0].write(str(row['Timestamp'])[:10])
            r[1].write(row['Advisor Name'])
            r[2].write(row['Manager'])
            r[3].markdown(f"[🔗 Link]({row['Chat DSAT URL']})")
            r[4].write(row['Type'] if pd.notna(row['Type']) else "-")
            r[5].write(row['Feedback'] if pd.notna(row['Feedback']) else "-")
            if access != "IC":
                if r[6].button("Update", key=f"ds_{idx}"):
                    st.toast("Opening Form...") # Placeholder for Iframe Dialog logic

if access != "IC":
    with tabs[2]:
        st.markdown("### 🏆 Leadership Rankings")
        ldb = f_kpi.groupby('Agent Name').agg({
            'Sent Rate %':'mean', 'Satisfied Survey %':'mean', 'Q/A Calls':'sum', 'OB Calls':'sum'
        }).reset_index().round(2)
        
        st.write("**✨ Success Champions**")
        st.caption("Criteria: Avg Sent Rate ≥ 85% and Avg Satisfied ≥ 90%")
        champs = ldb[(ldb['Sent Rate %'] >= 85) & (ldb['Satisfied Survey %'] >= 90)].sort_values('Satisfied Survey %', ascending=False)
        st.dataframe(champs[['Agent Name', 'Satisfied Survey %', 'Sent Rate %']], hide_index=True, use_container_width=True)
        
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            st.write("**Total QA Volume**")
            st.dataframe(ldb.sort_values('Q/A Calls', ascending=False)[['Agent Name', 'Q/A Calls']], hide_index=True, use_container_width=True)
        with col_l2:
            st.write("**Total OB Outreach**")
            st.dataframe(ldb.sort_values('OB Calls', ascending=False)[['Agent Name', 'OB Calls']], hide_index=True, use_container_width=True)

st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()
