import sys
import os
import logging
import traceback
from datetime import datetime, timedelta
import time
import subprocess
import json

# -- Early Logging Setup --
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app_debug.log")
    
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    logger = logging.getLogger(__name__)
    
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    logger.info("Logging initialized early.")
    logger.info(f"Log file path: {log_file}")
    
except Exception as e:
    print(f"CRITICAL: Logging setup failed: {e}")
    traceback.print_exc()

if "project_root" not in globals():
    fallback_current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(fallback_current_dir, "..", ".."))

# -- Imports --
try:
    logger.info("Importing dependencies...")
    import streamlit as st
    import pandas as pd
    import numpy as np
    import plotly.graph_objects as go
    
    logger.info("External dependencies imported.")
    
    from trading_bot.config import settings
    from trading_bot.backtesting.engine import BacktestEngine
    from trading_bot.data_feeds.market_data_service import MarketDataService
    from trading_bot.risk.service import RiskService
    from trading_bot.ui.charting import plot_candle_chart, plot_volume_chart, render_tradingview_chart
    
    logger.info("Internal modules imported.")
    
except ImportError as e:
    logger.critical(f"Failed to import internal modules: {e}")
    try:
        import streamlit as st
        st.error(f"Import Error: {e}")
        st.stop()
    except:
        pass
    sys.exit(1)
except Exception as e:
    logger.critical(f"Unexpected error during imports: {e}")
    logger.critical(traceback.format_exc())
    try:
        import streamlit as st
        st.error(f"Unexpected Import Error: {e}")
        st.code(traceback.format_exc())
        st.stop()
    except:
        pass
    sys.exit(1)

# -- Constants & Helpers --
PROJECT_ROOT = project_root
SIGNALS_DIR = os.path.join(PROJECT_ROOT, "signals")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
DAEMON_SCRIPT = os.path.join(SCRIPTS_DIR, "bot_daemon.py")
STATUS_FILE = os.path.join(SIGNALS_DIR, "status.json")
COMMAND_FILE = os.path.join(SIGNALS_DIR, "command.txt")
POSITIONS_FILE = os.path.join(DATA_DIR, "positions.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.csv")
LOG_FILE = os.path.join(LOGS_DIR, "bot.log")
PRESETS_FILE = os.path.join(PROJECT_ROOT, "presets.json")
DAEMON_STALE_THRESHOLD = 15  # seconds

def is_daemon_running():
    """Return True if the daemon reports an active running state."""
    return get_daemon_health()["running"]


def start_bot_daemon():
    """Ensure the daemon process is running and processing signals."""
    health = get_daemon_health()
    
    # If the daemon process is alive but idle, just send a START command
    if health["alive"]:
        if health["running"]:
            return True, "Daemon already running"
        sent = send_command("ACTION=START")
        if sent:
            return True, "Start command sent to daemon"
        return False, "Failed to send start command"
    
    # Spawn a new process
    logger.info(f"Starting daemon from: {DAEMON_SCRIPT}")
    logger.info(f"Project root: {PROJECT_ROOT}")
    
    # Verify the daemon script exists
    if not os.path.exists(DAEMON_SCRIPT):
        error_msg = f"Daemon script not found at: {DAEMON_SCRIPT}"
        logger.error(error_msg)
        return False, error_msg
    
    try:
        # Launch the daemon process
        process = subprocess.Popen(
            [sys.executable, DAEMON_SCRIPT],
            cwd=PROJECT_ROOT,
        )
        logger.info(f"Daemon process started with PID: {process.pid}")
        
        # Give it time to initialize
        time.sleep(2)
        
        # Verify the daemon is actually running
        health_check = get_daemon_health()
        if not health_check["alive"]:
            error_msg = f"Daemon failed to start: {health_check.get('error', 'Unknown error')}"
            logger.error(error_msg)
            return False, error_msg
        
        # Send START command to activate it
        if send_command("ACTION=START"):
            logger.info("Daemon launched and START command sent successfully")
            return True, "Daemon process launched successfully"
        else:
            logger.warning("Daemon launched but START command failed")
            return False, "Daemon launched but start command failed (please retry)"
            
    except FileNotFoundError as e:
        error_msg = f"Python executable or script not found: {e}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Failed to launch daemon: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False, error_msg

def send_command(cmd):
    """Write a command file for the daemon to pick up."""
    os.makedirs(os.path.dirname(COMMAND_FILE), exist_ok=True)
    try:
        with open(COMMAND_FILE, 'w') as f:
            f.write(cmd.strip() + "\n")
        return True
    except Exception as e:
        logger.error(f"Failed to write command '{cmd}': {e}")
        return False


