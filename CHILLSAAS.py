# CHILL MASTER ENGINE - v32.103 (Generic SaaS / Agnostic WMS Version)
import os
import sys
import multiprocessing

# ------------------------------------------------------------------------------
# PYINSTALLER BOOTLOADER LOCK
# ------------------------------------------------------------------------------
def _is_running_in_streamlit():
    try:
        import inspect
        for frame in inspect.stack():
            if 'script_runner' in frame.filename or 'scriptrunner' in frame.filename:
                return True
    except Exception:
        pass
    return False

if __name__ == '__main__':
    multiprocessing.freeze_support()
    
    if getattr(sys, 'frozen', False):
        if not _is_running_in_streamlit():
            import threading
            import webbrowser
            import time
            import streamlit.web.cli as stcli
            
            def open_browser():
                time.sleep(2.5)
                webbrowser.open('http://localhost:8501')
                
            threading.Thread(target=open_browser, daemon=True).start()
            
            sys.argv = [
                "streamlit", "run", __file__, 
                "--server.port=8501", 
                "--server.headless=true", 
                "--global.developmentMode=false", 
                "--server.fileWatcherType=none",
                "--browser.gatherUsageStats=false"
            ]
            sys.exit(stcli.main())

# ------------------------------------------------------------------------------
# MAIN APPLICATION LOGIC
# ------------------------------------------------------------------------------
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta, time as dt_time
import pytz
import io
import re

