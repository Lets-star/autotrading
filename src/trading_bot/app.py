import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import time
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from trading_bot.config import settings
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.data_feeds.market_data_service import MarketDataService
from trading_bot.ui.charting import plot_candle_chart, plot_volume_chart, render_tradingview_chart

# -- Constants & Helpers --
DAEMON_SCRIPT = "scripts/bot_daemon.py"
STATUS_FILE = "signals/status.json"
COMMAND_FILE = "signals/command.txt"
POSITIONS_FILE = "data/positions.json"
LOG_FILE = "logs/bot.log"
PRESETS_FILE = "presets.json"

def is_daemon_running():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r') as f:
                status = json.load(f)
            pid = status.get('pid')
            if pid:
                # Check if process exists
                try:
                    os.kill(pid, 0)
                    # Also check if timestamp is recent (e.g. within 10 seconds)
                    last_update = status.get('last_update')
                    if last_update:
                        dt = datetime.fromisoformat(last_update)
                        if (datetime.now() - dt).total_seconds() > 30:
                            return False # Stale
                    return True
                except OSError:
                    return False
        except:
            return False
    return False

def start_bot_daemon():
    if not is_daemon_running():
        # Start the process in background
        # Calculate project root: src/trading_bot/app.py -> src/trading_bot -> src -> project_root
        root_dir = Path(__file__).resolve().parents[2]
        daemon_script = root_dir / DAEMON_SCRIPT
        
        # On Windows, use CREATE_NEW_PROCESS_GROUP and CREATE_NO_WINDOW to prevent the subprocess
        # from inheriting the console. This prevents the daemon from affecting Streamlit's process.
        import platform
        startup_kwargs = {
            'cwd': str(root_dir),
            'stdin': subprocess.DEVNULL,
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL
        }
        
        if platform.system() == 'Windows':
            # CREATE_NEW_PROCESS_GROUP = 0x00000200
            # CREATE_NO_WINDOW = 0x08000000
            startup_kwargs['creationflags'] = 0x00000200 | 0x08000000
        
        try:
            subprocess.Popen([sys.executable, str(daemon_script)], **startup_kwargs)
            time.sleep(2) # Wait for startup
        except Exception as e:
            st.error(f"Failed to start bot daemon: {e}")
            return

def send_command(cmd):
    # Ensure directory exists
    os.makedirs(os.path.dirname(COMMAND_FILE), exist_ok=True)
    with open(COMMAND_FILE, 'w') as f:
        f.write(cmd)

def get_bot_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def get_positions():
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return []

def get_logs(lines=50):
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return f.readlines()[-lines:]
        except:
            pass
    return []

def load_presets():
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_preset(name, data):
    presets = load_presets()
    presets[name] = data
    with open(PRESETS_FILE, 'w') as f:
        json.dump(presets, f, indent=4)

st.set_page_config(page_title="Trading Bot Dashboard", layout="wide", page_icon="📈")

# -- Secrets & Config --
try:
    BYBIT_API_KEY = st.secrets["bybit"]["api_key"]
    BYBIT_API_SECRET = st.secrets["bybit"]["api_secret"]
except:
    BYBIT_API_KEY = settings.api_key
    BYBIT_API_SECRET = settings.api_secret

if not BYBIT_API_KEY:
    st.sidebar.warning("No API Key found. Using public endpoints only where possible.")

# -- Services --
@st.cache_resource
def get_market_service(api_key, api_secret):
    return MarketDataService(
        api_key=api_key, 
        api_secret=api_secret, 
        symbol="BTCUSDT", 
        timeframes=["1h", "4h", "1d"],
        selected_timeframe="1h"
    )

service = get_market_service(BYBIT_API_KEY, BYBIT_API_SECRET)

# -- Sidebar Controls --
st.sidebar.title("🤖 Bot Control")
mode = st.sidebar.radio("Operation Mode", ["Live Dashboard", "Backtest Lab"])

st.sidebar.markdown("---")
st.sidebar.subheader("Settings")
selected_symbol = st.sidebar.text_input("Symbol", "BTCUSDT", key="selected_pair")

# Timeframe Selector
if "active_timeframes" not in st.session_state:
    st.session_state.active_timeframes = ["1h", "4h", "1d"]

