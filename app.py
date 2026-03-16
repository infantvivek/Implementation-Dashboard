

# --- 1. DATA SOURCE LINKS ---
# Ensure these links point to the specific tabs in your Google Sheet (Published as CSV)
#TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8T5NPl5jhOiEIxvI5zo0MFE3CR3jaHPPW5I-9mK0k9WD8AMUZdMatNubJL3MYUo0HQT7sSrw84P2R/pub?gid=0&single=true&output=csv"
#KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8T5NPl5jhOiEIxvI5zo0MFE3CR3jaHPPW5I-9mK0k9WD8AMUZdMatNubJL3MYUo0HQT7sSrw84P2R/pub?gid=1918948844&single=true&output=csv"
#DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8T5NPl5jhOiEIxvI5zo0MFE3CR3jaHPPW5I-9mK0k9WD8AMUZdMatNubJL3MYUo0HQT7sSrw84P2R/pub?gid=367459010&single=true&output=csv" 
import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURATION & ACCESS ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8T5NPl5jhOiEIxvI5zo0MFE3CR3jaHPPW5I-9mK0k9WD8AMUZdMatNubJL3MYUo0HQT7sSrw84P2R/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8T5NPl5jhOiEIxvI5zo0MFE3CR3jaHPPW5I-9mK0k9WD8AMUZdMatNubJL3MYUo0HQT7sSrw84P2R/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8T5NPl5jhOiEIxvI5zo0MFE3CR3jaHPPW5I-9mK0k9WD8AMUZdMatNubJL3MYUo0HQT7sSrw84P2R/pub?gid=367459010&single=true&output=csv"

# SINGLE LIST PARAMETER FOR EASY USER MANAGEMENT
PRIVILEGED_EMAILS = [
    "vivek.j@gohighlevel.com", 
    "sumit.ludhwani@gohighlevel.com", 
    "ayush.bhadauria@gohighlevel.com",
    "shelby@gohighlevel.com"
]

st.set_page_config(page_title="The Go Getters | Performance Portal", layout="wide")

# --- 2. HELPER FUNCTIONS ---
def parse_time_to_minutes(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str): return 0
    try:
        hours, minutes = 0, 0
        parts = time_str.split()
        for part in parts:
            if 'h' in part: hours = int(part.replace('h', ''))
            elif 'm' in part: minutes = int(part.replace('m', ''))
        return (hours * 60) + minutes
    except: return 0

def format_minutes_to_hours(total_minutes):
    if pd.isna(total_minutes) or total_minutes <= 0: return "0h 0m"
    return f"{int(total_minutes // 60)}h {int(total_minutes % 60)}m"

# --- 3. DATA LOADING ---
@st.cache_data(ttl=30)
def load_data(url, is_kpi=False):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        if 'Email' in df.columns:
            df['Email'] = df['Email'].astype(str).str.strip().str.lower()
        if is_kpi:
            df['IA_Mins'] = df['IA_Hours'].apply(parse_time_to_minutes)
            df['Call_Mins'] = df['Advisor Call Time'].apply(parse_time_to_minutes)
            df['Shift_Score'] = (df['Call_Mins'] / df['IA_Mins'] * 100).fillna(0)
            numeric_cols = ['Sent Rate %', 'Satisfied Survey %', 'Call Abandons', 'MOB', 'OB Calls', 'Q/A Calls', 'Total Survey']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', '').str.strip(), errors='coerce').fillna(0)
        return df
    except: return None

# --- 4. AUTHENTICATION ---
if 'authenticated' not in st.session_state: st.session_state['authenticated'] = False
if not st.session_state['authenticated']:
    st.title("The Go Getters Login")
    with st.form("Login"):
        e_in, p_in = st.text_input("Email").lower(), st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            team_db = load_data(TEAM_URL)
            match = team_db[(team_db['Email'] == e_in) & (team_db['Password'].astype(str) == p_in)]
            if not match.empty:
                st.session_state.update({'authenticated': True, 'user_email': e_in, 'user_name': match['Advisor Name'].iloc[0]})
                st.rerun()
    st.stop()

# --- 5. DATA PREP & DRILL-DOWN ---
# Using the consolidated list for permission checks
is_privileged = st.session_state['user_email'] in PRIVILEGED_EMAILS
kpi_df, dsat_df = load_data(KPI_URL, is_kpi=True), load_data(DSAT_URL)

drill_down_advisor = None
view_mode = "Team Overview"