def get_daemon_health():
    """Return detailed daemon health info including running state."""
    health = {
        "alive": False,
        "running": False,
        "pid": None,
        "last_update": None,
        "simulation_mode": True,
        "position_count": 0,
        "state": "UNKNOWN",
        "error": None,
        "status": {},
    }
    
    if not os.path.exists(STATUS_FILE):
        health["error"] = "Status file not found"
        return health
    
    try:
        with open(STATUS_FILE, 'r') as f:
            status = json.load(f)
            health["status"] = status
        
        pid = status.get('pid')
        if not pid:
            health["error"] = "No PID in status file"
            return health
        
        health["pid"] = pid
        
        # Check if process is alive
        try:
            os.kill(pid, 0)
            health["alive"] = True
        except (OSError, ProcessLookupError):
            health["error"] = f"Process {pid} not found"
            return health
        
        # Check heartbeat
        last_update = status.get('last_update')
        if last_update:
            try:
                last_update_str = last_update.rstrip('Z')
                dt = datetime.fromisoformat(last_update_str)
                elapsed = (datetime.utcnow() - dt).total_seconds()
                health["last_update"] = last_update
                
                if elapsed > DAEMON_STALE_THRESHOLD:
                    health["error"] = f"Heartbeat stale ({elapsed:.1f}s)"
                    return health
            except ValueError as e:
                health["error"] = f"Invalid timestamp: {e}"
                return health
        
        # Daemon is alive and healthy; check running state
        health["running"] = status.get("running", False)
        health["state"] = status.get("state", "UNKNOWN")
        health["simulation_mode"] = status.get("simulation_mode", True)
        health["position_count"] = status.get("position_count", 0)
        
        return health
        
    except Exception as e:
        health["error"] = str(e)
        logger.error(f"Error reading daemon health: {e}")
        return health


def get_bot_status():
    """Legacy helper for backwards compatibility."""
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

def get_trades():
    if os.path.exists(TRADES_FILE):
        try:
            return pd.read_csv(TRADES_FILE)
        except:
            pass
    return pd.DataFrame()