if "selected_timeframe" not in st.session_state:
    st.session_state.selected_timeframe = "1h"

available_timeframes = ["5m", "15m", "30m", "1h", "3h", "4h", "1d", "1week"]
selected_timeframes = st.sidebar.multiselect(
    "Active Timeframes (MTF)",
    available_timeframes,
    default=st.session_state.active_timeframes,
    key="timeframe_selector"
)
st.session_state.active_timeframes = selected_timeframes

# Primary Timeframe Selector
primary_timeframe = st.sidebar.selectbox(
    "Primary Timeframe", 
    available_timeframes, 
    index=available_timeframes.index("1h") if "1h" in available_timeframes else 0,
    key="selected_timeframe"
)

# Update service settings if changed
if service.symbol != selected_symbol:
    service.symbol = selected_symbol
    
if service.timeframes != selected_timeframes:
    service.timeframes = selected_timeframes
    service.scoring.active_timeframes = selected_timeframes

if service.selected_timeframe != primary_timeframe:
    service.selected_timeframe = primary_timeframe

# -- Advanced Configuration (New) --
st.sidebar.markdown("---")
st.sidebar.subheader("Advanced Configuration")

presets = load_presets()
preset_names = ["Default"] + list(presets.keys())

# Preset Loader
c_p1, c_p2 = st.sidebar.columns([3, 1])
selected_preset = c_p1.selectbox("Preset", preset_names, label_visibility="collapsed")
if c_p2.button("Load"):
    if selected_preset != "Default":
        data = presets[selected_preset]
        for k, v in data.items():
            st.session_state[k] = v
        st.success(f"Loaded!")
        time.sleep(0.5)
        st.rerun()

# Configuration Tabs
tab_weights, tab_signal, tab_risk = st.sidebar.tabs(["Weights", "Signal", "Risk"])

with tab_weights:
    st.markdown("**Group Weights**")
    w_tech = st.slider("Technical", 0.0, 1.0, 0.2, key="w_tech")
    w_ob = st.slider("Orderbook", 0.0, 1.0, 0.2, key="w_ob")
    w_ms = st.slider("Structure", 0.0, 1.0, 0.2, key="w_ms")
    w_sent = st.slider("Sentiment", 0.0, 1.0, 0.2, key="w_sent")
    w_mtf = st.slider("MTF Align", 0.0, 1.0, 0.2, key="w_mtf")
    
    # Normalize Group Weights
    total_w = w_tech + w_ob + w_ms + w_sent + w_mtf
    if total_w == 0: total_w = 1.0
    
    st.caption(f"Norm: T:{w_tech/total_w:.2f} O:{w_ob/total_w:.2f} S:{w_ms/total_w:.2f} Sent:{w_sent/total_w:.2f} MTF:{w_mtf/total_w:.2f}")

    st.markdown("**Technical Sub-weights**")
    sw_rsi = st.slider("RSI", 0.0, 1.0, 0.2, key="sw_rsi")
    sw_macd = st.slider("MACD", 0.0, 1.0, 0.2, key="sw_macd")
    sw_atr = st.slider("ATR", 0.0, 1.0, 0.2, key="sw_atr")
    sw_bb = st.slider("Bollinger", 0.0, 1.0, 0.2, key="sw_bb")
    sw_div = st.slider("Divergences", 0.0, 1.0, 0.2, key="sw_div")

    total_sw = sw_rsi + sw_macd + sw_atr + sw_bb + sw_div
    if total_sw == 0: total_sw = 1.0

with tab_signal:
    st.markdown("**Signal Thresholds**")
    sig_long = st.slider("Long Threshold", 0.5, 1.0, 0.6, key="sig_long")
    sig_short = st.slider("Short Threshold", 0.0, 0.5, 0.4, key="sig_short")
    sig_conf = st.slider("Confidence Min", 0.0, 1.0, 0.5, key="sig_conf")
    
    st.markdown("**Calibration Targets**")
    target_wr = st.slider("Win Rate Target %", 30, 90, 60, key="target_wr")
    target_dd = st.slider("Max Drawdown %", 5, 50, 20, key="target_dd")