if is_privileged:
    st.sidebar.divider()
    view_mode = st.sidebar.radio("View Mode", ["Team Overview", "Specific Advisor View"])
    if view_mode == "Specific Advisor View":
        advisor_list = sorted(kpi_df['Advisor Name'].unique())
        drill_down_advisor = st.sidebar.selectbox("Select Advisor to Review", advisor_list)

c1, c2 = st.columns([2, 8])
with c1: st.image("https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482", width='stretch')
with c2: 
    st.title("The Go Getters")
    display_name = drill_down_advisor if drill_down_advisor else st.session_state['user_name']
    st.subheader(f"Welcome {st.session_state['user_name']}!! (Reviewing: {display_name})" if drill_down_advisor else f"Welcome {st.session_state['user_name']}!!")

if st.sidebar.button("Logout"):
    st.session_state['authenticated'] = False
    st.rerun()

# Set context for filtering
if not is_privileged:
    full_kpi = kpi_df[kpi_df['Email'] == st.session_state['user_email']].copy()
    active_email = st.session_state['user_email']
elif view_mode == "Specific Advisor View":
    full_kpi = kpi_df[kpi_df['Advisor Name'] == drill_down_advisor].copy()
    active_email = full_kpi['Email'].iloc[0] if not full_kpi.empty else ""
else:
    full_kpi = kpi_df.copy()

full_kpi['Date'] = pd.to_datetime(full_kpi['Date'], format="%b'%d'%y", errors='coerce')
full_kpi = full_kpi.dropna(subset=['Date']).sort_values('Date')

full_dsat = dsat_df.copy() if dsat_df is not None else pd.DataFrame()
if not full_dsat.empty:
    full_dsat['Date'] = pd.to_datetime(full_dsat['Date'], format="%d/%m/%Y", errors='coerce')
    full_dsat = full_dsat.dropna(subset=['Date'])
    if not is_privileged or view_mode == "Specific Advisor View":
        target_email = active_email if (is_privileged and view_mode == "Specific Advisor View") else st.session_state['user_email']
        full_dsat = full_dsat[full_dsat['Email'] == target_email]

freq = st.radio("Frequency:", ["Daily", "Weekly", "Monthly"], horizontal=True)

# Selection Filters
if freq == "Daily":
    sel = st.selectbox("Select Date:", sorted(full_kpi['Date'].unique(), reverse=True), format_func=lambda x: x.strftime('%d %b %Y'))
    f_kpi = full_kpi[full_kpi['Date'] == sel]
    f_dsat = full_dsat[full_dsat['Date'].dt.normalize() == sel] if not full_dsat.empty else pd.DataFrame()
elif freq == "Weekly":
    full_kpi['W_Start'] = full_kpi['Date'] - pd.to_timedelta((full_kpi['Date'].dt.dayofweek + 1) % 7, unit='d')
    full_kpi['Week_Range'] = full_kpi['W_Start'].dt.strftime('%d %b %Y') + " - " + (full_kpi['W_Start'] + pd.to_timedelta(6, unit='d')).dt.strftime('%d %b %Y')
    sel = st.selectbox("Select Week:", full_kpi.sort_values('W_Start', ascending=False)['Week_Range'].unique())
    f_kpi = full_kpi[full_kpi['Week_Range'] == sel]
    if not full_dsat.empty:
        full_dsat['W_Start'] = full_dsat['Date'] - pd.to_timedelta((full_dsat['Date'].dt.dayofweek + 1) % 7, unit='d')
        full_dsat['Week_Range'] = full_dsat['W_Start'].dt.strftime('%d %b %Y') + " - " + (full_dsat['W_Start'] + pd.to_timedelta(6, unit='d')).dt.strftime('%d %b %Y')
        f_dsat = full_dsat[full_dsat['Week_Range'] == sel]
else:
    full_kpi['Month_Label'] = full_kpi['Date'].dt.strftime('%B %Y')
    sel = st.selectbox("Select Month:", full_kpi.sort_values('Date', ascending=False)['Month_Label'].unique())
    f_kpi = full_kpi[full_kpi['Month_Label'] == sel]
    if not full_dsat.empty:
        full_dsat['Month_Label'] = full_dsat['Date'].dt.strftime('%B %Y')
        f_dsat = full_dsat[full_dsat['Month_Label'] == sel]

# Quality averages logic
avg_kpi = f_kpi[f_kpi['Total Survey'] > 0].copy()