def calculate_stats(trades_df):
    if trades_df.empty:
        return {}
    
    total_trades = len(trades_df)
    trades_df['pnl'] = pd.to_numeric(trades_df['pnl'], errors='coerce').fillna(0)
    
    winning = trades_df[trades_df['pnl'] > 0]
    losing = trades_df[trades_df['pnl'] <= 0]
    
    n_win = len(winning)
    n_loss = len(losing)
    win_rate = (n_win / total_trades * 100) if total_trades > 0 else 0
    
    avg_win = winning['pnl'].mean() if n_win > 0 else 0
    avg_loss = losing['pnl'].mean() if n_loss > 0 else 0
    
    ratio = abs(avg_win / avg_loss) if avg_loss != 0 else (avg_win if avg_win > 0 else 0)
    
    total_pnl = trades_df['pnl'].sum()
    
    trades_df['equity'] = trades_df['pnl'].cumsum()
    trades_df['peak'] = trades_df['equity'].cummax()
    trades_df['drawdown'] = trades_df['equity'] - trades_df['peak']
    max_dd = trades_df['drawdown'].min() if not trades_df.empty else 0
    
    gross_profit = winning['pnl'].sum()
    gross_loss = abs(losing['pnl'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else gross_profit
    
    return {
        "total_trades": total_trades,
        "n_win": n_win,
        "n_loss": n_loss,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "ratio": ratio,
        "total_pnl": total_pnl,
        "max_dd": max_dd,
        "profit_factor": profit_factor
    }

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

# -- Services --
@st.cache_resource
def get_market_service(api_key, api_secret):
    logger.info("Initializing MarketDataService...")
    return MarketDataService(
        api_key=api_key, 
        api_secret=api_secret, 
        symbol="BTCUSDT", 
        timeframes=["1h", "4h", "1d"],
        selected_timeframe="1h"
    )

# -- UI Render Functions --

def render_dashboard(service, selected_symbol, primary_timeframe):
    logger.info("  -> Entering render_dashboard")
    try:
        # 1. Header Section
        logger.info("  -> Creating columns for header")
        col_status, col_ticker, col_ob_mini = st.columns([1, 2, 2])
        
        logger.info("  -> Fetching service data")
        data = service.get_data()
        logger.info("  -> Service data fetched")
        
        with col_status:
            logger.info("  -> Rendering Status Column")
            st.subheader("Bot Status")
            st.metric("Status", data['status'])
            st.metric("Updates", data['update_count'])
            if data['error']:
                st.error(f"Error: {data['error']}")
        
        with col_ticker:
            logger.info("  -> Rendering Ticker Column")
            st.subheader("Live Ticker")
            df = data.get("price_history", pd.DataFrame())
            if not df.empty:
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                price_change = latest['close'] - prev['close']
                pct_change = (price_change / prev['close']) * 100
                vol_24h = df['volume'].sum() 
                
                st.metric(selected_symbol, f"{latest['close']:.2f}", f"{price_change:.2f} ({pct_change:.2f}%)")
                
                t1, t2, t3 = st.columns(3)
                t1.metric("Vol 24h", f"{vol_24h:.0f}")
                t2.metric("High 24h", f"{df['high'].max():.2f}")
                t3.metric("Low 24h", f"{df['low'].min():.2f}")
                
        with col_ob_mini:
            logger.info("  -> Rendering OB Mini Column")
            st.subheader("Order Book (Mini)")
            ob = data.get("orderbook", {})
            if ob:
                bids = pd.DataFrame(ob.get('bids', []), columns=['Price', 'Size'])
                asks = pd.DataFrame(ob.get('asks', []), columns=['Price', 'Size'])
                
                if not bids.empty and not asks.empty:
                    bids['Price'] = pd.to_numeric(bids['Price'])
                    bids['Size'] = pd.to_numeric(bids['Size'])
                    asks['Price'] = pd.to_numeric(asks['Price'])
                    asks['Size'] = pd.to_numeric(asks['Size'])
                    
                    c_ask, c_bid = st.columns(2)
                    with c_ask:
                        st.caption("Asks")
                        st.dataframe(asks.head(5).style.format({'Price': '{:.2f}', 'Size': '{:.3f}'}), hide_index=True)
                    with c_bid:
                        st.caption("Bids")
                        st.dataframe(bids.head(5).style.format({'Price': '{:.2f}', 'Size': '{:.3f}'}), hide_index=True)
            else:
                st.caption("No OB data")

        st.markdown("---")

        # 2. Position Panel
        logger.info("  -> Rendering Position Panel")
        st.subheader("Active Position")
        positions = get_positions()
        
        if positions:
            pos = positions[0]
            symbol = pos.get('symbol', selected_symbol)
            side = pos.get('side', 'Long')
            entry_price = float(pos.get('avgPrice', 0))
            current_price = float(pos.get('markPrice', 0))
            size = float(pos.get('size', 0))
            pnl = float(pos.get('unrealisedPnl', 0))
            
            position_value = size * entry_price
            pnl_pct = (pnl / position_value * 100) if position_value > 0 else 0
            
            sl_price = float(pos.get('stopLoss', 0))
            tp_price = float(pos.get('takeProfit', 0))
            
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Pair", symbol)
            p1.metric("Direction", side, delta="LONG" if side=="Buy" else "SHORT")
            
            p2.metric("Entry Price", f"{entry_price:.2f}")
            p2.metric("Current Price", f"{current_price:.2f}")
            
            p3.metric("PnL (USDT)", f"{pnl:.2f}", delta_color="normal")
            p3.metric("PnL %", f"{pnl_pct:.2f}%")
            
            p4.metric("Size", f"{size} BTC")
            p4.metric("Value", f"${position_value:.2f}")

            # Visualization
            if sl_price == 0: sl_price = entry_price * 0.99 
            if tp_price == 0: tp_price = entry_price * 1.03 
            
            tp1_p = tp_price
            tp2_p = entry_price + (tp_price - entry_price) * 2 
            tp3_p = entry_price + (tp_price - entry_price) * 3 
            
            min_val = min(sl_price, current_price, entry_price) * 0.999
            max_val = max(tp3_p, current_price, entry_price) * 1.001
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=[sl_price, tp3_p], y=[0, 0],
                mode='lines', line=dict(color='gray', width=10),
                showlegend=False
            ))
            
            fig.add_trace(go.Scatter(
                x=[current_price], y=[0],
                mode='markers', marker=dict(size=20, color='blue', symbol='line-ns-open'),
                name='Current'
            ))
            
            fig.add_trace(go.Scatter(
                x=[entry_price], y=[0],
                mode='markers', marker=dict(size=15, color='white', symbol='line-ns'),
                name='Entry'
            ))
            
            fig.add_trace(go.Scatter(
                x=[sl_price], y=[0],
                mode='markers', marker=dict(size=15, color='red', symbol='line-ns'),
                name='SL'
            ))
            
            fig.add_trace(go.Scatter(
                x=[tp1_p, tp2_p, tp3_p], y=[0, 0, 0],
                mode='markers', marker=dict(size=15, color='green', symbol='line-ns'),
                name='TP Targets'
            ))
            
            fig.update_layout(
                height=100, 
                xaxis=dict(range=[min_val, max_val], title="Price"),
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                margin=dict(l=20, r=20, t=30, b=20),
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True, key=f"pos_viz_{symbol}")
            
            if st.button("CLOSE POSITION", type="primary"):
                if send_command(f"ACTION=CLOSE_ALL\nPAIR={symbol}"):
                    st.success("Close command sent!")
                else:
                    st.error("Failed to send close command")
                
        else:
            st.info("No active positions")

        st.markdown("---")

        # 3. Charts
        logger.info("  -> Rendering Charts")
        c1, c2 = st.columns([3, 1])
        
        with c1:
            st.subheader("Price History")
            if not df.empty:
                risk_metrics = data.get("risk_metrics", {})
                render_tradingview_chart(
                    df, 
                    active_risk=risk_metrics, 
                    height=500,
                    key=f"chart_{primary_timeframe}_{selected_symbol}"
                )
                
        with c2:
            st.subheader("Signal Details")
            signal = data.get("signal", {})
            if signal:
                    st.metric("Score", f"{signal.get('score', 0):.2f}")
                    st.metric("Action", signal.get('action', 'NEUTRAL'))
                    st.json(signal.get('details', {}), expanded=False)

        st.markdown("---")

        # 4. Stats & History
        logger.info("  -> Rendering Stats")
        st.subheader("Performance & History")
        
        trades = get_trades()
        stats = calculate_stats(trades)
        
        s1, s2, s3, s4 = st.columns(4)
        if stats:
            s1.metric("Win Rate", f"{stats['win_rate']:.1f}%", f"{stats['n_win']}W / {stats['n_loss']}L")
            s2.metric("Total PnL", f"${stats['total_pnl']:.2f}", f"PF: {stats['profit_factor']:.2f}")
            s3.metric("Avg Trade", f"${stats['avg_win']:.2f} / ${stats['avg_loss']:.2f}", f"Ratio: {stats['ratio']:.2f}")
            s4.metric("Max Drawdown", f"${stats['max_dd']:.2f}")
        
        if not trades.empty:
            st.dataframe(
                trades.sort_index(ascending=False).head(10).style.map(
                    lambda x: 'color: green' if x > 0 else 'color: red', subset=['pnl']
                ),
                use_container_width=True
            )
            
            csv = trades.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download CSV",
                csv,
                "trades.csv",
                "text/csv",
                key='download-csv'
            )
            
    except Exception as e:
        logger.error(f"Error in render_dashboard: {e}")
        logger.error(traceback.format_exc())
        st.error(f"Dashboard Error: {e}")