with tab_risk:
    st.markdown("**Risk Parameters**")
    risk_pos = st.slider("Max Position ($)", 10.0, 10000.0, 100.0, key="risk_pos")
    risk_pct = st.slider("Risk per Trade %", 0.1, 5.0, 1.0, key="risk_pct")
    leverage = st.slider("Leverage", 1, 20, 1, key="risk_lev")
    
    st.markdown("**TP/SL Multipliers**")
    sl_mult = st.slider("SL (xATR)", 0.5, 5.0, 2.0, key="risk_sl_mult")
    tp1 = st.slider("TP1 (xSL)", 1.0, 5.0, 1.5, key="risk_tp1")
    tp2 = st.slider("TP2 (xSL)", 1.0, 10.0, 3.0, key="risk_tp2")
    tp3 = st.slider("TP3 (xSL)", 1.0, 20.0, 5.0, key="risk_tp3")

with st.sidebar.expander("Save Preset"):
    new_preset_name = st.text_input("Name", key="new_preset_name")
    if st.button("Save Preset"):
        if new_preset_name:
            current_settings = {
                "w_tech": w_tech, "w_ob": w_ob, "w_ms": w_ms, "w_sent": w_sent, "w_mtf": w_mtf,
                "sw_rsi": sw_rsi, "sw_macd": sw_macd, "sw_atr": sw_atr, "sw_bb": sw_bb, "sw_div": sw_div,
                "sig_long": sig_long, "sig_short": sig_short, "sig_conf": sig_conf, 
                "target_wr": target_wr, "target_dd": target_dd,
                "risk_pos": risk_pos, "risk_pct": risk_pct, "risk_lev": leverage, 
                "risk_sl_mult": sl_mult, "risk_tp1": tp1, "risk_tp2": tp2, "risk_tp3": tp3
            }
            save_preset(new_preset_name, current_settings)
            st.success(f"Saved {new_preset_name}")
            time.sleep(0.5)
            st.rerun()

if st.sidebar.button("Reset to Defaults"):
    # Clear keys from session state
    keys = ["w_tech", "w_ob", "w_ms", "w_sent", "w_mtf", "sw_rsi", "sw_macd", "sw_atr", "sw_bb", "sw_div",
            "sig_long", "sig_short", "sig_conf", "target_wr", "target_dd", 
            "risk_pos", "risk_pct", "risk_lev", "risk_sl_mult", "risk_tp1", "risk_tp2", "risk_tp3"]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()

# Apply Settings to Service
g_weights = {
    'Technical': w_tech/total_w,
    'Orderbook': w_ob/total_w,
    'MarketStructure': w_ms/total_w,
    'Sentiment': w_sent/total_w,
    'MultiTimeframe': w_mtf/total_w
}
s_weights = {
    'technical_rsi': sw_rsi/total_sw,
    'technical_macd': sw_macd/total_sw,
    'technical_atr': sw_atr/total_sw,
    'technical_bb': sw_bb/total_sw,
    'technical_divergences': sw_div/total_sw
}

service.scoring.update_weights_from_groups(g_weights, s_weights)
service.scoring.update_signal_parameters(sig_long, sig_short, sig_conf)
service.risk.update_parameters(
    max_pos_size=risk_pos,
    max_risk_pct=risk_pct/100.0,
    leverage=leverage,
    tp_mults=[tp1, tp2, tp3],
    sl_mult=sl_mult
)

# Start service if not running
service.start()