# --- 6. PERFORMANCE NARRATIVE ---
st.divider(); st.subheader("Performance Narrative")
avg_ia_mins = f_kpi['IA_Mins'].mean()
avg_score = f_kpi['Shift_Score'].mean()
avg_sent = avg_kpi['Sent Rate %'].mean() if not avg_kpi.empty else 0
avg_sat = avg_kpi['Satisfied Survey %'].mean() if not avg_kpi.empty else 0
total_surveys = f_kpi['Total Survey'].sum()
total_dsats = len(f_dsat)

narrative = ""
if is_privileged and view_mode == "Team Overview":
    narrative += f"### Team Summary for {sel}\n"
    narrative += f"**Quality & Satisfaction Analysis:** The team currently maintains an average Satisfaction rate of **{avg_sat:.1f}%** across **{int(total_surveys)}** total surveys. "
    narrative += "This aligns with our high-performance benchmark.\n" if avg_sat >= 80 else "This is currently below our 80% target\n"
    narrative += f"\n**Survey Engagement:** Recorded a Survey Sent Rate of **{avg_sent:.1f}%**.\n "
    if avg_sent < 80: narrative += "Attention required for data validity.\n "
    narrative += f"\n**Actionable Feedback (DSAT):** There are **{total_dsats}** records for review.\n "
    shout_out = avg_kpi[(avg_kpi['Sent Rate %'] >= 80) & (avg_kpi['Satisfied Survey %'] > 95)]['Advisor Name'].unique()
    if len(shout_out) > 0: narrative += f"\n**Success Champions:** Shout-out to **{', '.join(shout_out)}**."
else:
    target_name = drill_down_advisor if drill_down_advisor else "Your"
    narrative += f"### Performance Deep-Dive: {target_name}\n"
    narrative += f"Average Satisfaction score: **{avg_sat:.1f}%** based on **{int(total_surveys)}** responses. "
    narrative += f"\n**Sent Rate Insights:** Survey Sent Rate is **{avg_sent:.1f}%**. "
    if total_dsats > 0: narrative += f"\n**Feedback Alert:** You have **{total_dsats}** DSAT(s). Review 'DSAT Analysis' below."

st.markdown(narrative)

# --- 7. PERFORMANCE SUMMARY ---
st.header("Performance summary")
def get_delta_color(val, target, is_ia=False):
    condition = val > target if is_ia else val >= target
    return "normal" if condition else "inverse"

m = st.columns(5)
m[0].metric("Avg Shift Score", f"{avg_score:.1f}%", delta="Goal: >80%", delta_color=get_delta_color(avg_score, 80))
m[1].metric("Avg IA Hours", format_minutes_to_hours(avg_ia_mins), delta="Goal: >6h", delta_color=get_delta_color(avg_ia_mins, 360, True))
m[2].metric("Avg Sent Rate %", f"{avg_sent:.1f}%", delta="Goal: >=80%", delta_color=get_delta_color(avg_sent, 80))
m[3].metric("Avg Satisfied Survey", f"{avg_sat:.1f}%", delta="Goal: >=80%", delta_color=get_delta_color(avg_sat, 80))
m[4].metric("Total Survey", int(total_surveys))

v = st.columns(4)
v[0].metric("Total OB Calls", int(f_kpi['OB Calls'].sum()))
v[1].metric("Total Q/A Calls", int(f_kpi['Q/A Calls'].sum()))
v[2].metric("Total MOB", int(f_kpi['MOB'].sum()))
v[3].metric("Total Call Abandons", int(f_kpi['Call Abandons'].sum()))