def render_backtest(service):
    logger.info("  -> Entering render_backtest")
    try:
        st.header("Backtest Lab 🧪")
        
        with st.expander("Backtest Settings", expanded=True):
            col1, col2 = st.columns(2)
            initial_capital = col1.number_input("Initial Capital", 1000, 100000, 10000)
            bt_symbol = col2.text_input("Symbol", "BTCUSDT", key="bt_symbol")
            
            days = st.slider("Days to Backtest", 1, 365, 30)
            
            if st.button("Run Backtest"):
                with st.spinner("Running backtest..."):
                    fetcher = service.fetcher
                    engine = BacktestEngine(fetcher, initial_capital=initial_capital)
                    
                    # We need active_timeframes from session state
                    timeframes = st.session_state.get("active_timeframes", ["1h", "4h", "1d"])

                    results = engine.run(
                        symbol=bt_symbol,
                        start_time=int((datetime.now() - timedelta(days=days)).timestamp() * 1000),
                        end_time=int(datetime.now().timestamp() * 1000),
                        timeframes=timeframes
                    )
                    
                    st.success("Backtest Complete!")
                    
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total Return", f"{results['total_return_pct']:.2f}%")
                    m2.metric("Win Rate", f"{results['win_rate']:.1f}%")
                    m3.metric("Profit Factor", f"{results['profit_factor']:.2f}")
                    m4.metric("Max Drawdown", f"{results['max_drawdown_pct']:.2f}%")
                    
                    equity_df = pd.DataFrame(results['equity_curve'], columns=['time', 'equity'])
                    equity_df['time'] = pd.to_datetime(equity_df['time'], unit='ms')
                    st.line_chart(equity_df.set_index('time')['equity'])
                    
                    trades_df = pd.DataFrame(results['trades'])
                    if not trades_df.empty:
                        st.subheader("Trade History")
                        st.dataframe(trades_df)
    except Exception as e:
        logger.error(f"Error in render_backtest: {e}")
        logger.error(traceback.format_exc())
        st.error(f"Backtest Error: {e}")