if mode == "Live Dashboard":
    st.title(f"Live Dashboard: {selected_symbol} ({primary_timeframe})")
    
    # Auto-refresh logic (basic)
    auto_refresh = st.sidebar.checkbox("Auto-refresh (1s)", value=False)
    
    # Display Status
    status_col1, status_col2, status_col3 = st.sidebar.columns(3)
    data = service.get_data()
    
    status_col1.metric("Status", data['status'])
    status_col2.metric("Updates", data['update_count'])
    
    if data['last_updated'] > 0:
        latency = time.time() - data['last_updated']
        status_col3.metric("Latency", f"{latency:.1f}s")
    
    if data['error']:
        st.sidebar.error(f"Error: {data['error']}")

    # 1. Top Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    
    df = data.get("price_history", pd.DataFrame())
    signal = data.get("signal", {})
    
    if not df.empty:
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price_change = latest['close'] - prev['close']
        
        # Safe access to signal
        score = signal.get('score', 0.0) if signal else 0.0
        action = signal.get('action', 'NEUTRAL') if signal else 'NEUTRAL'
        details = signal.get('details', {})
        
        col1.metric("Price", f"{latest['close']:.2f}", f"{price_change:.2f}")
        col2.metric("Composite Score", f"{score:.2f}", delta_color="off")
        col3.metric("Action", action, delta_color="normal")
        
        risk = data.get("risk_metrics", {})
        if risk and 'sl' in risk:
             col4.metric("SL / TP", f"{risk['sl']:.2f} / {risk['tp']:.2f}", f"ATR: {risk['atr']:.2f}")
        else:
             atr_val = risk.get('atr', 0.0)
             col4.metric("Risk Status", "Watching", f"ATR: {atr_val:.2f}" if atr_val > 0 else "")
        
        # --- Composite Score Breakdown ---
        if details:
            st.markdown("### Composite Score Breakdown")
            
            # Prepare data
            components = details.get('components', {})
            weights = details.get('weights', {})
            
            comp_data = []
            for name, comp_res in components.items():
                cat = comp_res.get('category', 'Uncategorized')
                s_val = comp_res.get('score', 0.0)
                conf = comp_res.get('confidence', 1.0)
                w_val = weights.get(name, 1.0)
                contribution = s_val * w_val * conf
                
                comp_data.append({
                    "Name": name,
                    "Category": cat,
                    "Score": s_val,
                    "Weight": w_val,
                    "Confidence": conf,
                    "Contribution": contribution
                })
            
            comp_df = pd.DataFrame(comp_data)
            
            if not comp_df.empty:
                # Top level stats
                st.caption(f"Aggregated Score: {details.get('aggregated_score', 0.0):.3f}")
                
                # Visuals
                v1, v2 = st.columns([2, 1])
                with v1:
                    st.markdown("**Component Scores**")
                    # Simple bar chart of scores
                    st.bar_chart(comp_df.set_index("Name")['Score'])
                    
                with v2:
                    st.markdown("**Weights**")
                    st.bar_chart(comp_df.set_index("Name")['Weight'])
                
                # Detailed Grid by Category
                st.markdown("**Detailed Components**")
                categories = comp_df['Category'].unique()
                
                # Create rows of columns
                # We'll just iterate and create expanders or columns
                cat_cols = st.columns(len(categories)) if len(categories) > 0 else [st.container()]
                
                for idx, cat in enumerate(categories):
                    with cat_cols[idx % len(cat_cols)]:
                        st.info(f"**{cat}**")
                        cat_df = comp_df[comp_df['Category'] == cat]
                        for _, row in cat_df.iterrows():
                            # Render mini-card
                            # 0-0.4 Red (Bearish), 0.4-0.6 Grey (Neutral), 0.6-1 Green (Bullish)
                            if row['Score'] > 0.6:
                                score_color = ":green"
                            elif row['Score'] < 0.4:
                                score_color = ":red"
                            else:
                                score_color = ":grey"
                                
                            st.markdown(f"**{row['Name']}**")
                            st.markdown(f"Score: {score_color}[{row['Score']:.2f}] | W: {row['Weight']:.1f}")
                            st.progress(max(0.0, min(1.0, row['Score'])))
                            st.divider()

            with st.expander("Show Details (Logs & Metadata)"):
                st.json(details)

    else:
        st.warning("Waiting for data...")
    
    # 2. Charts & Order Book
    st.markdown("---")
    # Make chart column wider
    c1, c2 = st.columns([3, 1])
    
    with c1:
        st.subheader("Price History")
        if not df.empty:
            risk_metrics = data.get("risk_metrics", {})
            # Use TradingView chart
            render_tradingview_chart(df, active_risk=risk_metrics, height=500)
            
    with c2:
        st.subheader("Order Book")
        ob = data.get("orderbook", {})
        if ob:
            bids = pd.DataFrame(ob.get('bids', []), columns=['Price', 'Size'])
            asks = pd.DataFrame(ob.get('asks', []), columns=['Price', 'Size'])
            
            # Convert to numeric for display
            if not bids.empty:
                bids['Price'] = pd.to_numeric(bids['Price'])
                bids['Size'] = pd.to_numeric(bids['Size'])
            if not asks.empty:
                asks['Price'] = pd.to_numeric(asks['Price'])
                asks['Size'] = pd.to_numeric(asks['Size'])
            
            st.markdown("**Asks**")
            st.dataframe(asks.head(5), hide_index=True)
            st.markdown("**Bids**")
            st.dataframe(bids.head(5), hide_index=True)
        else:
            st.write("Order book unavailable")
            
    # 3. Active Positions & Logs
    st.subheader("Active Positions")
    
    positions = get_positions()
    if positions:
        # Columns: Pair, Entry Price, Current Price, TP1, TP2, TP3, SL, PnL, PnL%
        # We need to map Bybit fields to these
        pos_data = []
        for p in positions:
            entry = float(p.get('avgPrice', 0))
            curr = float(p.get('markPrice', 0))
            pnl = float(p.get('unrealisedPnl', 0))
            size = float(p.get('size', 0)) * float(p.get('avgPrice', 0)) # Approximate value
            pnl_pct = (pnl / size * 100) if size > 0 else 0.0
            
            pos_data.append({
                "Pair": p.get('symbol'),
                "Side": p.get('side'),
                "Size": p.get('size'),
                "Entry Price": entry,
                "Current Price": curr,
                "SL": p.get('stopLoss', '-'),
                "TP": p.get('takeProfit', '-'),
                "PnL": pnl,
                "PnL %": pnl_pct
            })
        
        pos_df = pd.DataFrame(pos_data)
        
        # Color styling for PnL
        def color_pnl(val):
            color = 'green' if val > 0 else 'red' if val < 0 else 'grey'
            return f'color: {color}'

        st.dataframe(
            pos_df.style.map(color_pnl, subset=['PnL', 'PnL %'])
                        .format({
                            'Entry Price': '{:.4f}',
                            'Current Price': '{:.4f}',
                            'PnL': '{:.4f}',
                            'PnL %': '{:.2f}%'
                        }),
            use_container_width=True
        )
        
        # Close button (Implementation would need another signal or API call)
        # For now, just a placeholder or we can implement a specific close signal
        # Ticket says: "Кнопка 'Close Position' для закрытия вручную"
        # Since we use signals/command.txt, we might need a format like "CLOSE BTCUSDT"
        
        c_close = st.columns(len(positions) + 1)
        for i, p in enumerate(positions):
             if c_close[i].button(f"Close {p.get('symbol')}", key=f"close_{i}"):
                 send_command(f"CLOSE {p.get('symbol')}")
                 st.toast(f"Sent close signal for {p.get('symbol')}")

    else:
        st.info("No active positions")
    
    st.subheader("System Logs")
    logs = get_logs()
    log_text = "".join(logs) if logs else "No logs available."
    st.text_area("Log Output", log_text, height=200, key="log_output")
    
    # Bot Controls
    st.markdown("---")
    st.subheader("Bot Control")
    
    bot_status = get_bot_status()
    is_running = is_daemon_running()
    
    st.metric("Daemon Status", "Running" if is_running else "Stopped", 
              delta="Active" if is_running else "Inactive", 
              delta_color="normal" if is_running else "off")
              
    if bot_status:
        st.json(bot_status, expanded=False)

    c_start, c_stop = st.columns(2)
    
    # Start Logic
    if c_start.button("🟢 Start Bot", use_container_width=True, disabled=is_running and bot_status.get("running", False)):
        try:
            if not is_running:
                with st.spinner("Starting bot daemon..."):
                    start_bot_daemon()
                st.success("Bot daemon started successfully!")
            
            send_command("START")
            st.success("START signal sent to bot")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to start bot: {e}")

    if c_stop.button("🔴 Stop Bot", use_container_width=True):
        try:
            send_command("STOP")
            st.success("STOP signal sent to bot")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to send stop signal: {e}")
        
    if st.button("⏸ Pause Bot", use_container_width=True):
        send_command("PAUSE")
        st.info("Signal sent: PAUSE")

        
    # Auto-refresh at the end
    if auto_refresh:
        time.sleep(1)
        st.rerun()

