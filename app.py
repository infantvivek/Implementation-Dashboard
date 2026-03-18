import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import urllib.parse
import re
import base64
from streamlit.components.v1 import iframe

# --- 1. CONFIGURATION & URLS ---
TEAM_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=0&single=true&output=csv"
KPI_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=1918948844&single=true&output=csv"
DSAT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSU-KDmKs9i1EIEuIuJTuKKxG4nFZoPluRqOonP2BxRbQuVJunS8WQ9uJA6ayUCdoq043uFMH6u3UcM/pub?gid=367459010&single=true&output=csv"
LOGO_URL = "https://s3.amazonaws.com/cdn.freshdesk.com/data/helpdesk/attachments/production/48175265495/original/PTXBCP40UHx-8LCKsM1zqLX-pq8nndFHSw.png?1641235482"

# --- GOOGLE FORM CONFIGURATION ---
FORM_ID = "1I3pOczioxWQQAbhz3yuqwGNADl9BbJiYnCBJpxNvE7w" # Replace with your actual Form ID
#https://docs.google.com/forms/d/e/1FAIpQLSdu2gEmHPZBCoUZ1naQlGTeJtgTgB47YfCENCfeKAHU1OA76g/viewform?usp=pp_url&entry.1726897360=test&entry.1303252108=Controllable&entry.1754509958=testbmbnm
ENTRY_KEY = "entry.1726897360"       
ENTRY_TYPE = "entry.1303252108"      
ENTRY_FEEDBACK = "entry.1754509958"  

st.set_page_config(layout="wide", page_title="HighLevel Performance Hub", page_icon="🚀")

# --- 2. SaaS/GHL THEME ENGINE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    
    :root { --ghl-blue: #0052FF; }

    /* Standard App Metrics */
    .stMetric { background-color: var(--secondary-background-color); padding: 20px; border-radius: 12px; border: 1px solid rgba(0, 82, 255, 0.1); box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05); }
    
    /* GHL Sidebar Branding - Adaptive to Light/Dark Mode */
    [data-testid="stSidebarNav"]::before {
        content: ""; display: block; background-image: url('""" + LOGO_URL + """');
        background-size: contain; background-repeat: no-repeat;
        width: 170px; height: 50px; margin: 25px 0 10px 25px; filter: brightness(0) invert(1); 
    }
    
    /* Tabs Styling */
    .stTabs [aria-selected="true"] { background-color: var(--ghl-blue) !important; color: white !important; border-radius: 8px; }
    div.stInfo { background-color: rgba(0, 82, 255, 0.05); border-left: 5px solid #0052FF; color: var(--text-color); border-radius: 10px; padding: 15px; }
    
    /* Center align main header image */
    .ghl-header-img { margin-bottom: 10px; filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.1)); }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST DATA PROCESSING ENGINE ---
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
        df.columns = [re.sub(r'[^a-zA-Z0-9]', '', str(c)).lower() for c in df.columns]
        
        rmap = {
            "advisorname": "name", "agentname": "name", "email": "email", "advisoremail": "email",
            "manager": "mgr", "managername": "mgr", "accesslevel": "level", "password": "pass",
            "ia": "ia_raw", "advisorcalltime": "call_raw", "sentrate": "sent_rate", 
            "satisfiedsurvey": "sat_rate", "obcalls": "ob", "qacalls": "qa", 
            "totalsurvey": "surveys", "timestamp": "ts_raw", "processed": "date_raw", "chatdsaturl": "link", "datelevelas": "date_raw"
        }
        df = df.rename(columns=rmap)
        if 'email' in df.columns: df['email'] = df['email'].astype(str).str.strip().str.lower()
        
        if sheet_type == "KPI":
            for col in ['sent_rate', 'sat_rate']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce')
                    if df[col].max() <= 1.1: df[col] = df[col] * 100
            
            df['date_dt'] = pd.to_datetime(df['date_raw'], format="%b'%d'%y", errors='coerce')
            df['ia_min'] = df['ia_raw'].apply(parse_duration) if 'ia_raw' in df.columns else 0
            df['call_min'] = df['call_raw'].apply(parse_duration) if 'call_raw' in df.columns else 0
            df['shift_score'] = np.where(df['ia_min'] > 0, (df['call_min']/df['ia_min']*100), np.nan)
        
        if sheet_type == "DSAT":
            df['date_dt'] = pd.to_datetime(df['date_raw'] if 'date_raw' in df.columns else df['ts_raw'], errors='coerce')
            
        return df
    except Exception as e:
        return pd.DataFrame()