def render_debug_section(service):
    st.header("🔧 Signal Debug")
    
    st.subheader("1. Simulation Parameters")
    c1, c2 = st.columns(2)
    score_input = c1.number_input("Simulated Score", 0.0, 1.0, 0.68, 0.01)
    threshold_input = c2.number_input("Threshold", 0.0, 1.0, 0.60, 0.01)
    
    action = "BUY" if score_input > threshold_input else "NEUTRAL"
    st.info(f"Signal: {action} (Score: {score_input:.2f})")
    
    if st.button("Manually Open Test Position (Simulation)"):
        st.write("---")
        st.write("### Execution Log")
        
        # 1. Signal
        st.write(f"1. **Signal Generation**: {action} detected.")
        if action == "NEUTRAL":
            st.warning("Score below threshold. No action.")
        else:
            # 2. Market Data
            st.write("2. **Fetching Market Data**...")
            try:
                # We use the service's fetcher
                df = service.fetcher.fetch_history(service.symbol, "1h", limit=100)
                if df.empty:
                    st.error("Failed to fetch market data (Empty DataFrame)")
                    return

                current_close = float(df.iloc[-1]['close'])
                volume_24h = float(df['volume'].sum())
                
                # ATR calc
                try:
                    import pandas_ta as ta
                    atr_series = df.ta.atr(length=14)
                    atr = float(atr_series.iloc[-1])
                except:
                    atr = float((df['high'] - df['low']).mean())
                    
                st.success(f"Market Data: Price={current_close}, Vol24h={volume_24h:.2f}, ATR={atr:.4f}")
                
                market_data = {
                    "volume_24h": volume_24h,
                    "atr": atr,
                    "close": current_close
                }
                
                # 3. Risk Check
                st.write("3. **Risk Management Check**...")
                
                risk_service = RiskService()
                
                amount = getattr(settings, 'risk_limit_amount', 1000.0)
                st.write(f"Checking for amount: ${amount}")
                
                order_params = {"amount": amount, "symbol": service.symbol}
                allowed, reason = risk_service.validate_order(order_params, market_data)
                
                if allowed:
                    st.success("✅ Risk Check PASSED")
                    st.write("In a real run, position would be opened now.")
                    
                    cmd = f"""ACTION={action}
PAIR={service.symbol}
SCORE={score_input:.2f}
TIMESTAMP={datetime.utcnow().isoformat()}Z"""
                    if send_command(cmd):
                        st.info(f"Signal sent to daemon:\n{cmd}")
                    else:
                        st.error("Failed to send signal to daemon")
                else:
                    st.error(f"❌ Risk Check FAILED: {reason}")
            except Exception as e:
                st.error(f"Error during simulation: {e}")
                st.code(traceback.format_exc())
            
    st.markdown("---")
    st.subheader("System Logs")
    if st.button("Refresh Logs"):
        pass
    
    logs = get_logs(20)
    log_text = "".join(logs)
    st.text_area("Daemon Logs", log_text, height=300)

def render_settings():
    st.header("Settings")
    st.write("Settings are available in the sidebar.")
    st.info("Detailed settings configuration is located in the sidebar to allow adjustments while viewing the dashboard.")

def render_ui(service, selected_symbol, primary_timeframe):
    logger.info("Starting render_ui")
    try:
        logger.info("Rendering Main Title")
        st.title("Trading Bot Dashboard")
        
        logger.info("Creating Tabs")
        tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Backtest", "Settings", "Debug"])
        
        with tab1:
            logger.info("Rendering Tab 1: Dashboard")
            render_dashboard(service, selected_symbol, primary_timeframe)
            
        with tab2:
            logger.info("Rendering Tab 2: Backtest")
            render_backtest(service)
            
        with tab3:
            logger.info("Rendering Tab 3: Settings")
            render_settings()

        with tab4:
            logger.info("Rendering Tab 4: Debug")
            render_debug_section(service)
            
    except Exception as e:
        logger.error(f"Critical Error in render_ui: {e}")
        logger.error(traceback.format_exc())
        st.error(f"UI Rendering Error: {e}")

