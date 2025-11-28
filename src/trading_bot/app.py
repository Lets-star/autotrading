import streamlit as st
import pandas as pd
import numpy as np
from trading_bot.config import settings
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.data_feeds.bybit_fetcher import BybitDataFetcher
from trading_bot.scoring.service import ScoringService
import time

st.set_page_config(page_title="Trading Bot Dashboard", layout="wide", page_icon="📈")

# -- Secrets & Config --
# Try to load from st.secrets, fallback to env vars (settings)
try:
    BYBIT_API_KEY = st.secrets["bybit"]["api_key"]
    BYBIT_API_SECRET = st.secrets["bybit"]["api_secret"]
except:
    BYBIT_API_KEY = settings.api_key
    BYBIT_API_SECRET = settings.api_secret

if not BYBIT_API_KEY:
    st.sidebar.warning("No API Key found. Using public endpoints only where possible.")

# -- Sidebar Controls --
st.sidebar.title("🤖 Bot Control")
mode = st.sidebar.radio("Operation Mode", ["Live Dashboard", "Backtest Lab"])

st.sidebar.markdown("---")
st.sidebar.subheader("Settings")
selected_symbol = st.sidebar.text_input("Symbol", "BTCUSDT")

# Timeframe Selector
if "active_timeframes" not in st.session_state:
    st.session_state.active_timeframes = ["1h", "4h", "1d"]

available_timeframes = ["5m", "15m", "30m", "1h", "3h", "4h", "1d", "1week"]
selected_timeframes = st.sidebar.multiselect(
    "Active Timeframes",
    available_timeframes,
    default=st.session_state.active_timeframes,
    key="timeframe_selector"
)
st.session_state.active_timeframes = selected_timeframes

# Update global settings (for this process)
settings.active_timeframes = selected_timeframes

# -- Services --
# Initialize services
fetcher = BybitDataFetcher(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
scoring = ScoringService(active_timeframes=selected_timeframes)

if mode == "Live Dashboard":
    st.title(f"Live Dashboard: {selected_symbol}")
    
    # Auto-refresh logic (basic)
    if st.sidebar.checkbox("Auto-refresh (15s)", value=False):
        time.sleep(15)
        st.rerun()

    # 1. Top Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    
    # Fetch latest data
    df = fetcher.fetch_history(selected_symbol, "1m", limit=50)
    
    if not df.empty:
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price_change = latest['close'] - prev['close']
        
        # Fetch MTF data for scoring
        mtf_data = {}
        for tf in selected_timeframes:
             # Fetch a small limit, we just need latest for current signal
             tf_df = fetcher.fetch_history(selected_symbol, tf, limit=50)
             if not tf_df.empty:
                 mtf_data[tf] = tf_df

        # Calculate Score
        signal = scoring.calculate_signals(df, mtf_data=mtf_data)
        
        col1.metric("Price", f"{latest['close']:.2f}", f"{price_change:.2f}")
        col2.metric("Composite Score", f"{signal['score']:.2f}", delta_color="off")
        col3.metric("Action", signal['action'], delta_color="normal")
        col4.metric("Risk Status", "Normal", "0.0%")
    else:
        st.error("Failed to fetch market data.")
    
    # 2. Charts & Order Book
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("Price History")
        if not df.empty:
            st.line_chart(df.set_index("timestamp")["close"])
            
    with c2:
        st.subheader("Order Book")
        ob = fetcher.fetch_orderbook(selected_symbol)
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
    # Mock data since we don't have a live DB connection in this scope
    st.info("No active positions (Mock)")
    
    st.subheader("System Logs")
    st.text_area("Log Output", "Bot started...\nConnected to Bybit...\nListening for signals...", height=100)
    
    # Bot Controls
    st.markdown("---")
    c_start, c_stop = st.columns(2)
    if c_start.button("🟢 Start Bot", use_container_width=True):
        st.success("Signal sent to start bot daemon.")
    if c_stop.button("🔴 Stop Bot", use_container_width=True):
        st.error("Signal sent to stop bot daemon.")

elif mode == "Backtest Lab":
    st.title("Backtest Lab")
    
    with st.expander("Configuration", expanded=True):
        with st.form("bt_form"):
            c1, c2, c3 = st.columns(3)
            bt_symbol = c1.text_input("Symbol", selected_symbol)
            bt_interval = c2.selectbox("Interval", ["1m", "5m", "15m", "30m", "1h", "4h", "1d"], index=4)
            bt_limit = c3.slider("History Length (Candles)", 100, 1000, 500)
            
            run_bt = st.form_submit_button("Run Simulation")
            
    if run_bt:
        with st.spinner(f"Backtesting {bt_symbol} on {bt_interval}..."):
            engine = BacktestEngine(
                api_key=BYBIT_API_KEY, 
                api_secret=BYBIT_API_SECRET,
                active_timeframes=st.session_state.active_timeframes
            )
            results = engine.run(bt_symbol, bt_interval, bt_limit)
            
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