def create_metric_card(title, value, target=None, is_percent=True):
    if target:
        if value >= target: color = "#22C55E" # Green
        elif value >= target - 15: color = "#F59E0B" # Yellow
        else: color = "#EF4444" # Red
    else:
        color = "#0052FF" # Default Blue

    val_str = f"{value:.2f}%" if is_percent else f"{int(value):,}"
    target_str = f"Target: {target}{'%' if is_percent else ''}" if target else "Activity Metric"
    
    html = f"""
    <div style="background-color: var(--secondary-background-color); padding: 15px; border-radius: 12px; border-left: 6px solid {color}; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-bottom: 1rem;">
        <p style="color: gray; font-size: 14px; margin-bottom: 5px; font-weight: 600;">{title}</p>
        <h2 style="color: {color}; margin-top: 0; margin-bottom: 0; font-size: 28px;">{val_str}</h2>
        <p style="color: gray; font-size: 12px; margin-top: 5px;">{target_str}</p>
    </div>
    """
    return html

@st.dialog("Update Feedback & Type", width="large")
def open_form_dialog(row):
    fb = row.get('feedback', '')
    tp = row.get('type', '')
    params = {
        ENTRY_KEY: row.get('link', ''),
        ENTRY_FEEDBACK: fb if str(fb) != "nan" and fb != "-" else "",
        ENTRY_TYPE: tp if str(tp) != "nan" and tp != "-" else ""
    }
    url = f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform?usp=pp_url&{urllib.parse.urlencode(params)}"
    st.markdown("### Update Data Repository")
    st.caption("Submit updates below to push them directly to the Google Sheet backend.")
    iframe(url, height=550, scrolling=True)
    if st.button("Close & Sync Dashboard", use_container_width=True): st.rerun()

# --- 4. AUTHENTICATION (BULLETPROOF URL SESSIONS) ---
if 'auth' not in st.session_state: st.session_state.auth = None
team_db = load_and_standardize(TEAM_URL, "TEAM")

# 1. Check URL for existing session (Bypasses all browser cookie blockers)
if not st.session_state.auth and 'session' in st.query_params:
    try:
        decoded_email = base64.b64decode(st.query_params['session']).decode('utf-8')
        match = team_db[team_db['email'] == decoded_email]
        if not match.empty:
            st.session_state.auth = match.iloc[0].to_dict()
    except Exception:
        pass

# 2. Show Login screen if no active session is found
if not st.session_state.auth:
    col_l, col_r = st.columns([1, 4])
    with col_l: st.image(LOGO_URL, width=150)
    with col_r: st.title("HighLevel Performance Hub")
    
    with st.form("login"):
        u_email = st.text_input("Work Email").lower().strip()
        u_pass = st.text_input("Password", type="password")
        
        if st.form_submit_button("Sign In"):
            match = team_db[(team_db['email'] == u_email) & (team_db['pass'].astype(str) == str(u_pass))]
            if not match.empty:
                st.session_state.auth = match.iloc[0].to_dict()
                
                # Create a secure URL Token
                token = base64.b64encode(u_email.encode('utf-8')).decode('utf-8')
                st.query_params['session'] = token
                
                st.rerun()
            else: 
                st.error("Invalid credentials.")
    st.stop()

# --- 5. FREQUENCY & DATA FILTERING ---
user = st.session_state.auth
kpi_raw = load_and_standardize(KPI_URL, "KPI")
dsat_raw = load_and_standardize(DSAT_URL, "DSAT")