def main():
    try:
        # 1. Set Page Config (Must be first Streamlit command)
        st.set_page_config(page_title="Trading Bot Dashboard", layout="wide", page_icon="📈")
        logger.info("Page config set")
        
        # Initialize session state variables
        if "selected_timeframe" not in st.session_state:
            st.session_state.selected_timeframe = "1h"
        if "selected_pair" not in st.session_state:
            st.session_state.selected_pair = "BTCUSDT"
        if "active_timeframes" not in st.session_state:
            st.session_state.active_timeframes = ["1h", "4h", "1d"]

        print("1. Loading settings...")
        logger.info("Loading settings...")
        
        print("2. Initializing session state...")
        logger.info("Initializing session state...")

        # -- Secrets & Config --
        try:
            BYBIT_API_KEY = st.secrets["bybit"]["api_key"]
            BYBIT_API_SECRET = st.secrets["bybit"]["api_secret"]
        except:
            logger.warning("Secrets not found, falling back to settings")
            BYBIT_API_KEY = settings.api_key
            BYBIT_API_SECRET = settings.api_secret

        if not BYBIT_API_KEY:
            st.sidebar.warning("No API Key found. Using public endpoints only where possible.")
        
        print("3. Loading market service...")
        logger.info("Loading market service...")
        
        service = get_market_service(BYBIT_API_KEY, BYBIT_API_SECRET)
        logger.info("Market Service Loaded")

        # -- Sidebar Controls --
        st.sidebar.title("🤖 Bot Control")
        # Radio removed, using Tabs in main area
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("Settings")
        selected_symbol = st.sidebar.text_input("Symbol", value="BTCUSDT", key="selected_pair")

        # Timeframe Selector
        available_timeframes = ["5m", "15m", "30m", "1h", "3h", "4h", "1d", "1week"]
        
        selected_timeframes = st.sidebar.multiselect(
            "Active Timeframes (MTF)",
            available_timeframes,
            default=st.session_state.active_timeframes,
            key="timeframe_selector"
        )
        st.session_state.active_timeframes = selected_timeframes

        # Primary Timeframe Selector
        try:
            tf_index = available_timeframes.index(st.session_state.selected_timeframe)
        except ValueError:
            tf_index = 3 # Default to 1h
            
        primary_timeframe = st.sidebar.selectbox(
            "Primary Timeframe", 
            available_timeframes, 
            index=tf_index,
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

        # -- Daemon Control --
        st.sidebar.markdown("---")
        st.sidebar.subheader("Daemon Control")
        
        health = get_daemon_health()
        daemon_running = health["running"]
        daemon_alive = health["alive"]
        
        # Display daemon status
        if daemon_alive and daemon_running:
            status_text = f"✅ **Running** (PID: {health['pid']})"
            if health.get("simulation_mode"):
                status_text += " [SIM]"
            st.sidebar.success(status_text)
            
            if health.get("position_count", 0) > 0:
                st.sidebar.info(f"📊 {health['position_count']} active position(s)")
            
            if st.sidebar.button("Stop Bot"):
                if send_command("ACTION=STOP"):
                    st.sidebar.info("Stop command sent")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.sidebar.error("Failed to send stop command")
                    
        elif daemon_alive and not daemon_running:
            st.sidebar.warning(f"⏸️ **Idle** (PID: {health['pid']})")
            if st.sidebar.button("Start Bot"):
                if send_command("ACTION=START"):
                    st.sidebar.info("Start command sent")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.sidebar.error("Failed to send start command")
        else:
            st.sidebar.error("❌ **Daemon Not Running**")
            if health.get("error"):
                st.sidebar.caption(f"Error: {health['error']}")
            
            if st.sidebar.button("Start Daemon"):
                success, message = start_bot_daemon()
                if success:
                    st.sidebar.success(message)
                else:
                    st.sidebar.error(message)
                time.sleep(2)
                st.rerun()

        # -- Main UI --
        render_ui(service, selected_symbol, primary_timeframe)

    except Exception as e:
        logger.critical(f"Critical error in main: {e}")
        logger.critical(traceback.format_exc())
        st.error(f"Application Error: {e}")
        st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