elif mode == "Backtest Lab":
    st.title("Backtest Lab")
    
    with st.expander("Configuration", expanded=True):
        with st.form("bt_form"):
            c1, c2, c3, c4, c5 = st.columns(5)
            # Defaulting to Bybit only as per requirements
            data_source = c1.selectbox("Source", ["Bybit"]) 
            bt_symbol = c2.text_input("Symbol", selected_symbol)
            
            bt_opts = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
            def_idx = bt_opts.index(primary_timeframe) if primary_timeframe in bt_opts else 4
            
            bt_interval = c3.selectbox("Interval", bt_opts, index=def_idx)
            bt_limit = c4.slider("Len", 100, 1000, 500)
            debug_mode = c5.checkbox("Debug", value=False)
            
            run_bt = st.form_submit_button("Run Simulation")
            
    if run_bt:
        with st.spinner(f"Backtesting {bt_symbol} on {bt_interval} via {data_source}..."):
            engine = BacktestEngine(
                api_key=BYBIT_API_KEY, 
                api_secret=BYBIT_API_SECRET,
                active_timeframes=st.session_state.active_timeframes,
                data_source=data_source
            )
            
            # Apply UI Settings to Backtest Engine
            engine.scoring.update_weights_from_groups(g_weights, s_weights)
            engine.scoring.update_signal_parameters(sig_long, sig_short, sig_conf)
            engine.risk.update_parameters(
                max_pos_size=risk_pos,
                max_risk_pct=risk_pct/100.0,
                leverage=leverage,
                tp_mults=[tp1, tp2, tp3],
                sl_mult=sl_mult
            )
            
            results = engine.run(bt_symbol, bt_interval, bt_limit, debug=debug_mode)
            
            # Display connection status
            status = getattr(engine.fetcher, 'status', 'Unknown')
            status_color = "green" if status == "Connected" else "orange" if status == "Using Cache" else "red"
            st.markdown(f"**Connection Status:** :{status_color}[{status}]")
            
            if "error" in results:
                st.error(results['error'])
            else:
                st.success("Backtest Complete")
                
                # Metrics
                m1, m2, m3, m4 = st.columns(4)
                
                total_pnl = results.get('total_pnl', 0.0)
                initial_balance = results.get('initial_balance', 10000.0)
                pnl_pct = (total_pnl / initial_balance) * 100
                
                m1.metric("Total PnL", f"${total_pnl:.2f}", delta=f"{pnl_pct:.2f}%")
                m2.metric("Win Rate", f"{results.get('win_rate', 0.0):.1f}%")
                m3.metric("Trades", results.get('trade_count', 0))
                m4.metric("Final Balance", f"${results.get('final_balance', 0.0):.2f}")
                
                # Visuals
                trades_data = results.get('trades', [])
                trades_df = pd.DataFrame(trades_data)
                
                st.subheader("Price Chart with Signals")
                bt_data = results.get('data', pd.DataFrame())
                if not bt_data.empty:
                     render_tradingview_chart(bt_data, trades=trades_data, height=600)

                st.subheader("Equity Curve")
                equity_curve = results.get('equity_curve', [])
                if equity_curve:
                    st.line_chart([initial_balance] + equity_curve)
                else:
                    st.info("No equity curve to display (no trades).")
                
                if not trades_df.empty:
                    st.subheader("Trade History")
                    
                    # Style the dataframe
                    st.dataframe(
                        trades_df.style.format({
                            'entry_price': '{:.2f}',
                            'exit_price': '{:.2f}',
                            'pnl': '{:.2f}',
                            'balance': '{:.2f}',
                            'return_pct': '{:.2f}%'
                        })
                    )
                else:
                    st.warning("No trades were executed with the current strategy.")

                # Debug Logs
                if debug_mode:
                    st.subheader("Backtest Debug Logs")
                    logs = results.get('debug_logs', [])
                    if logs:
                        st.text_area("Detailed Logs", "\n".join(logs), height=300)
                    else:
                        st.info("No debug logs generated.")
