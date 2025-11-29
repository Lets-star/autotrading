import streamlit as st
import pandas as pd
import numpy as np
from trading_bot.config import settings
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.data_feeds.market_data_service import MarketDataService
import time

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

# Global settings for config only


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

# Update service settings if changed
if service.symbol != selected_symbol:
    service.symbol = selected_symbol
    
if service.timeframes != selected_timeframes:
    service.timeframes = selected_timeframes
    service.scoring.active_timeframes = selected_timeframes

if service.selected_timeframe != primary_timeframe:
    service.selected_timeframe = primary_timeframe

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
                            score_color = ":green" if row['Score'] > 0 else ":red" if row['Score'] < 0 else ":grey"
                            st.markdown(f"**{row['Name']}**")
                            st.markdown(f"Score: {score_color}[{row['Score']:.2f}] | W: {row['Weight']:.1f}")
                            st.progress(max(0.0, min(1.0, abs(row['Score']))))
                            st.divider()

            with st.expander("Show Details (Logs & Metadata)"):
                st.json(details)

    else:
        st.warning("Waiting for data...")
    
    # 2. Charts & Order Book
    st.markdown("---")
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("Price History")
        if not df.empty:
            st.line_chart(df.set_index("timestamp")["close"])
            
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
        
    # Auto-refresh at the end
    if auto_refresh:
        time.sleep(1)
        st.rerun()

elif mode == "Backtest Lab":
    st.title("Backtest Lab")
    
    with st.expander("Configuration", expanded=True):
        with st.form("bt_form"):
            c1, c2, c3, c4 = st.columns(4)
            bt_symbol = c1.text_input("Symbol", selected_symbol)
            
            bt_opts = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
            def_idx = bt_opts.index(primary_timeframe) if primary_timeframe in bt_opts else 4
            
            bt_interval = c2.selectbox("Interval", bt_opts, index=def_idx)
            bt_limit = c3.slider("History Length (Candles)", 100, 1000, 500)
            debug_mode = c4.checkbox("Show Debug Logs", value=False)
            
            run_bt = st.form_submit_button("Run Simulation")
            
    if run_bt:
        with st.spinner(f"Backtesting {bt_symbol} on {bt_interval}..."):
            engine = BacktestEngine(
                api_key=BYBIT_API_KEY, 
                api_secret=BYBIT_API_SECRET,
                active_timeframes=st.session_state.active_timeframes
            )
            results = engine.run(bt_symbol, bt_interval, bt_limit, debug=debug_mode)
            
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

                # Debug Logs
                if debug_mode:
                    st.subheader("Backtest Debug Logs")
                    logs = results.get('debug_logs', [])
                    if logs:
                        st.text_area("Detailed Logs", "\n".join(logs), height=300)
                    else:
                        st.info("No debug logs generated.")