st.sidebar.title("Navigation Filters")
freq = st.sidebar.radio("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], horizontal=True)

if not kpi_raw.empty:
    if freq == "Daily":
        available = sorted(kpi_raw['date_dt'].dropna().unique(), reverse=True)
        if available:
            sel = st.sidebar.selectbox("Select Date", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
            k_f = kpi_raw[kpi_raw['date_dt'] == sel]
            d_f = dsat_raw[dsat_raw['date_dt'].dt.date == sel.date()] if not dsat_raw.empty else dsat_raw.copy()
        else: k_f, d_f = kpi_raw.copy(), dsat_raw.copy()
        
    elif freq == "Weekly":
        kpi_raw['wk'] = kpi_raw['date_dt'].dt.to_period('W').apply(lambda r: r.start_time)
        available = sorted(kpi_raw['wk'].dropna().unique(), reverse=True)
        if available:
            sel = st.sidebar.selectbox("Select Week", available, format_func=lambda x: x.strftime('%d-%m-%Y'))
            k_f = kpi_raw[kpi_raw['wk'] == sel]
            d_f = dsat_raw[(dsat_raw['date_dt'] >= sel) & (dsat_raw['date_dt'] < sel + pd.Timedelta(days=7))] if not dsat_raw.empty else dsat_raw.copy()
        else: k_f, d_f = kpi_raw.copy(), dsat_raw.copy()
        
    else:
        kpi_raw['mo'] = kpi_raw['date_dt'].dt.strftime('%B %Y') if freq == "Monthly" else kpi_raw['date_dt'].dt.year
        available = kpi_raw.sort_values('date_dt', ascending=False)['mo'].dropna().unique()
        if len(available) > 0:
            sel = st.sidebar.selectbox(f"Select Period", available)
            k_f = kpi_raw[kpi_raw['mo'] == sel]
            if freq == "Monthly": d_f = dsat_raw[dsat_raw['date_dt'].dt.strftime('%B %Y') == sel] if not dsat_raw.empty else dsat_raw.copy()
            else: d_f = dsat_raw[dsat_raw['date_dt'].dt.year == sel] if not dsat_raw.empty else dsat_raw.copy()
        else: k_f, d_f = kpi_raw.copy(), dsat_raw.copy()
else:
    k_f, d_f = kpi_raw.copy(), dsat_raw.copy()

# --- 6. HIERARCHY DRILL-DOWN ---
access = str(user.get('level', 'IC')).strip()
scoped_emails = []

if access == "Admin":
    view_mode = st.sidebar.selectbox("Organization View", ["Entire Organisation", "Jarvis Sokolowich", "Sumit Ludhwani"])
    if view_mode == "Entire Organisation": 
        scoped_emails = team_db['email'].dropna().unique().tolist()
    else:
        mgrs = team_db[team_db['mgr'] == view_mode]['name'].dropna().unique().tolist()
        if not mgrs: scoped_emails = team_db['email'].dropna().unique().tolist()
        else:
            mgr_sel = st.sidebar.selectbox(f"Managers under {view_mode}", ["All Teams"] + mgrs)
            if mgr_sel == "All Teams": 
                mgr_emails = team_db[team_db['name'].isin(mgrs)]['email'].tolist()
                adv_emails = team_db[team_db['mgr'].isin(mgrs)]['email'].tolist()
                scoped_emails = list(set(mgr_emails + adv_emails))
            else:
                advs = team_db[team_db['mgr'] == mgr_sel]['name'].dropna().unique().tolist()
                adv_sel = st.sidebar.selectbox(f"Advisors under {mgr_sel}", ["Full Team"] + advs)
                if adv_sel == "Full Team":
                    mgr_email = team_db[team_db['name'] == mgr_sel]['email'].tolist()
                    adv_emails = team_db[team_db['mgr'] == mgr_sel]['email'].tolist()
                    scoped_emails = list(set(mgr_email + adv_emails))
                else:
                    found = team_db[team_db['name'] == adv_sel]['email'].tolist()
                    scoped_emails = found if found else []

elif access == "Manager":
    mode = st.sidebar.selectbox("View Mode", ["Team Overview", "Specific Advisor"])
    my_advs = team_db[team_db['mgr'] == user.get('name')]
    if my_advs.empty:
        scoped_emails = [user.get('email')]
    else:
        if mode == "Team Overview": 
            scoped_emails = my_advs['email'].tolist() + [user.get('email')]
        else:
            adv_options = my_advs['name'].dropna().unique().tolist()
            adv_sel = st.sidebar.selectbox("Select Advisor", adv_options)
            found = my_advs[my_advs['name'] == adv_sel]['email'].tolist()
            scoped_emails = found if found else [user.get('email')]
else:
    scoped_emails = [user.get('email')]

f_kpi = k_f[k_f['email'].isin(scoped_emails)]
f_dsat = d_f[d_f['email'].isin(scoped_emails)]

# --- 7. MAIN UI ---
header_col1, header_col2 = st.columns([1, 10])
with header_col1: st.image(LOGO_URL, width=80)
with header_col2: st.title("Implementation Team Performance Hub")

st.success(f"Welcome **{user.get('name', 'User')}**!! | Access Level : **{access}**")

tabs_list = ["📊 Performance Overview", "🚫 DSAT Analysis & Feedback", "📄 Detailed Report"]
if access != "IC": tabs_list.append("🏆 Leaderboards")
tabs = st.tabs(tabs_list)

with tabs[0]:
    tot_ia = f_kpi['ia_min'].sum() if not f_kpi.empty else 0
    tot_call = f_kpi['call_min'].sum() if not f_kpi.empty else 0
    avg_score = (tot_call / tot_ia * 100) if tot_ia > 0 else 0
    
    st.markdown("### Performance Narrative")
    st.info(f"In the selected timeframe, the group maintains an average Shift Score of **{avg_score:.2f}%**. Monitoring trends indicate consistent engagement during active operations.")
    
    st.markdown("### Performance Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    sent_rates = f_kpi['sent_rate'].dropna() if 'sent_rate' in f_kpi.columns else pd.Series([])
    avg_sent = sent_rates.mean() if not sent_rates.empty else 0
    
    sat_rates = f_kpi['sat_rate'].dropna() if 'sat_rate' in f_kpi.columns else pd.Series([])
    avg_sat = sat_rates.mean() if not sat_rates.empty else 0
    
    tot_surveys = int(f_kpi['surveys'].fillna(0).sum()) if not f_kpi.empty else 0
    tot_ob = int(f_kpi['ob'].fillna(0).sum()) if not f_kpi.empty else 0
    tot_qa = int(f_kpi['qa'].fillna(0).sum()) if not f_kpi.empty else 0
    
    c1.markdown(create_metric_card("Avg Survey Sent", avg_sent, 85, True), unsafe_allow_html=True)
    c2.markdown(create_metric_card("Avg Satisfied", avg_sat, 90, True), unsafe_allow_html=True)
    c3.markdown(create_metric_card("Avg Shift Score", avg_score, 85, True), unsafe_allow_html=True)
    c4.markdown(create_metric_card("Total Surveys", tot_surveys, None, False), unsafe_allow_html=True)
    c5.markdown(create_metric_card("Total OB Calls", tot_ob, None, False), unsafe_allow_html=True)
    c6.markdown(create_metric_card("Total QA Calls", tot_qa, None, False), unsafe_allow_html=True)

    st.markdown("### Performance Trends")
    if not f_kpi.empty:
        trend = f_kpi.groupby('date_dt').agg(
            sent_rate=('sent_rate', lambda x: x.dropna().mean()),
            sat_rate=('sat_rate', lambda x: x.dropna().mean()),
            ob=('ob', 'sum'),
            qa=('qa', 'sum'),
            ia_min=('ia_min', 'sum'),
            call_min=('call_min', 'sum')
        ).reset_index().sort_values('date_dt')
        
        trend['shift_score'] = np.where(trend['ia_min'] > 0, (trend['call_min'] / trend['ia_min']) * 100, 0)
        
        t1, t2 = st.columns(2)
        with t1: st.plotly_chart(px.line(trend, x='date_dt', y='sent_rate', title="Survey Sent Trend (%)", markers=True), use_container_width=True)
        with t2: st.plotly_chart(px.line(trend, x='date_dt', y='sat_rate', title="Satisfied Survey Trend (%)", markers=True), use_container_width=True)
        
        t3, t4, t5 = st.columns(3)
        with t3: st.plotly_chart(px.line(trend, x='date_dt', y='shift_score', title="Shift Score Trend (%)", markers=True), use_container_width=True)
        with t4: st.plotly_chart(px.bar(trend, x='date_dt', y='ob', title="Total OB Calls"), use_container_width=True)
        with t5: st.plotly_chart(px.bar(trend, x='date_dt', y='qa', title="Total OH Calls"), use_container_width=True)

with tabs[1]:
    st.markdown("### DSAT Summary")
    fb_col = f_dsat['feedback'].astype(str).str.strip().str.lower() if 'feedback' in f_dsat.columns else pd.Series([])
    pending = len(fb_col[fb_col.isin(["nan", "-", ""])])
    
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total DSATs", f"{len(f_dsat)}")
    s2.metric("Feedback Pending", f"{pending}")
    s3.metric("Controllable", f"{len(f_dsat[f_dsat['type'] == 'Controllable']) if 'type' in f_dsat.columns else 0}")
    s4.metric("Uncontrollable", f"{len(f_dsat[f_dsat['type'] == 'Uncontrollable']) if 'type' in f_dsat.columns else 0}")

    st.markdown("### DSAT Details & Feedback")
    if not f_dsat.empty:
        f_table = f_dsat.merge(team_db[['email', 'name', 'mgr']], on='email', how='left')
        
        headers = ["Date", "Advisor Name"]
        col_w = [1.5, 2]
        if access == "Admin": headers.append("Manager"); col_w.append(1.5)
        headers.extend(["DSAT Chat Link", "Type", "Feedback"])
        col_w.extend([2.5, 1.5, 3])
        if access != "IC": headers.append("Action"); col_w.append(1.5)
        
        header_cols = st.columns(col_w)
        for i, h in enumerate(headers): header_cols[i].write(f"**{h}**")
        st.divider()
        
        for idx, row in f_table.reset_index().iterrows():
            r = st.columns(col_w)
            date_str = str(row['date_dt'])[:10] if pd.notna(row['date_dt']) else "-"
            fb = row.get('feedback', '-')
            tp = row.get('type', '-')
            
            c_idx = 0
            r[c_idx].write(date_str); c_idx += 1
            r[c_idx].write(row.get('name', '-')); c_idx += 1
            if access == "Admin": r[c_idx].write(row.get('mgr', '-')); c_idx += 1
            r[c_idx].markdown(f"[🔗 View Chat Context]({row.get('link', '#')})"); c_idx += 1
            r[c_idx].write(tp if str(tp) != 'nan' and tp != "" else "-"); c_idx += 1
            r[c_idx].write(fb if str(fb) != 'nan' and fb != "" else "-"); c_idx += 1
            
            if access != "IC":
                if r[c_idx].button("📝 Update", key=f"upd_{idx}"):
                    open_form_dialog(row)

with tabs[2]:
    st.markdown("### 📄 Detailed KPI Report")
    st.caption(f"Comprehensive view of daily metrics for the selected time range. Data is scoped by your role and filter selections.")
    
    if not f_kpi.empty:
        rep_df = pd.DataFrame()
        rep_df['Date'] = f_kpi['date_dt'].dt.strftime('%Y-%m-%d')
        rep_df['Advisor Name'] = f_kpi['name']
        
        if access != "IC":
            rep_df['Manager'] = f_kpi['mgr']
            
        if 'shift' in f_kpi.columns: rep_df['Shift'] = f_kpi['shift']
        rep_df['IA'] = f_kpi['ia_raw']
        rep_df['Call Time'] = f_kpi['call_raw']
        rep_df['Shift Score %'] = f_kpi['shift_score'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "-")
        
        rep_df['OB Calls'] = f_kpi['ob'].fillna(0).astype(int)
        rep_df['QA Calls'] = f_kpi['qa'].fillna(0).astype(int)
        if 'mob' in f_kpi.columns: rep_df['MOB'] = f_kpi['mob'].fillna(0).astype(int)
        
        rep_df['Total Survey'] = f_kpi['surveys'].fillna(0).astype(int)
        rep_df['Survey Sent %'] = f_kpi['sent_rate'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "-")
        rep_df['Satisfied Survey %'] = f_kpi['sat_rate'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "-")
        
        if 'avgobcalltime' in f_kpi.columns: rep_df['Avg OB Call Time'] = f_kpi['avgobcalltime'].fillna("-")
        if 'avgqacalltime' in f_kpi.columns: rep_df['Avg QA Call Time'] = f_kpi['avgqacalltime'].fillna("-")
        if 'timeoff' in f_kpi.columns: rep_df['Time Off'] = f_kpi['timeoff'].fillna("-")
        if 'callabandons' in f_kpi.columns: rep_df['Call Abandons'] = f_kpi['callabandons'].fillna(0).astype(int)
        if 'ticketscreated' in f_kpi.columns: rep_df['Tickets Created'] = f_kpi['ticketscreated'].fillna(0).astype(int)
        
        st.dataframe(rep_df, hide_index=True, use_container_width=True)
        
        csv_data = rep_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Detailed Report CSV",
            data=csv_data,
            file_name="detailed_performance_report.csv",
            mime="text/csv",
        )
    else:
        st.info("No data available for the selected filters.")

if access != "IC":
    with tabs[3]:
        if not f_kpi.empty:
            ldb = f_kpi.groupby('name').agg(
                sent_rate=('sent_rate', lambda x: x.dropna().mean()),
                sat_rate=('sat_rate', lambda x: x.dropna().mean()),
                qa=('qa', 'sum'),
                ob=('ob', 'sum')
            ).reset_index()
            
            ldb['sent_rate'] = ldb['sent_rate'].fillna(0).round(2)
            ldb['sat_rate'] = ldb['sat_rate'].fillna(0).round(2)
            ldb['qa'] = ldb['qa'].fillna(0)
            ldb['ob'] = ldb['ob'].fillna(0)
            
            st.markdown("### 🏆 Success Champions")
            st.caption("Advisors maintaining an Avg Survey Sent ≥ 85.00% AND Avg Satisfied Survey ≥ 90.00%.")
            champs = ldb[(ldb['sent_rate'] >= 85) & (ldb['sat_rate'] >= 90)].sort_values('sat_rate', ascending=False)
            
            if not champs.empty:
                st.dataframe(champs[['name', 'sat_rate', 'sent_rate']].rename(columns={'name': 'Advisor Name', 'sat_rate': 'Satisfied %', 'sent_rate': 'Survey Sent %'}), hide_index=True, use_container_width=True)
            else:
                st.info("No Success Champions met the criteria in this period.")

            st.markdown("---")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 📈 Survey Sent %")
                st.dataframe(ldb.sort_values('sent_rate', ascending=False)[['name', 'sent_rate']].rename(columns={'name': 'Advisor Name', 'sent_rate': 'Survey Sent %'}), hide_index=True, use_container_width=True)
            with c2:
                st.markdown("#### ⭐ Satisfied Survey %")
                st.dataframe(ldb.sort_values('sat_rate', ascending=False)[['name', 'sat_rate']].rename(columns={'name': 'Advisor Name', 'sat_rate': 'Satisfied %'}), hide_index=True, use_container_width=True)
                
            st.markdown("---")
            
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("#### 📞 Top QA Guru")
                st.dataframe(ldb.sort_values('qa', ascending=False)[['name', 'qa']].rename(columns={'name': 'Advisor Name', 'qa': 'Total QA Calls'}), hide_index=True, use_container_width=True)
            with c4:
                st.markdown("#### 🚀 OB Expert")
                st.dataframe(ldb.sort_values('ob', ascending=False)[['name', 'ob']].rename(columns={'name': 'Advisor Name', 'ob': 'Total OB Calls'}), hide_index=True, use_container_width=True)

# --- 8. LOGOUT (WIPES URL SESSION) ---
st.sidebar.divider()
if st.sidebar.button("Logout"): 
    st.session_state.auth = None
    st.query_params.clear()
    st.rerun()
    
