import streamlit as st
import pandas as pd
import numpy as np
from trading_bot.config import settings

st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")

st.title("Trading Bot Dashboard")

st.sidebar.header("Configuration")
st.sidebar.text(f"Exchange: {settings.exchange_id}")
st.sidebar.text(f"Risk Limit: {settings.risk_limit_amount}")

st.header("Market Data")
st.write("Placeholder for real-time market data")

# Example chart
chart_data = pd.DataFrame(
    np.random.randn(20, 3),
    columns=['a', 'b', 'c'])

st.line_chart(chart_data)

st.header("Active Orders")
st.write("No active orders.")

st.header("Logs")
st.text("Log stream placeholder...")