# --- 8. PRIVILEGED LEADERBOARDS ---
if is_privileged and view_mode == "Team Overview":
    st.divider(); st.header("🏆 Leaderboards")
    ldb = avg_kpi.groupby('Advisor Name').agg({'Sent Rate %':'mean','Satisfied Survey %':'mean','Email':'first'}).reset_index()
    ldb_vol = f_kpi.groupby('Advisor Name').agg({'Q/A Calls':'sum','OB Calls':'sum','Email':'first'}).reset_index()
    if not f_dsat.empty:
        dsat_counts = f_dsat.groupby('Email').size().reset_index(name='Total DSAT')
        ldb_vol = ldb_vol.merge(dsat_counts, on='Email', how='left').fillna(0)
    if 'Total DSAT' not in ldb_vol.columns: ldb_vol['Total DSAT'] = 0
    
    col_l1, col_l2, col_l3 = st.columns(3)
    with col_l1:
        st.subheader("🏆 Success Champions")
        # Updated Criteria in Caption
        st.caption("Criteria: Survey Sent Rate ≥ 85% and Satisfied Survey > 90% (Excludes 0-survey days)")
        
        # ELIGIBILITY FILTER: Sent >= 85%, Satisfied > 90%
        sc = ldb[(ldb['Sent Rate %'] >= 85) & (ldb['Satisfied Survey %'] > 90)].copy()
        
        # MULTI-LEVEL SORT: Priority 1: Satisfied Survey (DESC), Priority 2: Sent Rate (DESC)
        sc_sorted = sc.sort_values(by=['Satisfied Survey %', 'Sent Rate %'], ascending=[False, False])
        
        st.dataframe(sc_sorted[['Advisor Name', 'Satisfied Survey %', 'Sent Rate %']], hide_index=True)
        
        st.subheader("Avg Satisfied Survey")
        st.dataframe(ldb.sort_values('Satisfied Survey %', ascending=False)[['Advisor Name', 'Satisfied Survey %']].round(2), hide_index=True)
    with col_l2:
        st.subheader("Total DSAT Received")
        st.dataframe(ldb_vol.sort_values('Total DSAT', ascending=False)[['Advisor Name', 'Total DSAT']], hide_index=True)
        st.subheader("Total QA Calls")
        st.dataframe(ldb_vol.sort_values('Q/A Calls', ascending=False)[['Advisor Name', 'Q/A Calls']], hide_index=True)
    with col_l3:
        st.subheader("Avg Survey Sent %")
        st.dataframe(ldb.sort_values('Sent Rate %', ascending=False)[['Advisor Name', 'Sent Rate %']].round(2), hide_index=True)
        st.subheader("Total OB Calls")
        st.dataframe(ldb_vol.sort_values('OB Calls', ascending=False)[['Advisor Name', 'OB Calls']], hide_index=True)
# --- 9. TRENDS ---
st.divider(); st.header("Performance Trends")
chart_df = f_kpi if (not is_privileged or view_mode == "Specific Advisor View") else f_kpi.groupby('Date').mean(numeric_only=True).reset_index()
t1, t2 = st.columns(2)
with t1:
    st.plotly_chart(px.line(chart_df, x='Date', y='Shift_Score', title="Shift Score Trend", markers=True), width='stretch')
    st.plotly_chart(px.line(avg_kpi.groupby('Date').mean(numeric_only=True).reset_index() if (is_privileged and view_mode == "Team Overview") else avg_kpi, 
                            x='Date', y='Satisfied Survey %', title="Satisfied Survey Trend", markers=True), width='stretch')
with t2:
    st.plotly_chart(px.line(chart_df, x='Date', y='IA_Mins', title="IA Minutes Trend", markers=True), width='stretch')
    st.plotly_chart(px.line(avg_kpi.groupby('Date').mean(numeric_only=True).reset_index() if (is_privileged and view_mode == "Team Overview") else avg_kpi, 
                            x='Date', y='Sent Rate %', title="Survey Sent Trend", markers=True), width='stretch')
# --- 10. DSAT ANALYSIS SECTION ---
st.divider(); st.subheader(f"🚫 DSAT Analysis & Feedback ({len(f_dsat)})")
if not f_dsat.empty:
    # FORMAT DATE TO DD-MM-YYYY
    f_dsat['Formatted_Date'] = f_dsat['Date'].dt.strftime('%d-%m-%Y')
    display_cols = ['Formatted_Date', 'Advisor Name', 'Chat_Link', 'Feedback'] if (is_privileged and view_mode == "Team Overview") else ['Formatted_Date', 'Chat_Link', 'Feedback']
    st.dataframe(
        f_dsat[display_cols].sort_values('Formatted_Date', ascending=False), 
        column_config={"Chat_Link": st.column_config.LinkColumn("View Chat"), "Formatted_Date": "Date"}, 
        hide_index=True, 
        width='stretch'
    )
else:
    st.info("No DSAT records found for this period.")

st.divider(); st.header("Detailed Report")
# FORMATTING DATE TO DD-MM-YYYY FOR DISPLAY
kpi_display = f_kpi.copy()
kpi_display['Date'] = kpi_display['Date'].dt.strftime('%d-%m-%Y')
st.dataframe(kpi_display.sort_values('Date', ascending=False), hide_index=True)