# --- SYSTEM CONFIGURATION ---
st.set_page_config(
    page_title="CHILL | Critical Health Integrated Learning Library", 
    page_icon="❄️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- SESSION STATE INITIALIZATION ---
if 'setup_complete' not in st.session_state:
    st.session_state.setup_complete = False
if 'active_sites' not in st.session_state:
    st.session_state.active_sites = {} 

# --- BRANDING CSS ---
st.markdown("""
    <style>
    .stDeployButton {display:none;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    button[data-baseweb="tab"] {
        padding-top: 12px !important;
        padding-bottom: 12px !important;
    }
    button[data-baseweb="tab"] > div[data-testid="stMarkdownContainer"] > p {
        font-size: 1.25rem !important;
        font-weight: 800 !important;
    }
    
    .chill-main-title {
        font-size: 70px;
        font-weight: 900;
        color: #ffffff;
        text-align: center;
        margin-bottom: 5px;
        letter-spacing: 4px;
        text-shadow: 0px 0px 15px rgba(0, 168, 225, 0.9);
    }
    .chill-subtitle {
        font-size: 24px;
        color: #00a8e1;
        text-align: center;
        margin-top: 0px;
        margin-bottom: 30px;
        font-weight: 700;
        letter-spacing: 1px;
    }
    .site-header {
        font-size: 28px;
        font-weight: bold;
        color: #ffffff;
        border-left: 5px solid #00a8e1;
        padding-left: 15px;
        margin-top: 10px;
        margin-bottom: 20px;
        background: rgba(0, 168, 225, 0.1);
        padding: 10px;
        border-radius: 0 5px 5px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .metric-box {
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.1rem;
    }
    .metric-green { background-color: rgba(0, 255, 0, 0.1); border: 1px solid #00ff00; color: #00ff00; }
    .metric-red { background-color: rgba(255, 0, 0, 0.1); border: 1px solid #ff0000; color: #ff0000; }
    .metric-yellow { background-color: rgba(255, 255, 0, 0.1); border: 1px solid #ffff00; color: #ffff00; }
    .batch-box { border-left: 4px solid #b388ff; padding-left: 10px; background: rgba(179, 136, 255, 0.05); border-radius: 0 5px 5px 0;}
    .plan-box { background-color: #262730; padding: 15px; border-radius: 8px; border: 1px solid #444; margin-bottom: 10px; }
    .plan-header { color: #00a8e1; font-weight: bold; font-size: 1.2em; margin-bottom: 10px; text-align: center; border-bottom: 1px solid #444; padding-bottom: 5px;}
    .calc-display { background-color: #000; color: #00ff00; padding: 5px; border-radius: 4px; text-align: center; font-family: monospace; font-weight: bold; }
    .compact-input > div { margin-bottom: -15px; }
    .note-log { background-color: #262730; padding: 10px; border-radius: 5px; margin-bottom: 5px; border-left: 3px solid #ff4b4b; }
    .wip-status-badge { font-size: 0.8em; font-weight: bold; padding: 2px 6px; border-radius: 4px; }
    
    .snapshot-btn {
        background-color: #333; color: white; border: 1px solid #555;
        padding: 5px 15px; border-radius: 5px; cursor: pointer;
        font-weight: bold; margin-left: 15px;
    }
    .snapshot-btn:hover { background-color: #555; }
    
    .live-compare {
        font-size: 0.75em; color: #00a8e1; 
        margin-top: -10px; margin-bottom: 10px; text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENT STATE WRAPPERS ---
def saved_number_input(label, default_value, widget_key, site_store, **kwargs):
    if widget_key not in site_store: site_store[widget_key] = default_value
    def sync_state(): site_store[widget_key] = st.session_state[widget_key]
    return st.number_input(label, value=site_store[widget_key], key=widget_key, on_change=sync_state, **kwargs)

def saved_multiselect(label, options, default_value, widget_key, site_store, **kwargs):
    if widget_key not in site_store: site_store[widget_key] = default_value
    def sync_state(): site_store[widget_key] = st.session_state[widget_key]
    return st.multiselect(label, options, default=site_store[widget_key], key=widget_key, on_change=sync_state, **kwargs)

def saved_selectbox(label, options, widget_key, site_store, **kwargs):
    if widget_key not in site_store: site_store[widget_key] = options[0]
    def sync_state(): site_store[widget_key] = st.session_state[widget_key]
    try: idx = options.index(site_store[widget_key])
    except: idx = 0
    return st.selectbox(label, options, index=idx, key=widget_key, on_change=sync_state, **kwargs)

# --- HELPER FUNCTIONS ---
def clean_cols(df):
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('.', '')
    return df

def safe_int(val, default=0):
    try:
        if pd.isna(val) or val is None: return default
        return int(float(val))
    except: return default

def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val is None: return default
        if isinstance(val, str): val = val.replace('%', '').replace(',', '').strip()
        return float(val)
    except: return default

def parse_redline(val, default=15):
    try:
        if pd.isna(val) or val is None: return default
        if isinstance(val, str): 
            val = val.replace('%', '').replace(',', '').strip()
        v = float(val)
        if 0 < v <= 1.0: return int(v * 100)
        return int(v)
    except: return default

def calculate_shift_progress(shift_type, current_time, dna):
    start_str = str(dna.get('day_shift_start', '06:30')) if "Day" in shift_type else str(dna.get('night_shift_start', '18:00'))
    try: start_h, start_m = map(int, start_str.split(':'))
    except: start_h, start_m = (6, 30) if "Day" in shift_type else (18, 0)
    
    shift_duration = timedelta(hours=10, minutes=30)
    
    if "Day" in shift_type:
        start = current_time.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end = start + shift_duration
    else: 
        if current_time.hour < 12: 
            start = (current_time - timedelta(days=1)).replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        else: 
            start = current_time.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end = start + shift_duration
    
    total_seconds = (end - start).total_seconds()
    elapsed = (current_time - start).total_seconds()
    
    pct = max(0, min(100, (elapsed / total_seconds) * 100))
    return pct, start, end

def process_query(query, site_name, site_data):
    query = query.lower()
    response = "I couldn't find that specific data point. Try asking about 'misses', 'rates', 'wip', or 'sla'."
    if 'miss' in query or 'rca' in query or 'incident' in query:
        if f"{site_name}_miss_count" in st.session_state:
            cnt = st.session_state[f"{site_name}_miss_count"]
            response = f"Based on the latest RCA scan, there are **{cnt}** total misses recorded."
        else: response = "No RCA/Incident data has been uploaded yet."
    elif 'rate' in query or 'pick' in query or 'pack' in query:
        if f"storage_{site_name}" in st.session_state:
            store = st.session_state[f"storage_{site_name}"]
            response = f"Current Flow State:\n- **Std Pack Output:** {store.get('final_tph', 0):,} TPH\n- **Batch Output:** {store.get('batch_tph', 0):,} TPH\n- **Net Delta:** {store.get('final_delta', 0):,} units"
    elif 'sorter' in query or 'recirc' in query:
        response = "Check the Sorter Tab. If OOS duration > 30 mins, create an engineering ticket."
    elif 'shift' in query or 'time' in query:
        response = f"Current Shift: **{site_data['shift']}**\nTimezone: {site_data['timezone']}"
    return response

# ==============================================================================
# SITE DASHBOARD
# ==============================================================================
def render_site_dashboard(site_name, site_data):
    if f"storage_{site_name}" not in st.session_state:
        st.session_state[f"storage_{site_name}"] = {
            'chat_history': [{"role": "assistant", "content": f"Hello! I am connected to the {site_name} data stream."}],
            'final_tph': 0, 'batch_tph': 0, 'final_delta': 0, 'active_hcs': {}, 'total_putwalls': 12,
            'curr_scanned_cnt': 0, 'curr_exc_cnt': 0, 'curr_scanned_paths': {}, 'curr_exc_paths': {},
            'prev_scanned_cnt': 0, 'prev_exc_cnt': 0, 'prev_scanned_paths': {}, 'prev_exc_paths': {},
            'last_wave_id': None, 'wip_health': {},
            'shift_notes': [] 
        }
    
    store = st.session_state[f"storage_{site_name}"]
    dna = site_data['dna']
    tz_name = site_data['timezone']
    shift_name = site_data['shift']
    season_status = site_data.get('season', 'STANDARD')

    sla_pull_mins = safe_int(dna.get('sla_pull_minutes'), 30)
    sla_visibility_mins = safe_int(dna.get('sla_visibility_minutes'), 150)
    
    putwall_min_global = safe_int(dna.get('putwall_buffer_min'), 20)
    putwall_max_global = safe_int(dna.get('putwall_buffer_max'), 40)
    path_min_global = safe_int(dna.get('path_buffer_min'), 15)
    path_max_global = safe_int(dna.get('path_buffer_max'), 25)
    
    if "Day" in shift_name:
        rca_limit = safe_int(dna.get('day_rca_threshold'), 2000)
    else:
        rca_limit = safe_int(dna.get('night_rca_threshold'), 2000)

    city = str(dna.get('site_city', 'Unknown')).replace('_', ' ').title()
    state = str(dna.get('site_state', 'NA')).upper()
    
    season_badge = "🔥 PEAK" if season_status == "PEAK" else "🟩 STANDARD"
    
    st.markdown(f"""
    <div class='site-header'>
        <span>📍 {site_name} OPERATIONS CONSOLE  |  {city}, {state}</span> 
        <div style='display:flex; align-items:center;'>
            <span>{season_badge}</span>
            <button class='snapshot-btn' onclick='window.print()'>📷 SNAPSHOT</button>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    components.html("""<script>
    const buttons = window.parent.document.getElementsByClassName('snapshot-btn');
    for (let i = 0; i < buttons.length; i++) {
        buttons[i].onclick = function() { window.parent.print(); };
    }
    </script>""", height=0, width=0)

    try: tz = pytz.timezone(tz_name)
    except: tz = pytz.timezone('UTC')
    now = datetime.now(tz)
    
    dst_offset = safe_int(dna.get('dst_time_shift_hour'), 0)
    if dst_offset != 0:
        now = now + timedelta(hours=dst_offset)

    pct, start, end = calculate_shift_progress(shift_name, now, dna)
    if pct < 35: bar_color = "#ff4b4b" 
    elif pct < 75: bar_color = "#ffa500" 
    else: bar_color = "#00c853" 
    
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(f"""
        <div style="background-color: #333; border-radius: 10px; padding: 3px; margin-top: 10px;">
            <div style="
                width: {pct}%;
                background-color: {bar_color};
                height: 25px;
                border-radius: 8px;
                transition: width 0.5s;
                text-align: right;
                padding-right: 10px;
                color: white;
                font-weight: bold;
                line-height: 25px;
            ">
            {int(pct)}%
            </div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 0.8em; color: #888; margin-top: 5px;">
            <span>Start: {start.strftime('%H:%M')}</span>
            <span>Shift Progress</span>
            <span>End: {end.strftime('%H:%M')}</span>
        </div>
        """, unsafe_allow_html=True)
    with c2: 
        st.metric("Local Time", now.strftime("%H:%M:%S"))
    
    st.divider()

    with st.expander("⚙️ Customize Workspace Tabs", expanded=False):
        all_tool_tabs = ["Planning (Sandbox)", "SLA (Tactical)", "Sorter (Health)", "WIP (Command)", "RCA (Root Cause)", "Scanned / Exceptions", "Shift Notes", "Query"]
        user_tab_order = saved_multiselect(
            "Drag and drop to rearrange. 'Logic Engine' is pinned first.", 
            all_tool_tabs, 
            default_value=all_tool_tabs, 
            widget_key=f"{site_name}_tab_order", 
            site_store=store
        )
        
    dynamic_tab_names = ["🏠 LOGIC ENGINE (MAIN)"] + user_tab_order
    tabs = st.tabs(dynamic_tab_names)
    active_hcs = {} 

    for idx, tab_name in enumerate(dynamic_tab_names):
        
        # ---------------------------------------------------------
        # TAB: PLANNING (SANDBOX)
        # ---------------------------------------------------------
        if tab_name == "Planning (Sandbox)":
            with tabs[idx]:
                num_periods = safe_int(dna.get('shift_periods'), 4)
                grand_total_planned = 0
                std_keys = [k for k in dna.keys() if (('hc' in k and 'max' in k) or ('pack' in k and 'max' in k)) and 'pick' not in k and 'wall' not in k and 'batch' not in k.lower()]
                valid_std_paths = sorted([k for k in std_keys if safe_float(dna.get(k, 0)) > 0])
                putwall_keys = sorted([k for k in dna.keys() if 'putwall' in k and safe_float(dna[k]) > 0])
                
                export_data = {'Metric': []}
                for i in range(num_periods): export_data[f'Period {i+1}'] = []
                
                rows = ['Pick HC', 'Pick RT', 'Pick TPH']
                if putwall_keys:
                    for key in putwall_keys:
                        l = key.replace('pp', '').replace('_max', '').upper()
                        rows.extend([f'{l} Modules', f'{l} Rate'])
                    rows.append('Total Sort TPH')
                    
                if valid_std_paths:
                    for key in valid_std_paths:
                        l = re.sub(r'_?(max|hc|pack)_?', '', key.lower()).replace('pp', '').strip('_').upper()
                        rows.extend([f'{l} HC', f'{l} RT', f'{l} TPH'])
                        
                rows.extend(['Cross-dock Target', 'NET DELTA', 'PERIOD TOTAL OB'])
                export_data['Metric'] = rows

                for i in range(num_periods):
                    p_num = i + 1
                    col_data = []
                    
                    pk_hc = st.session_state.get(f"{site_name}_p{p_num}_pick_hc", 0)
                    pk_rt = st.session_state.get(f"{site_name}_p{p_num}_pick_rt", 100)
                    p_pick_tph = pk_hc * pk_rt
                    col_data.extend([pk_hc, pk_rt, p_pick_tph])
                    
                    p_sort_tph = 0
                    if putwall_keys:
                        for key in putwall_keys:
                            l = key.replace('pp', '').replace('_max', '').upper()
                            iw = st.session_state.get(f"{site_name}_p{p_num}_w_{l}", 0)
                            ir = st.session_state.get(f"{site_name}_p{p_num}_r_{l}", 600)
                            col_data.extend([iw, ir])
                            p_sort_tph += (iw * ir)
                        col_data.append(p_sort_tph)

                    p_pack_tph = 0
                    if valid_std_paths:
                        for key in valid_std_paths:
                            l = re.sub(r'_?(max|hc|pack)_?', '', key.lower()).replace('pp', '').strip('_').upper()
                            phc = st.session_state.get(f"{site_name}_p{p_num}_phc_{l}", 0)
                            prt = st.session_state.get(f"{site_name}_p{p_num}_prt_{l}", 160)
                            tph = phc * prt
                            col_data.extend([phc, prt, tph])
                            p_pack_tph += tph
                    
                    crossdock = st.session_state.get(f"{site_name}_p{p_num}_crossdock", 0)
                    delta = p_pick_tph - p_pack_tph - crossdock
                    grand_total_planned += p_pack_tph

                    col_data.extend([crossdock, delta, p_pack_tph])
                    export_data[f'Period {p_num}'] = col_data

                st.subheader("Shift Planner (Sandbox)")
                m1, m2, m3 = st.columns([2, 3, 1])
                with m1: 
                    st.metric("Total Planned OB Volume", f"{grand_total_planned:,} units")
                with m2:
                    df_export = pd.DataFrame(export_data)
                    csv = df_export.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Generate Plan (CSV)", csv, f"{site_name}_Shift_Plan.csv", "text/csv", use_container_width=True)
                
                st.divider()
                
                plan_cols = st.columns(num_periods)
                for i in range(num_periods):
                    p_num = i + 1
                    with plan_cols[i]:
                        st.markdown(f"<div class='plan-box'><div class='plan-header'>PERIOD {p_num}</div>", unsafe_allow_html=True)
                        show_comp = st.toggle("📊 Compare Live", key=f"{site_name}_p{p_num}_comp")
                        
                        st.markdown("**PICK**")
                        c_pk1, c_pk2 = st.columns(2)
                        with c_pk1: 
                            st.number_input("HC", value=0, key=f"{site_name}_p{p_num}_pick_hc", label_visibility="collapsed")
                            if show_comp:
                                live_val = st.session_state.get(f"{site_name}_pick_hc", 50)
                                plan_val = st.session_state.get(f"{site_name}_p{p_num}_pick_hc", 0)
                                st.markdown(f"<div class='live-compare'>Live: {live_val} ({live_val - plan_val:+})</div>", unsafe_allow_html=True)
                                
                        with c_pk2: 
                            st.number_input("RT", value=100, key=f"{site_name}_p{p_num}_pick_rt", label_visibility="collapsed")
                            if show_comp:
                                live_val = st.session_state.get(f"{site_name}_pick_rt", 100)
                                plan_val = st.session_state.get(f"{site_name}_p{p_num}_pick_rt", 100)
                                st.markdown(f"<div class='live-compare'>Live: {live_val} ({live_val - plan_val:+})</div>", unsafe_allow_html=True)
                        
                        p_tph = st.session_state.get(f"{site_name}_p{p_num}_pick_hc", 0) * st.session_state.get(f"{site_name}_p{p_num}_pick_rt", 100)
                        
                        if show_comp:
                            live_p_tph = st.session_state.get(f"{site_name}_pick_hc", 50) * st.session_state.get(f"{site_name}_pick_rt", 100)
                            st.markdown(f"<div class='calc-display'>⛏️ {p_tph:,} TPH<br><span style='font-size:0.8em;color:#aaa;'>Live: {live_p_tph:,} (Δ {live_p_tph - p_tph:+,})</span></div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div class='calc-display'>⛏️ {p_tph:,} TPH</div>", unsafe_allow_html=True)
                            
                        st.divider()

                        if putwall_keys:
                            st.markdown("**SORTATION**")
                            p_sort_cap = 0
                            live_sort_cap = 0
                            for key in putwall_keys:
                                label = key.replace('pp', '').replace('_max', '').upper()
                                st.caption(label)
                                ic1, ic2 = st.columns(2)
                                with ic1: 
                                    st.number_input("W", value=0, key=f"{site_name}_p{p_num}_w_{label}", label_visibility="collapsed")
                                    if show_comp:
                                        live_val = st.session_state.get(f"{site_name}_w_{label}", int(safe_int(dna[key])*0.8))
                                        plan_val = st.session_state.get(f"{site_name}_p{p_num}_w_{label}", 0)
                                        st.markdown(f"<div class='live-compare'>Live: {live_val} ({live_val - plan_val:+})</div>", unsafe_allow_html=True)
                                        
                                with ic2: 
                                    st.number_input("R", value=600, key=f"{site_name}_p{p_num}_r_{label}", label_visibility="collapsed")
                                    if show_comp:
                                        live_val = st.session_state.get(f"{site_name}_r_{label}", 600)
                                        plan_val = st.session_state.get(f"{site_name}_p{p_num}_r_{label}", 600)
                                        st.markdown(f"<div class='live-compare'>Live: {live_val} ({live_val - plan_val:+})</div>", unsafe_allow_html=True)
                                
                                p_sort_cap += (st.session_state.get(f"{site_name}_p{p_num}_w_{label}", 0) * st.session_state.get(f"{site_name}_p{p_num}_r_{label}", 600))
                                if show_comp:
                                    live_sort_cap += (st.session_state.get(f"{site_name}_w_{label}", int(safe_int(dna[key])*0.8)) * st.session_state.get(f"{site_name}_r_{label}", 600))
                                    
                            if show_comp:
                                st.markdown(f"<div class='calc-display'>📥 {p_sort_cap:,} TPH<br><span style='font-size:0.8em;color:#aaa;'>Live: {live_sort_cap:,} (Δ {live_sort_cap - p_sort_cap:+,})</span></div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='calc-display'>📥 {p_sort_cap:,} TPH</div>", unsafe_allow_html=True)
                            st.divider()
                        
                        st.markdown("**PACK**")
                        p_pack_cap = 0
                        live_pack_cap = 0
                        if valid_std_paths:
                            for key in valid_std_paths:
                                label = re.sub(r'_?(max|hc|pack)_?', '', key.lower()).replace('pp', '').strip('_').upper()
                                st.caption(label)
                                pc1, pc2 = st.columns(2)
                                with pc1: 
                                    st.number_input("HC", value=0, key=f"{site_name}_p{p_num}_phc_{label}", label_visibility="collapsed")
                                    if show_comp:
                                        live_val = st.session_state.get(f"{site_name}_hc_{key}", int(safe_int(dna[key])*0.8))
                                        plan_val = st.session_state.get(f"{site_name}_p{p_num}_phc_{label}", 0)
                                        st.markdown(f"<div class='live-compare'>Live: {live_val} ({live_val - plan_val:+})</div>", unsafe_allow_html=True)
                                        
                                with pc2: 
                                    st.number_input("RT", value=160, key=f"{site_name}_p{p_num}_prt_{label}", label_visibility="collapsed")
                                    if show_comp:
                                        live_val = st.session_state.get(f"{site_name}_rt_{key}", 160)
                                        plan_val = st.session_state.get(f"{site_name}_p{p_num}_prt_{label}", 160)
                                        st.markdown(f"<div class='live-compare'>Live: {live_val} ({live_val - plan_val:+})</div>", unsafe_allow_html=True)
                                
                                p_pack_cap += (st.session_state.get(f"{site_name}_p{p_num}_phc_{label}", 0) * st.session_state.get(f"{site_name}_p{p_num}_prt_{label}", 160))
                                if show_comp:
                                    live_pack_cap += (st.session_state.get(f"{site_name}_hc_{key}", int(safe_int(dna[key])*0.8)) * st.session_state.get(f"{site_name}_rt_{key}", 160))
                        
                        if show_comp:
                            st.markdown(f"<div class='calc-display'>📦 {p_pack_cap:,} TPH<br><span style='font-size:0.8em;color:#aaa;'>Live: {live_pack_cap:,} (Δ {live_pack_cap - p_pack_cap:+,})</span></div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div class='calc-display'>📦 {p_pack_cap:,} TPH</div>", unsafe_allow_html=True)
                        st.divider()

                        st.number_input("Target Cross-dock", value=0, key=f"{site_name}_p{p_num}_crossdock")
                        crossdock_plan = st.session_state.get(f"{site_name}_p{p_num}_crossdock", 0)
                        delta = p_tph - p_pack_cap - crossdock_plan
                        
                        if show_comp:
                            live_crossdock = st.session_state.get(f"{site_name}_crossdock", 1500)
                            live_delta = live_p_tph - live_pack_cap - live_crossdock
                            diff_delta = live_delta - delta
                            
                            color = "#ff4b4b" if delta > 0 else "#ffa500" if delta < -500 else "#00c853" 
                            l_color = "#ff4b4b" if live_delta > 0 else "#ffa500" if live_delta < -500 else "#00c853" 
                            
                            st.markdown(f"""
                            <div style='text-align: center; margin-top: 5px; font-weight: bold;'>
                                NET DELTA<br>
                                <span style='color: {color}; font-size: 1.2em;'>{delta:+,}</span><br>
                                <span style='font-size:0.8em; color:#aaa;'>Live: <span style='color:{l_color}'>{live_delta:+,}</span> (Δ {diff_delta:+,})</span>
                            </div></div>
                            """, unsafe_allow_html=True)
                        else:
                            color = "#ff4b4b" if delta > 0 else "#ffa500" if delta < -500 else "#00c853" 
                            st.markdown(f"<div style='text-align: center; margin-top: 5px; font-weight: bold;'>NET DELTA<br><span style='color: {color}; font-size: 1.2em;'>{delta:+,}</span></div></div>", unsafe_allow_html=True)

        # ---------------------------------------------------------
        # TAB: LOGIC ENGINE (MAIN)
        # ---------------------------------------------------------
        elif tab_name == "🏠 LOGIC ENGINE (MAIN)":
            with tabs[idx]:
                st.markdown("### 🎛️ Live Flow Balance & Capacity")
                
                st.subheader("Respiratory Flow Balance")
                c1, c2, c3 = st.columns(3)
                with c1: pick_hc = saved_number_input("Standard Pick HC (Excludes Batch)", 50, f"{site_name}_pick_hc", store)
                with c2: pick_rt = saved_number_input("Avg Pick Rate", 100, f"{site_name}_pick_rt", store)
                total_in_pick = pick_hc * pick_rt
                with c3: st.metric("Standard Pick Input TPH", f"{total_in_pick:,}", help="Strictly Standard Flow")
                
                st.divider()
                
                st.markdown("#### Unit Sortation Capacity")
                putwall_keys = sorted([k for k in dna.keys() if 'putwall' in k and safe_float(dna[k]) > 0])
                max_sort = 0
                total_modules = 0
                
                if putwall_keys:
                    sort_cols = st.columns(len(putwall_keys) + 1)
                    for i, key in enumerate(putwall_keys):
                        label = key.replace('pp', '').replace('_max', '').upper()
                        
                        wip_status = store.get('wip_health', {}).get(label, "No Data")
                        status_icon = "⚪"
                        if "Blowout" in wip_status: status_icon = "🔴"
                        elif "Starvation" in wip_status: status_icon = "🟡"
                        elif "Healthy" in wip_status: status_icon = "🟢"
                        
                        with sort_cols[i]:
                            st.markdown(f"**{label}** {status_icon}")
                            max_w = safe_int(dna[key])
                            w = saved_number_input(f"Modules", int(max_w*0.8), f"{site_name}_w_{label}", store, min_value=0)
                            r = saved_number_input(f"Rate/Mod", 600, f"{site_name}_r_{label}", store, step=50, min_value=0)
                            max_sort += (w * r)
                            total_modules += w
                            active_hcs[f"{label}_MODULES"] = w
                    
                    with sort_cols[-1]:
                        delta_sort = max_sort - total_in_pick
                        st.metric("Total Sort Capacity", f"{max_sort:,}", help="Sum of All Sortation (Modules * Rate)")
                        if delta_sort < 0:
                            st.caption(f"**Deviation:** Pick outpaces Sort by {abs(delta_sort):,} units")
                        else:
                            st.caption(f"**Deviation:** {delta_sort:,} units of Sort buffer available")
                else:
                    st.info("No Sort paths detected in Site configuration.")
                    
                store['total_putwalls'] = total_modules if total_modules > 0 else 12

                st.divider()
                
                std_keys = [k for k in dna.keys() if (('hc' in k and 'max' in k) or ('pack' in k and 'max' in k)) and 'pick' not in k and 'wall' not in k and 'batch' not in k.lower()]
                valid_std_paths = sorted([k for k in std_keys if safe_float(dna.get(k, 0)) > 0])
                
                batch_keys = [k for k in dna.keys() if 'batch' in k.lower() and ('hc' in k or 'max' in k)]
                valid_batch_paths = sorted([k for k in batch_keys if safe_float(dna.get(k, 0)) > 0])
                
                c_std, c_batch, c_calc = st.columns([1.5, 2.0, 1.2])
                total_std_pack = 0
                
                with c_std:
                    st.markdown("#### Standard Pack")
                    if valid_std_paths:
                        for key in valid_std_paths:
                            label = re.sub(r'_?(max|hc|pack)_?', '', key.lower()).replace('pp', '').strip('_').upper()
                            
                            wip_status = store.get('wip_health', {}).get(label, "No Data")
                            status_icon = "⚪"
                            if "Blowout" in wip_status: status_icon = "🔴"
                            elif "Starvation" in wip_status: status_icon = "🟡"
                            elif "Healthy" in wip_status: status_icon = "🟢"

                            sc1, sc2, sc3 = st.columns([2, 1, 1])
                            with sc1: st.markdown(f"**{label}** {status_icon}")
                            with sc2:
                                safe_val = safe_int(dna[key])
                                hc = saved_number_input(f"HC", int(safe_val*0.8), f"{site_name}_hc_{key}", store, label_visibility="collapsed")
                            with sc3:
                                rt = saved_number_input(f"RT", 160, f"{site_name}_rt_{key}", store, label_visibility="collapsed")
                            
                            total_std_pack += (hc * rt)
                            active_hcs[f"{label}_HC"] = hc
                    else: st.caption("No standard pack paths detected.")
                                
                with c_batch:
                    st.markdown("<div class='batch-box'>", unsafe_allow_html=True)
                    st.markdown("#### Batch Pick & Sort Flow")
                    st.caption("Batch flow operates independently (Closed Loop).")
                    
                    batch_cells = sorted(list(set([re.search(r'batch\d*', k.lower()).group() for k in valid_batch_paths if re.search(r'batch\d*', k.lower())])))
                    
                    total_batch_pick_tph = 0
                    total_batch_pack_tph = 0
                    
                    if batch_cells:
                        for cell in batch_cells:
                            st.markdown(f"**{cell.upper()}**")
                            p1, p2, p3, p4 = st.columns(4)
                            
                            pick_k = next((k for k in valid_batch_paths if cell in k.lower() and 'pick' in k.lower()), None)
                            pack_k = next((k for k in valid_batch_paths if cell in k.lower() and 'pack' in k.lower()), None)
                            
                            safe_pick = safe_int(dna.get(pick_k, 0)) if pick_k else 0
                            safe_pack = safe_int(dna.get(pack_k, 0)) if pack_k else 0
                            
                            with p1: pick_hc = saved_number_input("Pick HC", int(safe_pick*0.8), f"{site_name}_{cell}_pick_hc", store, help="Batch Pickers")
                            with p2: pick_rt = saved_number_input("Pick RT", 300, f"{site_name}_{cell}_pick_rt", store)
                            with p3: pack_hc = saved_number_input("Pack HC", int(safe_pack*0.8), f"{site_name}_{cell}_pack_hc", store, help="Batch Packers")
                            with p4: pack_rt = saved_number_input("Pack RT", 150, f"{site_name}_{cell}_pack_rt", store)
                            
                            total_batch_pick_tph += (pick_hc * pick_rt)
                            total_batch_pack_tph += (pack_hc * pack_rt)
                            
                            active_hcs[f"{cell.upper()}_HC"] = pack_hc 
                            
                        st.markdown("---")
                        m1, m2 = st.columns(2)
                        batch_internal_delta = total_batch_pick_tph - total_batch_pack_tph
                        
                        with m1: 
                            st.metric("Batch Pick Input", f"{total_batch_pick_tph:,}")
                            st.metric("Batch Pack Output", f"{total_batch_pack_tph:,}")
                            
                        with m2: 
                            st.metric("Batch Net Flow", f"{batch_internal_delta:,}", delta_color="inverse", help="Batch Pick - Batch Pack")
                            if batch_internal_delta > 1000: st.error("OVERSTUFF RISK")
                            elif batch_internal_delta < -1000: st.warning("STARVATION RISK")
                            else: st.success("BALANCED FLOW")
                    else: st.caption("No Batch paths detected in configuration.")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                store['active_hcs'] = active_hcs

                with c_calc:
                    st.markdown("#### Global Outbound Math")
                    crossdock = saved_number_input("Cross-dock/Passthrough TPH", 1500, f"{site_name}_crossdock", store)
                    
                    final_delta = total_in_pick - total_std_pack - crossdock
                    
                    st.metric("Standard Pick Input", f"{total_in_pick:,}")
                    st.metric("Standard Pack Output", f"{total_std_pack:,}", help="Pure standard pack (Batch entirely excluded)")
                    st.metric("Net Flow (Delta)", f"{final_delta:,}", delta_color="inverse", help="(Std Pick Input) - (Std Pack Output + Cross-dock)")
                    
                    if final_delta > 3000: st.error("GRIDLOCK ALERT")
                    elif final_delta < -1500: st.warning("STARVATION RISK")
                    else: st.success("OPTIMIZED FLOW")
                    
                store['final_tph'] = total_std_pack
                store['batch_tph'] = total_batch_pack_tph
                store['final_delta'] = final_delta

        # ---------------------------------------------------------
        # TAB: SLA TACTICAL
        # ---------------------------------------------------------
        elif tab_name == "SLA (Tactical)":
            with tabs[idx]:
                st.subheader("SLA Tactical Commander")
                live_std = store.get('final_tph', 0)
                live_batch = store.get('batch_tph', 0)
                live_tph = live_std + live_batch
                st.caption(f"Combined Output Cap: {live_tph:,} TPH (Std: {live_std:,} + Batch: {live_batch:,})")

                wave_file = st.file_uploader("Upload Wave/Shipment List", type=["csv", "xlsx"], key=f"{site_name}_wave")
                if wave_file:
                    try:
                        if wave_file.name.endswith('.csv'): df_r = pd.read_csv(wave_file)
                        else: df_r = pd.read_excel(wave_file)
                        df_r = clean_cols(df_r)

                        time_col = next((c for c in df_r.columns if 'sla' in c or 'pull' in c or 'ship_date' in c or 'dispatch' in c), None)
                        
                        qty_col = next((c for c in df_r.columns if 'qty' in c or 'quantity' in c), None)
                        if qty_col:
                            df_r[qty_col] = pd.to_numeric(df_r[qty_col], errors='coerce').fillna(1)
                        else:
                            df_r['quantity'] = 1
                            qty_col = 'quantity'
                            
                        pool_col = next((c for c in df_r.columns if 'pool' in c or 'status' in c), None)
                        path_col = next((c for c in df_r.columns if 'path' in c or 'pp' in c), 'process_path')
                        
                        if time_col and pool_col:
                            df_r[time_col] = pd.to_datetime(df_r[time_col], errors='coerce')
                            if df_r[time_col].dt.tz is None: df_r[time_col] = df_r[time_col].dt.tz_localize(tz, ambiguous='NaT', nonexistent='shift_forward')
                            else: df_r[time_col] = df_r[time_col].dt.tz_convert(tz)
                            
                            scanned_df = df_r[df_r[pool_col].astype(str).str.contains('Scan', case=False, na=False)]
                            exc_df = df_r[df_r[pool_col].astype(str).str.contains('Exception|Problem', case=False, na=False)]
                            
                            scanned_cnt = scanned_df[qty_col].sum() if not scanned_df.empty else 0
                            exc_cnt = exc_df[qty_col].sum() if not exc_df.empty else 0
                            
                            file_id = f"{wave_file.name}_{wave_file.size}"
                            
                            if store.get('last_wave_id') != file_id:
                                store['prev_scanned_cnt'] = store.get('curr_scanned_cnt', scanned_cnt)
                                store['prev_exc_cnt'] = store.get('curr_exc_cnt', exc_cnt)
                                store['prev_scanned_paths'] = store.get('curr_scanned_paths', scanned_df.groupby(path_col)[qty_col].sum().to_dict() if not scanned_df.empty else {})
                                store['prev_exc_paths'] = store.get('curr_exc_paths', exc_df.groupby(path_col)[qty_col].sum().to_dict() if not exc_df.empty else {})
                                store['last_wave_id'] = file_id
                                
                            store['curr_scanned_cnt'] = scanned_cnt
                            store['curr_exc_cnt'] = exc_cnt
                            store['curr_scanned_paths'] = scanned_df.groupby(path_col)[qty_col].sum().to_dict() if not scanned_df.empty else {}
                            store['curr_exc_paths'] = exc_df.groupby(path_col)[qty_col].sum().to_dict() if not exc_df.empty else {}

                            future_slas = df_r[df_r[time_col] > (now - timedelta(hours=4))].copy()
                            
                            if not future_slas.empty:
                                unique_times = sorted(future_slas[time_col].unique())
                                active_slas = [t for t in unique_times if t > (now - timedelta(minutes=sla_pull_mins + 60))]
                                next_sla_time = active_slas[0] if active_slas else unique_times[-1]

                                next_sla_df = future_slas[future_slas[time_col] == next_sla_time]
                                next_sla_units = next_sla_df[qty_col].sum()

                                pull_time = next_sla_time - timedelta(minutes=sla_pull_mins)
                                mins_to_pull = (pull_time - now).total_seconds() / 60 
                                
                                open_slas = []
                                for sla in unique_times:
                                    if (sla - timedelta(minutes=sla_visibility_mins)) > now:
                                        open_slas.append(sla.strftime("%H:%M"))

                                m1, m2, m3, m4 = st.columns(4)
                                with m1: st.metric("Next SLA Time", next_sla_time.strftime("%H:%M"))
                                with m2: 
                                    label = "Time to Pull (Countdown)"
                                    val = f"{int(mins_to_pull)} mins"
                                    if mins_to_pull < 0: st.metric(label, f"BREACHED {abs(int(mins_to_pull))}m", delta="-", delta_color="inverse")
                                    elif mins_to_pull < 30: st.metric(label, val, delta="CRITICAL", delta_color="inverse")
                                    else: st.metric(label, val)
                                with m3: st.metric("Units Remaining", f"{int(next_sla_units):,}")
                                with m4:
                                    st.metric("Open Charge Windows", f"{len(open_slas)} Active", help=f"Future SLAs currently taking charge (Visibility Limit: {sla_visibility_mins}m)")
                                    if open_slas:
                                        st.caption(", ".join(open_slas))
                                    else:
                                        st.caption("All future windows closed")

                                total_backlog_units = future_slas[qty_col].sum()
                                hrs_to_eos = max((end - now).total_seconds() / 3600.0, 0.1) 
                                
                                req_tph_total = total_backlog_units / hrs_to_eos
                                if req_tph_total > 0:
                                    pace_pct = (live_tph / req_tph_total) * 100
                                else:
                                    pace_pct = 100 

                                st.markdown("#### 🏁 Shift Backlog Pace Tracker")
                                st.caption(f"Required Output to clear Total Backlog ({int(total_backlog_units):,} units) by End of Shift: **{int(req_tph_total):,} TPH**")
                                
                                p_col1, p_col2 = st.columns([3, 1])
                                with p_col1: st.progress(min(pace_pct/100, 1.0))
                                with p_col2:
                                    if pace_pct >= 100: st.markdown(f"<div class='metric-box metric-green'>AHEAD ({int(pace_pct)}%)</div>", unsafe_allow_html=True)
                                    elif pace_pct >= 90: st.markdown(f"<div class='metric-box metric-yellow'>ON PACE ({int(pace_pct)}%)</div>", unsafe_allow_html=True)
                                    else: st.markdown(f"<div class='metric-box metric-red'>BEHIND ({int(pace_pct)}%)</div>", unsafe_allow_html=True)

                                st.markdown("---")
                                st.markdown("### 📦 Shift Health")
                                
                                s1, s2, s3 = st.columns(3)
                                with s1: st.metric("✅ Total Scanned/Packed", f"{int(scanned_cnt):,}")
                                with s2: st.metric("⚠️ Exception Inventory", f"{int(exc_cnt):,}")
                                with s3: st.metric("Total Backlog", f"{int(total_backlog_units):,}")
                                
                                st.dataframe(next_sla_df.groupby([path_col])[qty_col].sum().reset_index(name='Units'), use_container_width=True)
                            else: st.success("All SLAs Cleared!")
                    except Exception as e: st.error(f"Analysis Failed: {e}")

        # ---------------------------------------------------------
        # TAB: SORTER HEALTH
        # ---------------------------------------------------------
        elif tab_name == "Sorter (Health)":
            with tabs[idx]:
                st.subheader("Sorter Health & Recirculation Tracker")
                st.info("Upload your raw Telemetry (Grafana/Datadog) or Standard Sorter CSV.")
                
                s_type = saved_selectbox("Select Sorter System", ["Shipping Sorter", "FLAT Sorter", "Tote Router", "AS/RS Mezz"], f"{site_name}_sort_type", store)
                
                if "Shipping" in s_type: threshold_disp = parse_redline(dna.get('shipping_sorter_redline', 15), 15)
                elif "FLAT" in s_type: threshold_disp = parse_redline(dna.get('flat_sorter_redline', 5), 5)
                elif "AS/RS" in s_type: threshold_disp = parse_redline(dna.get('asrs_mezz_redline', 5), 5)
                else: threshold_disp = parse_redline(dna.get('tote_router_redline', 5), 5)
                    
                st.info(f"Analysis Threshold for {s_type}: **{threshold_disp}%** Recirculation")
                sort_file = st.file_uploader("Upload Sorter Data (.csv)", type=["csv"], key=f"{site_name}_sort_up")
                
                if sort_file:
                    try:
                        df_raw = pd.read_csv(sort_file, header=None)
                        
                        if df_raw.iloc[0, 0] == 'Id' and df_raw.iloc[1, 0] == 'Label':
                            label_row = df_raw.iloc[1].tolist()
                            clean_labels = ['Time']
                            
                            for lbl in label_row[1:]:
                                lbl_str = str(lbl).lower()
                                clean_lbl = re.sub(r'\[.*?\]', '', lbl_str).replace('label=', '').strip()
                                
                                if 'shippingsorter1' in lbl_str: name = "Shipping Sorter 1"
                                elif 'shippingsorter2' in lbl_str: name = "Shipping Sorter 2"
                                elif 'shippingrouter' in lbl_str: name = "Shipping Router"
                                elif 'shippingsorter' in lbl_str: name = "Shipping Sorter"
                                elif 'tote router' in lbl_str or 'mrs' in lbl_str: name = "Main Tote Router"
                                elif 'flat' in lbl_str: name = "FLAT Sorter"
                                elif 'mezz' in lbl_str or 'as/rs' in lbl_str: name = "AS/RS Mezz"
                                else: name = clean_lbl.title()
                                
                                orig_name = name
                                count = 1
                                while name in clean_labels:
                                    name = f"{orig_name} {count}"
                                    count += 1
                                clean_labels.append(name)
                                
                            data_start_idx = df_raw[df_raw[0] == 'Max'].index[0] + 1 if 'Max' in df_raw[0].values else 3
                            
                            df_data = df_raw.iloc[data_start_idx:].copy()
                            df_data.columns = clean_labels
                        else:
                            sort_file.seek(0)
                            df_data = pd.read_csv(sort_file, header=0)
                            df_data = clean_cols(df_data)
                            df_data.rename(columns={df_data.columns[0]: 'Time'}, inplace=True)
                        
                        df_data = df_data.dropna(axis=1, how='all')
                        
                        if 'Time' in df_data.columns:
                            df_data['Time'] = df_data['Time'].astype(str).str.replace(r' [A-Z]{3,4}$', '', regex=True)
                            df_data['Time'] = pd.to_datetime(df_data['Time'], errors='coerce')
                            df_data = df_data.dropna(subset=['Time'])
                            
                            active_sorters = []
                            for col in df_data.columns:
                                if col != 'Time':
                                    df_data[col] = pd.to_numeric(df_data[col].astype(str).str.replace('%', ''), errors='coerce')
                                    if df_data[col].notna().sum() > 0:
                                        active_sorters.append(col)
                                        
                            if not active_sorters:
                                st.error("No valid numeric recirculation data found in the upload.")
                            else:
                                interval_mins = 5
                                if len(df_data) > 1:
                                    interval_mins = (df_data['Time'].iloc[1] - df_data['Time'].iloc[0]).total_seconds() / 60.0
                                    if interval_mins == 0: interval_mins = 5
                                    
                                st.success(f"Detected {len(active_sorters)} active sorter feeds. Logging interval: {int(interval_mins)} mins.")
                                summary_metrics = []
                                
                                for sorter in active_sorters:
                                    if 'tote' in sorter.lower() or 'router' in sorter.lower():
                                        thresh = parse_redline(dna.get('tote_router_redline', 5), 5)
                                    elif 'flat' in sorter.lower():
                                        thresh = parse_redline(dna.get('flat_sorter_redline', 5), 5)
                                    elif 'mezz' in sorter.lower() or 'asrs' in sorter.lower():
                                        thresh = parse_redline(dna.get('asrs_mezz_redline', 5), 5)
                                    else:
                                        thresh = parse_redline(dna.get('shipping_sorter_redline', 15), 15)
                                        
                                    series = df_data[sorter].dropna()
                                    if series.empty: continue
                                    
                                    current_val = series.iloc[-1]
                                    min_val = series.min()
                                    max_val = series.max()
                                    avg_val = series.mean()
                                    
                                    is_oos = series > thresh
                                    oos_count = is_oos.sum()
                                    total_oos_mins = oos_count * interval_mins
                                    
                                    spikes = (is_oos & ~is_oos.shift(1).fillna(False)).sum()
                                    status = "OOS" if current_val > thresh else "Standard"
                                    
                                    summary_metrics.append({
                                        "Sorter ID": sorter,
                                        "Threshold": f"{thresh}",
                                        "Live Status": status,
                                        "Live Value": f"{current_val:.1f}",
                                        "Spikes Detected": int(spikes),
                                        "Total Time OOS": f"{int(total_oos_mins)} mins",
                                        "Min / Avg / Max": f"{min_val:.1f} / {avg_val:.1f} / {max_val:.1f}"
                                    })
                                    
                                    st.markdown(f"### ⚙️ {sorter}")
                                    c1, c2, c3, c4 = st.columns(4)
                                    with c1: 
                                        if status == "OOS": st.markdown(f"<div class='metric-box metric-red'>OOS ({current_val:.1f})</div>", unsafe_allow_html=True)
                                        else: st.markdown(f"<div class='metric-box metric-green'>STANDARD ({current_val:.1f})</div>", unsafe_allow_html=True)
                                    with c2: st.metric("Allowed Limit", f"{thresh}")
                                    with c3: st.metric("Spike Events", int(spikes))
                                    with c4: st.metric("Total Time OOS", f"{int(total_oos_mins)} mins")
                                    
                                    chart_df = df_data[['Time', sorter]].dropna().copy()
                                    chart_df.rename(columns={sorter: 'Recirc_Value'}, inplace=True)
                                    
                                    base = alt.Chart(chart_df).encode(x=alt.X('Time:T', title='Time'))
                                    line = base.mark_line(strokeWidth=3).encode(
                                        y=alt.Y('Recirc_Value:Q', title='Value'),
                                        color=alt.condition(alt.datum['Recirc_Value'] > thresh, alt.value('red'), alt.value('#00a8e1'))
                                    )
                                    rule = alt.Chart(pd.DataFrame({'y': [thresh]})).mark_rule(color='red', strokeDash=[5,5]).encode(y='y')
                                    st.altair_chart(line + rule, use_container_width=True)
                                    st.markdown("---")
                                    
                                if summary_metrics:
                                    st.markdown("### 📊 Sorter Shift Summary")
                                    st.dataframe(pd.DataFrame(summary_metrics), use_container_width=True)
                                    
                        else: st.error("Could not parse 'Time' column.")
                    except Exception as e: st.error(f"Sorter Analysis Error: {e}")

        # ---------------------------------------------------------
        # TAB: WIP COMMAND
        # ---------------------------------------------------------
        elif tab_name == "WIP (Command)":
            with tabs[idx]:
                st.subheader("CHILL WIP Command Center")
                st.caption(f"⚙️ **Live Sync Active:** Dynamically calculating buffers based on inputs from the Logic Engine.")
                
                wip_file = st.file_uploader("Upload WIP Telemetry Data (.csv)", type=["csv"], key=f"{site_name}_wip_up")
                
                if wip_file:
                    try:
                        df_raw = pd.read_csv(wip_file, header=None)
                        
                        if df_raw.iloc[0, 0] == 'Id' and df_raw.iloc[1, 0] == 'Label':
                            label_row = df_raw.iloc[1].tolist()
                            clean_labels = ['Time']
                            for lbl in label_row[1:]:
                                lbl_str = str(lbl)
                                clean_lbl = re.sub(r'\[.*?\]', '', lbl_str).replace('Label=', '').replace('"', '').strip()
                                orig_name = clean_lbl
                                count = 1
                                while clean_lbl in clean_labels:
                                    clean_lbl = f"{orig_name} {count}"
                                    count += 1
                                clean_labels.append(clean_lbl)
                                
                            data_start_idx = df_raw[df_raw[0] == 'Max'].index[0] + 1 if 'Max' in df_raw[0].values else 3
                            df_w = df_raw.iloc[data_start_idx:].copy()
                            df_w.columns = clean_labels
                        else:
                            wip_file.seek(0)
                            df_w = pd.read_csv(wip_file, header=0)
                            df_w = clean_cols(df_w)
                            df_w.rename(columns={df_w.columns[0]: 'Time'}, inplace=True)
                        
                        df_w = df_w.dropna(axis=1, how='all')
                        
                        if 'Time' in df_w.columns:
                            df_w['Time'] = df_w['Time'].astype(str).str.replace(r' [A-Z]{3,4}$', '', regex=True)
                            df_w['Time'] = pd.to_datetime(df_w['Time'], errors='coerce')
                            df_w = df_w.dropna(subset=['Time'])
                        
                        picked_cols = []
                        valid_path_keywords = ['pp', 'putwall', 'batch', 'mix', 'single', 'autobagger', 'non_conveyable', 'wrap']
                        ignore_keywords = ['dest', 'transit', 'min', 'max', 'usage', 'throttle', 'criteria', 'recirc', 'sorter']
                        
                        for c in df_w.columns:
                            if c == 'Time': continue
                            cl = c.lower().replace(' ', '').replace('.', '')
                            if any(ig in cl for ig in ignore_keywords): continue
                            
                            if 'picked' in cl or any(pk in cl for pk in valid_path_keywords):
                                picked_cols.append(c)
                        
                        if picked_cols:
                            std_wip, std_max = 0, 0
                            batch_wip, batch_max = 0, 0
                            path_analyses = []
                            path_table_data = [] 
                            wip_health_dict = {}
                            
                            for col in picked_cols:
                                clean_str = col.replace('Label=', '').replace('"', '').lower()
                                path_name_raw = clean_str.split(' ')[0]
                                clean_path = path_name_raw.replace('pp', '')

                                if 'smartpac' in clean_path and 'poly' in clean_path: clean_path = 'spp'
                                elif 'cw1000' in clean_path: clean_path = 'cw1000'
                                elif 'sioc' in clean_path: clean_path = 'non_conveyable'
                                elif 'autobag' in clean_path: clean_path = 'autobagger'
                                elif 'mix' in clean_path: clean_path = 'mix'
                                elif 'single' in clean_path: clean_path = 'singles'
                                
                                is_sort = ('putwall' in clean_path or 'rebin' in clean_path) and 'batch' not in clean_path
                                is_batch = 'batch' in clean_path
                                series = pd.to_numeric(df_w[col], errors='coerce')
                                series = series[series.notna()]
                                if len(series) == 0: continue
                                current_val = series.iloc[-1]
                                
                                candidates = [
                                    f"{clean_path}_buffer_min",
                                    f"pp{clean_path}_buffer_min",
                                    f"{path_name_raw}_buffer_min"
                                ]
                                
                                if 'poly' in path_name_raw: candidates.append('spp_buffer_min')
                                if 'cw1000' in path_name_raw: candidates.append('cw1000_buffer_min')
                                if 'non_conveyable' in path_name_raw: candidates.append('non_conveyable_buffer_min')
                                
                                spec_min = None
                                spec_max = None
                                
                                for k in candidates:
                                    if k in dna and safe_int(dna[k]) > 0:
                                        spec_min = safe_int(dna[k])
                                        max_k = k.replace('_min', '_max')
                                        if max_k in dna: spec_max = safe_int(dna[max_k])
                                        break

                                if is_sort:
                                    matched_modules = store.get('total_putwalls', 12) 
                                    for k, v in store.get('active_hcs', {}).items():
                                        if 'modules' in k.lower() and clean_path in k.lower(): matched_modules = v; break
                                    
                                    min_mult = spec_min if spec_min is not None else putwall_min_global
                                    max_mult = spec_max if spec_max is not None else putwall_max_global
                                    calc_min = matched_modules * min_mult
                                    calc_max = matched_modules * max_mult
                                    basis_str = f"{matched_modules} Active Modules"
                                else:
                                    matched_hc = 10 
                                    for k, v in store.get('active_hcs', {}).items():
                                        if 'hc' in k.lower() and clean_path in k.lower(): matched_hc = v; break
                                    
                                    min_mult = spec_min if spec_min is not None else path_min_global
                                    max_mult = spec_max if spec_max is not None else path_max_global
                                    calc_min = matched_hc * min_mult
                                    calc_max = matched_hc * max_mult
                                    basis_str = f"{matched_hc} Active HC"
                                
                                if current_val < calc_min:
                                    status = "⚠️ Low WIP / Starvation"
                                    health_key = "Starvation"
                                elif current_val > calc_max:
                                    status = "🔴 High WIP / Blowout"
                                    health_key = "Blowout"
                                else:
                                    status = "✅ Healthy"
                                    health_key = "Healthy"
                                    
                                clean_label = path_name_raw.upper()
                                wip_health_dict[clean_label] = health_key
                                path_table_data.append({
                                    "Process Path": clean_label,
                                    "Basis (Logic Tab)": basis_str,
                                    "Range (Min-Max)": f"x{min_mult} - x{max_mult}",
                                    "Calc Buffer Target": f"{int(calc_min)} - {int(calc_max)}",
                                    "Live WIP": int(current_val),
                                    "Status": status
                                })
                                
                                if is_batch:
                                    batch_wip += current_val
                                    batch_max += calc_max
                                else:
                                    std_wip += current_val
                                    std_max += calc_max
                                    
                                path_analyses.append({'name': clean_label, 'current': current_val, 'min': calc_min, 'max': calc_max, 'series': series, 'is_batch': is_batch, 'basis': basis_str, 'status': status})

                            store['wip_health'] = wip_health_dict

                            if path_table_data:
                                st.markdown("#### 📊 Dynamic Buffer Calculation Table")
                                st.caption("CHILL uses the inputs from the Logic Engine tab to calculate these targets in real-time.")
                                st.dataframe(pd.DataFrame(path_table_data), use_container_width=True)
                                st.divider()

                            w1, w2 = st.columns(2)
                            with w1:
                                st.markdown("#### Standard Flow WIP (Sortation/Singles)")
                                std_var = ((std_wip - std_max) / std_max * 100) if std_max > 0 else 0
                                st.metric("Total Standard WIP", f"{int(std_wip):,}", f"{int(std_var)}% variance", delta_color="inverse")
                                st.caption(f"Allowed Maximum Buffer: {int(std_max):,}")
                            with w2:
                                st.markdown("<div class='batch-box'>", unsafe_allow_html=True)
                                st.markdown("#### Batch Pick & Sort Flow WIP")
                                batch_var = ((batch_wip - batch_max) / batch_max * 100) if batch_max > 0 else 0
                                st.metric("Total Batch WIP", f"{int(batch_wip):,}", f"{int(batch_var)}% variance", delta_color="inverse")
                                st.caption(f"Allowed Maximum Buffer: {int(batch_max):,}")
                                st.markdown("</div>", unsafe_allow_html=True)
                            
                            st.divider()
                            st.markdown("### Path Diagnostics")
                            cols = st.columns(4)
                            for i, p in enumerate(path_analyses):
                                variance = ((p['current'] - p['max']) / p['max']) * 100 if p['max'] > 0 else 0
                                icon = "📦" if not p['is_batch'] else "🟪"
                                is_alert = "Blowout" in p['status'] or "Starvation" in p['status']
                                with cols[i % 4]:
                                    with st.expander(f"{icon} {p['name']}", expanded=is_alert):
                                        st.metric("Current WIP", int(p['current']), delta=f"{int(p['current']-p['max'])} units", delta_color="inverse")
                                        st.caption(f"Target: {int(p['min'])} - {int(p['max'])} | {p['status']}")
                                        
                                        chart_data = pd.DataFrame({'Time': range(len(p['series'])), 'Val': p['series'].values})
                                        c = alt.Chart(chart_data).mark_line().encode(
                                            x=alt.X('Time', title=None), 
                                            y=alt.Y('Val', scale=alt.Scale(domain=[0, max(p['max'] * 1.3, p['current'] * 1.1)]))
                                        ).properties(height=100)
                                        
                                        line_max = alt.Chart(pd.DataFrame({'y': [p['max']]})).mark_rule(color='red', strokeWidth=2).encode(y='y')
                                        line_min = alt.Chart(pd.DataFrame({'y': [p['min']]})).mark_rule(color='orange', strokeDash=[5,5]).encode(y='y')
                                        
                                        st.altair_chart(c + line_max + line_min, use_container_width=True)
                        else: st.warning("No valid WIP columns (e.g. 'Picked' or 'PutWall') found in this file.")
                    except Exception as e: st.error(f"WIP Error: {e}")

        # ---------------------------------------------------------
        # TAB: RCA (ROOT CAUSE) CONSULTANT
        # ---------------------------------------------------------
        elif tab_name == "RCA (Root Cause)":
            with tabs[idx]:
                st.subheader("Root Cause Analysis (RCA) Consultant")
                st.caption(f"Active Shift RCA Threshold: {rca_limit} units")
                miss_f = st.file_uploader("Upload Raw Incident List (.txt/.csv)", type=["csv", "txt"], key=f"{site_name}_rca_up")
                
                if miss_f:
                    try:
                        if miss_f.name.endswith('.txt'): df_m = pd.read_csv(miss_f, sep='\t', low_memory=False)
                        else: df_m = pd.read_csv(miss_f, low_memory=False)
                        df_m = clean_cols(df_m)
                        
                        if 'quantity' not in df_m.columns:
                            df_m['quantity'] = 1
                        else:
                            df_m['quantity'] = pd.to_numeric(df_m['quantity'], errors='coerce').fillna(1)
                        
                        if 'process_path' in df_m.columns and 'work_pool' in df_m.columns:
                            if 'dwell_time_hours' in df_m.columns:
                                 df_m['dwell_time_hours'] = pd.to_numeric(df_m['dwell_time_hours'], errors='coerce').fillna(0)
                            else:
                                 df_m['dwell_time_hours'] = 0

                            path_stats = df_m.groupby('process_path')['quantity'].sum().reset_index(name='Miss Count')
                            path_stats = path_stats.sort_values('Miss Count', ascending=False)
                            total_misses = path_stats['Miss Count'].sum()
                            path_stats['% Contrib'] = ((path_stats['Miss Count'] / total_misses) * 100).round(1)
                            
                            pool_stats = df_m.groupby('work_pool').agg(
                                Miss_Count=('quantity', 'sum'),
                                Max_Dwell=('dwell_time_hours', 'max')
                            ).reset_index()
                            pool_stats = pool_stats.sort_values('Miss_Count', ascending=False)
                            pool_stats['% Contrib'] = ((pool_stats['Miss_Count'] / total_misses) * 100).round(1)
                            
                            sla_str = "[SLA Data Not Found]"
                            time_col = next((c for c in df_m.columns if 'expected_ship' in c or 'sla' in c or 'pull' in c), None)
                            if time_col:
                                df_m[time_col] = pd.to_datetime(df_m[time_col], errors='coerce')
                                sla_stats = df_m.groupby(df_m[time_col].dt.strftime('%H:%M'))['quantity'].sum().reset_index()
                                sla_stats = sla_stats.sort_values('quantity', ascending=False).head(3)
                                slas = [f"{row[time_col]} ({int(row['quantity'])} units)" for idx, row in sla_stats.iterrows()]
                                sla_str = ", ".join(slas)

                            st.session_state[f"{site_name}_miss_count"] = total_misses
                            
                            c1, c2 = st.columns(2)
                            with c1: st.metric("Total True Misses (Units)", f"{int(total_misses):,}")
                            with c2: st.metric("Site Threshold", f"{int(rca_limit):,}")

                            if total_misses >= rca_limit: st.error(f"CRITICAL BREACH: {int(total_misses):,} > {int(rca_limit):,}")
                            else: st.success(f"OPERATIONAL STABLE: {int(total_misses):,} < {int(rca_limit):,}")

                            date_str = datetime.now().strftime('%Y-%m-%d')
                            path_breakdown = " | ".join([f"{row['process_path']} {int(row['Miss Count'])} units {row['% Contrib']}%" for idx, row in path_stats.head(4).iterrows()])
                            pool_breakdown = " | ".join([f"{row['work_pool']} {int(row['Miss_Count'])} units {row['% Contrib']}%" for idx, row in pool_stats.head(4).iterrows()])
                            dwell_breakdown = ", ".join([f"{row['work_pool']} {row['Max_Dwell']} hr dwell" for idx, row in pool_stats.head(4).iterrows()])
                            
                            notes_section = ""
                            if store.get('shift_notes'):
                                relevant_notes = [n for n in store['shift_notes'] if any(k in n.lower() for k in ['down', 'outage', 'jam', 'maintenance', 'support', 'labor', 'sorter'])]
                                if relevant_notes:
                                    notes_section = "CORRELATED OPERATIONAL EVENTS:\n" + "\n".join(relevant_notes)
                            
                            if total_misses < rca_limit:
                                report_text = f"""*** DIAGNOSTIC SHIFT SUMMARY: {site_name} ***
DATE: {date_str}
IMPACT: {int(total_misses):,} Units (Status: MINOR - Below Threshold {int(rca_limit):,})

OVERVIEW:
{site_name} experienced a service deviation below the RCA threshold, missing a total of {int(total_misses):,} units past SLA. 

PATH BREAKDOWN:
{path_breakdown}

WORKPOOL BREAKDOWN & DWELLS:
{pool_breakdown}
Max Dwells: {dwell_breakdown}

SLA IMPACT:
{sla_str}

{notes_section}

FUTURE ACTIONS:
[Manual Input Required: Detail actions taken to prevent recurrence]
"""
                            else:
                                top_path = path_stats.iloc[0]['process_path'] if not path_stats.empty else "[Unknown Path]"
                                report_text = f"""*** ROOT CAUSE ANALYSIS (RCA) REPORT: {site_name} ***
DATE: {date_str}
IMPACT: {int(total_misses):,} Units (Status: CRITICAL BREACH >= {int(rca_limit):,})

1. PROBLEM STATEMENT (SUMMARY):

**Summary** {site_name} missed a total of {int(total_misses):,} Late Dispatches - primarily within {sla_str} SLAs. 
- Process Path(s): {path_breakdown} 

- Work Pool(s): {pool_breakdown} 

- Dwells: Scanned {dwell_breakdown} 

- Site was impacted by [Manual Input: localized OUTAGE event / bottleneck] which prompted a [Manual Input] from XX:XX - XX:XX.


2. ROOT CAUSE ANALYSIS (5 WHYS):
WHY 1: Why were {int(total_misses):,} units missed past SLA?
ANSWER: Units dwelled in {top_path} past pull time.

WHY 2: Why was dwell time high in {top_path}?
ANSWER: [Manual Input Required]

WHY 3: Why did [Cause from Why 2] occur?
ANSWER: [Manual Input Required]

WHY 4: [Systemic Reason]
ANSWER: [Manual Input Required]

WHY 5: [Root Cause]
ANSWER: [Manual Input Required]

Make sure the 5 whys are nested and each are accompanied by a relevant metric.

{notes_section}

3. CAPA (Corrective & Preventative Actions):
[ ] Immediate: ...
[ ] Preventative: ...
"""
                            st.text_area("Generated Output Report", report_text, height=450)
                            st.download_button("📄 Download Text Report", report_text, f"{site_name}_RCA_Report.txt")
                            
                            st.markdown("### 📊 Detailed Path Breakdown")
                            
                            detailed_stats = df_m.groupby('process_path').agg(
                                Miss_Count=('quantity', 'sum'),
                                Avg_Dwell_Hr=('dwell_time_hours', 'mean'),
                                Max_Dwell_Hr=('dwell_time_hours', 'max')
                            ).reset_index()
                            
                            detailed_stats = detailed_stats.sort_values('Miss_Count', ascending=False)
                            detailed_stats['% Contrib'] = ((detailed_stats['Miss_Count'] / total_misses) * 100).round(1)
                            
                            detailed_stats.rename(columns={
                                'process_path': 'Process Path',
                                'Miss_Count': 'Missed Units',
                                'Avg_Dwell_Hr': 'Avg Dwell (Hr)',
                                'Max_Dwell_Hr': 'Max Dwell (Hr)'
                            }, inplace=True)
                            
                            detailed_stats = detailed_stats[['Process Path', 'Missed Units', '% Contrib', 'Avg Dwell (Hr)', 'Max Dwell (Hr)']]
                            
                            def color_scale(col):
                                min_val = col.min()
                                max_val = col.max()
                                if min_val == max_val:
                                    return ['background-color: rgba(255, 0, 0, 0.3)'] * len(col)
                                colors = []
                                for val in col:
                                    norm = (val - min_val) / (max_val - min_val)
                                    r = int(norm * 255)
                                    g = int((1 - norm) * 200) 
                                    colors.append(f'background-color: rgba({r}, {g}, 0, 0.25)')
                                return colors
                            
                            styled_df = detailed_stats.style.apply(color_scale, subset=['Missed Units']).format({
                                '% Contrib': '{:.1f}%',
                                'Avg Dwell (Hr)': '{:.2f}',
                                'Max Dwell (Hr)': '{:.2f}'
                            })
                            
                            st.dataframe(styled_df, use_container_width=True)
                            
                        else: st.error("Error: Columns 'process_path' and 'work_pool' required.")
                    except Exception as e: st.error(f"Analysis Failed: {e}")

        # ---------------------------------------------------------
        # TAB: SCANNED / EXCEPTIONS
        # ---------------------------------------------------------
        elif tab_name == "Scanned / Exceptions":
            with tabs[idx]:
                st.subheader("Scanned & Exceptions Tracker")
                st.caption("Data is automatically populated from the latest Wave Report uploaded in the **SLA (Tactical)** tab.")
                
                curr_s_cnt = store.get('curr_scanned_cnt', 0)
                prev_s_cnt = store.get('prev_scanned_cnt', 0)
                curr_p_cnt = store.get('curr_exc_cnt', 0)
                prev_p_cnt = store.get('prev_exc_cnt', 0)
                
                s_delta = curr_s_cnt - prev_s_cnt
                p_delta = curr_p_cnt - prev_p_cnt
                
                if curr_s_cnt >= 12000:
                    st.error(f"🚨 **STAND DOWN IMMINENT:** Scanned volume ({int(curr_s_cnt):,}) exceeds 12,000 threshold!")
                elif curr_s_cnt >= 5000:
                    st.warning(f"⚠️ **ELEVATED VOLUME:** Scanned volume ({int(curr_s_cnt):,}) exceeds 5,000 threshold.")
                elif curr_s_cnt >= 2500:
                    st.info(f"ℹ️ **HIGH VOLUME:** Scanned volume ({int(curr_s_cnt):,}) exceeds 2,500 threshold.")

                if curr_p_cnt >= 1000:
                    st.error(f"🚨 **STAND DOWN IMMINENT:** Exception volume ({int(curr_p_cnt):,}) exceeds 1,000 threshold!")
                elif curr_p_cnt >= 500:
                    st.warning(f"⚠️ **ELEVATED EXCEPTIONS:** Exception volume ({int(curr_p_cnt):,}) exceeds 500 threshold.")
                
                m1, m2 = st.columns(2)
                with m1:
                    st.metric("Total Scanned Units", f"{int(curr_s_cnt):,}", delta=int(s_delta))
                with m2:
                    st.metric("Total Exceptions (QA) Units", f"{int(curr_p_cnt):,}", delta=int(p_delta), delta_color="inverse")
                    
                st.divider()
                
                col1, col2 = st.columns(2)
                
                curr_s_paths = store.get('curr_scanned_paths', {})
                prev_s_paths = store.get('prev_scanned_paths', {})
                
                s_table = []
                all_s_paths = set(curr_s_paths.keys()).union(set(prev_s_paths.keys()))
                for p in sorted(all_s_paths):
                    c = int(curr_s_paths.get(p, 0))
                    pr = int(prev_s_paths.get(p, 0))
                    d = c - pr
                    arr = "🔼" if d > 0 else "🔽" if d < 0 else "➖"
                    d_str = f"{arr} {abs(d)}" if d != 0 else "--"
                    s_table.append({"Process Path": p, "Units": c, "Trend": d_str, "SortKey": c})
                    
                curr_p_paths = store.get('curr_exc_paths', {})
                prev_p_paths = store.get('prev_exc_paths', {})
                
                p_table = []
                all_p_paths = set(curr_p_paths.keys()).union(set(prev_p_paths.keys()))
                for p in sorted(all_p_paths):
                    c = int(curr_p_paths.get(p, 0))
                    pr = int(prev_p_paths.get(p, 0))
                    d = c - pr
                    arr = "🔼" if d > 0 else "🔽" if d < 0 else "➖"
                    d_str = f"{arr} {abs(d)}" if d != 0 else "--"
                    p_table.append({"Process Path": p, "Units": c, "Trend": d_str, "SortKey": c})
                    
                with col1:
                    st.markdown("#### ✅ Scanned Breakdown")
                    if s_table:
                        df_s = pd.DataFrame(s_table).sort_values('SortKey', ascending=False).drop(columns=['SortKey'])
                        st.dataframe(df_s, use_container_width=True, hide_index=True)
                    else:
                        st.info("No Scanned units detected in active backlog.")
                        
                with col2:
                    st.markdown("#### ⚠️ Exceptions Breakdown")
                    if p_table:
                        df_p = pd.DataFrame(p_table).sort_values('SortKey', ascending=False).drop(columns=['SortKey'])
                        st.dataframe(df_p, use_container_width=True, hide_index=True)
                    else:
                        st.info("No Exception units detected in active backlog.")

        # ---------------------------------------------------------
        # TAB: SHIFT NOTES
        # ---------------------------------------------------------
        elif tab_name == "Shift Notes":
            with tabs[idx]:
                st.subheader("Shift Notes & Event Log")
                st.caption("Notes logged here will be automatically correlated with the RCA report generator.")
                
                c_in, c_btn = st.columns([6, 1])
                with c_in:
                    note_input = st.text_input("Log an event (e.g., 'PutWall 2 Tray Sorter Jam 14:00-14:15')", key=f"{site_name}_note_in_{idx}")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Add Note", key=f"{site_name}_add_note_{idx}"):
                        if note_input:
                            ts = datetime.now(tz).strftime('%H:%M')
                            store['shift_notes'].insert(0, f"[{ts}] {note_input}")
                            st.success("Note Logged!")
                            st.rerun()
                
                st.divider()
                
                if store.get('shift_notes'):
                    for note in store['shift_notes']:
                        st.markdown(f"<div class='note-log'>{note}</div>", unsafe_allow_html=True)
                else:
                    st.info("No notes logged for this shift yet.")

        # ---------------------------------------------------------
        # TAB: QUERY
        # ---------------------------------------------------------
        elif tab_name == "Query":
            with tabs[idx]:
                st.subheader(f"💬 Ask CHILL ({site_name})")
                for msg in store['chat_history']:
                    with st.chat_message(msg["role"]): st.write(msg["content"])
                
                if prompt := st.chat_input(f"Query {site_name} data...", key=f"{site_name}_chat"):
                    store['chat_history'].append({"role": "user", "content": prompt})
                    with st.chat_message("user"): st.write(prompt)
                    answer = process_query(prompt, site_name, site_data)
                    store['chat_history'].append({"role": "assistant", "content": answer})
                    with st.chat_message("assistant"): st.write(answer)

# ==============================================================================
# PHASE 1: INITIAL SETUP
# ==============================================================================
if not st.session_state.setup_complete:
    st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="margin-bottom: 0px; font-weight: 900; color: #ffffff; letter-spacing: 4px; font-size: 70px;">❄️ CHILL</h1>
            <p style="font-size: 24px; color: #00a8e1; font-weight: bold; margin-top: 0px;">Critical Health Integrated Learning Library</p>
        </div>
    """, unsafe_allow_html=True)
    st.divider()
    
    st.write("### ⚙️ System Initialization")
    dna_file = st.file_uploader("1. Upload Network Config (Site_DNA)", type=["xlsx", "csv"])
    if dna_file:
        try:
            if dna_file.name.endswith('.csv'): df_dna = pd.read_csv(dna_file)
            else: df_dna = pd.read_excel(dna_file)
            df_dna = clean_cols(df_dna)
            target_col = next((c for c in df_dna.columns if 'code' in c or 'site' in c), None)
            if target_col:
                all_sites = df_dna[target_col].astype(str).str.upper().unique().tolist()
                
                global_shift_disp = st.radio("Select Global Shift", ["☀️ Day Shift (DS)", "🌙 Night Shift (NS)"], horizontal=True)
                global_shift = "DS" if "Day" in global_shift_disp else "NS"
                
                season_disp = st.radio("Select Operational Volume", ["🟩 Standard", "🟥 PEAK"], horizontal=True)
                season_val = "PEAK" if "PEAK" in season_disp else "STANDARD"
                
                c1, c2 = st.columns(2)
                with c1: s1 = st.selectbox("Primary Site", all_sites, key="s1")
                with c2: s2 = st.selectbox("Secondary Site (Optional)", ["None"] + all_sites, key="s2")
                
                st.write("") 
                if st.button("🚀 RUN FLOW", type="primary", use_container_width=True):
                    row1 = df_dna[df_dna[target_col].astype(str).str.upper() == s1].iloc[0]
                    tz_col = next((c for c in df_dna.columns if 'iana' in c or 'time' in c and 'zone' in c), None)
                    st.session_state.active_sites[s1] = {'dna': row1.to_dict(), 'shift': global_shift, 'timezone': row1[tz_col] if tz_col else 'UTC', 'season': season_val}
                    if s2 != "None":
                        row2 = df_dna[df_dna[target_col].astype(str).str.upper() == s2].iloc[0]
                        st.session_state.active_sites[s2] = {'dna': row2.to_dict(), 'shift': global_shift, 'timezone': row2[tz_col] if tz_col else 'UTC', 'season': season_val}
                    st.session_state.setup_complete = True
                    st.rerun()
            else: st.error("Site Code column not found.")
        except Exception as e: st.error(f"Error: {e}")

# Phase 2 Header Update
if st.session_state.setup_complete:
    c_title, c_btn = st.columns([8, 1])
    with c_title:
        st.markdown("""
            <div style="margin-top: -20px; padding-bottom: 10px;">
                <h2 style="margin-bottom: 0px; font-weight: 900; color: #ffffff; letter-spacing: 2px;">❄️ CHILL</h2>
                <p style="font-size: 14px; color: #00a8e1; font-weight: bold; margin-top: 0px; margin-bottom: 0px;">Critical Health Integrated Learning Library</p>
            </div>
        """, unsafe_allow_html=True)
    with c_btn:
        st.write("") 
        if st.button("GLOBAL RESET", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    site_names = list(st.session_state.active_sites.keys())
    st.write("") 
    
    site_tab_names = [f"🏢 {s_name} CONSOLE" for s_name in site_names]
    top_tabs = st.tabs(site_tab_names)
    
    for i, site_name in enumerate(site_names):
        with top_tabs[i]:
            render_site_dashboard(site_name, st.session_state.active_sites[site_name])