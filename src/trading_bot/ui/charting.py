import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

try:
    from streamlit_lightweight_charts import renderLightweightCharts
except ImportError:
    renderLightweightCharts = None

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate technical indicators for the chart:
    - MA 20, MA 50
    - Bollinger Bands (20, 2)
    - ATR Channels (SuperTrend)
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # Ensure close is float
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['open'] = df['open'].astype(float)
    df['volume'] = df['volume'].astype(float)
    
    # MA 20, 50
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA50'] = df['close'].rolling(window=50).mean()
    
    # Bollinger Bands (20, 2)
    std = df['close'].rolling(window=20).std()
    df['BB_upper'] = df['MA20'] + (std * 2)
    df['BB_lower'] = df['MA20'] - (std * 2)
    
    # ATR (14)
    # True Range
    c_shift = df['close'].shift()
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - c_shift).abs()
    tr3 = (df['low'] - c_shift).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # SuperTrend (ATR Channel / TSL)
    # Using period 10, multiplier 3.0
    period = 10
    multiplier = 3.0
    
    atr_st = tr.rolling(window=period).mean()
    
    hl2 = (df['high'] + df['low']) / 2
    basic_upper = hl2 + (multiplier * atr_st)
    basic_lower = hl2 - (multiplier * atr_st)
    
    # Initialize columns
    df['ST_upper'] = np.nan
    df['ST_lower'] = np.nan
    df['ST_trend'] = 0 # 1: Up, -1: Down
    
    # Convert to numpy arrays for loop performance
    close_arr = df['close'].values
    bu_arr = basic_upper.values
    bl_arr = basic_lower.values
    
    final_upper = np.zeros(len(df))
    final_lower = np.zeros(len(df))
    trend = np.zeros(len(df))
    
    # Initialize first values (skipping NaN)
    start_idx = period
    if len(df) > start_idx:
        final_upper[start_idx] = bu_arr[start_idx]
        final_lower[start_idx] = bl_arr[start_idx]
        trend[start_idx] = 1
        
        for i in range(start_idx + 1, len(df)):
            # Upper Band Logic
            if (bu_arr[i] < final_upper[i-1]) or (close_arr[i-1] > final_upper[i-1]):
                final_upper[i] = bu_arr[i]
            else:
                final_upper[i] = final_upper[i-1]
                
            # Lower Band Logic
            if (bl_arr[i] > final_lower[i-1]) or (close_arr[i-1] < final_lower[i-1]):
                final_lower[i] = bl_arr[i]
            else:
                final_lower[i] = final_lower[i-1]
                
            # Trend Logic
            prev_trend = trend[i-1]
            if prev_trend == 1:
                if close_arr[i] <= final_lower[i]:
                    trend[i] = -1
                else:
                    trend[i] = 1
            else: # prev_trend == -1 or 0
                if close_arr[i] >= final_upper[i]:
                    trend[i] = 1
                else:
                    trend[i] = -1
                    
        df['ST_upper'] = final_upper
        df['ST_lower'] = final_lower
        df['ST_trend'] = trend
    
    return df

def plot_candle_chart(df: pd.DataFrame, trades: Optional[List[Dict]] = None, active_risk: Optional[Dict] = None, height: int = 600, title: str = "Price History") -> go.Figure:
    """
    Create a Plotly candlestick chart with indicators and optional trade markers.
    Deprecated in favor of render_tradingview_chart for UI, but kept for fallback/reports.
    """
    if df.empty:
        return go.Figure()
        
    df = calculate_indicators(df)
    
    # Main Chart (Candles + Indicators)
    fig = go.Figure()
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='OHLC'
    ))
    
    # MAs
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MA20'], line=dict(color='orange', width=1), name='MA 20'))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MA50'], line=dict(color='blue', width=1), name='MA 50'))
    
    # Bollinger Bands
    # Upper
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['BB_upper'], 
        line=dict(color='rgba(128,128,128,0.5)', width=1, dash='dot'), 
        name='BB Upper', showlegend=False
    ))
    # Lower
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['BB_lower'], 
        line=dict(color='rgba(128,128,128,0.5)', width=1, dash='dot'), 
        fill='tonexty', fillcolor='rgba(128,128,128,0.1)',
        name='Bollinger Bands'
    ))
    
    # SuperTrend (ATR Channels)
    # Plot TrendUp (Green Line) where trend is 1
    # Plot TrendDown (Red Line) where trend is -1
    
    st_up = df.copy()
    st_up.loc[st_up['ST_trend'] != 1, 'ST_lower'] = np.nan
    
    st_down = df.copy()
    st_down.loc[st_down['ST_trend'] != -1, 'ST_upper'] = np.nan
    
    fig.add_trace(go.Scatter(
        x=st_up['timestamp'], y=st_up['ST_lower'], 
        line=dict(color='green', width=2), name='SuperTrend Up'
    ))
    
    fig.add_trace(go.Scatter(
        x=st_down['timestamp'], y=st_down['ST_upper'], 
        line=dict(color='red', width=2), name='SuperTrend Down'
    ))

    # Add Trades if provided
    if trades:
        long_entries = []
        short_entries = []
        long_exits = []
        short_exits = []
        
        for t in trades:
            if t['type'] == 'LONG':
                long_entries.append({'t': t['entry_time'], 'p': t['entry_price']})
                long_exits.append({'t': t['exit_time'], 'p': t['exit_price'], 'pnl': t['pnl']})
            else:
                short_entries.append({'t': t['entry_time'], 'p': t['entry_price']})
                short_exits.append({'t': t['exit_time'], 'p': t['exit_price'], 'pnl': t['pnl']})
        
        if long_entries:
            le_df = pd.DataFrame(long_entries)
            fig.add_trace(go.Scatter(
                x=le_df['t'], y=le_df['p'],
                mode='markers', marker=dict(symbol='triangle-up', size=12, color='green', line=dict(width=1, color='black')),
                name='Long Entry'
            ))
            
        if short_entries:
            se_df = pd.DataFrame(short_entries)
            fig.add_trace(go.Scatter(
                x=se_df['t'], y=se_df['p'],
                mode='markers', marker=dict(symbol='triangle-down', size=12, color='red', line=dict(width=1, color='black')),
                name='Short Entry'
            ))
            
        if long_exits:
            lx_df = pd.DataFrame(long_exits)
            fig.add_trace(go.Scatter(
                x=lx_df['t'], y=lx_df['p'],
                mode='markers', marker=dict(symbol='x', size=8, color='black'),
                name='Long Exit',
                hovertext=[f"PnL: {x['pnl']:.2f}" for x in long_exits]
            ))
            
        if short_exits:
            sx_df = pd.DataFrame(short_exits)
            fig.add_trace(go.Scatter(
                x=sx_df['t'], y=sx_df['p'],
                mode='markers', marker=dict(symbol='x', size=8, color='black'),
                name='Short Exit',
                hovertext=[f"PnL: {x['pnl']:.2f}" for x in short_exits]
            ))
            
    # Active Risk Levels (TP/SL) for Live Dashboard
    if active_risk:
        if 'sl' in active_risk:
            fig.add_hline(y=active_risk['sl'], line_dash="dash", line_color="red", annotation_text="SL", annotation_position="top right")
        if 'tp' in active_risk:
            fig.add_hline(y=active_risk['tp'], line_dash="dash", line_color="green", annotation_text="TP", annotation_position="bottom right")
    
    # Layout adjustments
    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False, 
        height=height,
        hovermode='x unified',
        template='plotly_dark', 
        margin=dict(l=10, r=10, t=30, b=10)
    )
    
    return fig

def plot_volume_chart(df: pd.DataFrame, height: int = 200) -> go.Figure:
    """
    Create a separate Plotly volume chart.
    """
    if df.empty:
        return go.Figure()

    # Ensure float
    df = df.copy()
    df['open'] = df['open'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)

    fig = go.Figure()

    # Color volume bars based on price change
    colors = ['green' if r['close'] >= r['open'] else 'red' for i, r in df.iterrows()]
    fig.add_trace(go.Bar(
        x=df['timestamp'], y=df['volume'], 
        marker_color=colors, name='Volume'
    ))

    fig.update_layout(
        title="Volume",
        height=height,
        hovermode='x unified',
        template='plotly_dark',
        margin=dict(l=10, r=10, t=30, b=10),
        yaxis=dict(title='Volume')
    )
    
    return fig

def render_tradingview_chart(df: pd.DataFrame, trades: Optional[List[Dict]] = None, active_risk: Optional[Dict] = None, height: int = 500):
    """
    Render a TradingView-like chart using streamlit-lightweight-charts.
    """
    import streamlit as st
    
    if df.empty:
        st.warning("No data to display.")
        return

    if renderLightweightCharts is None:
        st.error("Lightweight Charts library not found. Falling back to Plotly.")
        # Fallback to plotly if not installed (though we should have it)
        fig = plot_candle_chart(df, trades, active_risk, height)
        st.plotly_chart(fig, use_container_width=True)
        return

    df = calculate_indicators(df)
    
    # Timestamp handling: ensure unix seconds
    if pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['time'] = df['timestamp'].astype(np.int64) // 10**9
    else:
        df['time'] = pd.to_datetime(df['timestamp']).astype(np.int64) // 10**9

    # 1. Candlestick Series
    candle_data = df[['time', 'open', 'high', 'low', 'close']].to_dict('records')
    
    # 2. Volume Series
    vol_df = df[['time', 'volume', 'open', 'close']].copy()
    vol_df['color'] = np.where(vol_df['close'] >= vol_df['open'], '#26a69a', '#ef5350')
    vol_df = vol_df.rename(columns={'volume': 'value'})
    volume_data = vol_df[['time', 'value', 'color']].to_dict('records')
    
    # 3. Indicators
    ma20_data = df[['time', 'MA20']].dropna().rename(columns={'MA20': 'value'}).to_dict('records')
    ma50_data = df[['time', 'MA50']].dropna().rename(columns={'MA50': 'value'}).to_dict('records')
    
    bb_upper = df[['time', 'BB_upper']].dropna().rename(columns={'BB_upper': 'value'}).to_dict('records')
    bb_lower = df[['time', 'BB_lower']].dropna().rename(columns={'BB_lower': 'value'}).to_dict('records')
    
    st_up = df[df['ST_trend'] == 1][['time', 'ST_lower']].dropna().rename(columns={'ST_lower': 'value'}).to_dict('records')
    st_down = df[df['ST_trend'] == -1][['time', 'ST_upper']].dropna().rename(columns={'ST_upper': 'value'}).to_dict('records')

    # Markers
    markers = []
    if trades:
        for t in trades:
            try:
                entry_ts = int(pd.to_datetime(t['entry_time']).timestamp())
                exit_ts = int(pd.to_datetime(t['exit_time']).timestamp())
            except:
                continue
                
            markers.append({
                "time": entry_ts,
                "position": "belowBar" if t['type'] == 'LONG' else "aboveBar",
                "color": "#2196F3" if t['type'] == 'LONG' else "#E91E63",
                "shape": "arrowUp" if t['type'] == 'LONG' else "arrowDown",
                "text": "L" if t['type'] == 'LONG' else "S"
            })
            
            markers.append({
                "time": exit_ts,
                "position": "aboveBar" if t['type'] == 'LONG' else "belowBar",
                "color": "#2196F3" if t['type'] == 'LONG' else "#E91E63",
                "shape": "arrowDown" if t['type'] == 'LONG' else "arrowUp",
                "text": f"{t['pnl']:.1f}"
            })

    # Options
    chartOptions = {
        "layout": {
            "textColor": '#d1d4dc',
            "background": {
                "type": 'solid',
                "color": '#131722'
            }
        },
        "grid": {
            "vertLines": {"color": "rgba(42, 46, 57, 0.5)"},
            "horzLines": {"color": "rgba(42, 46, 57, 0.5)"}
        },
        "height": height,
        "rightPriceScale": {
            "scaleMargins": {
                "top": 0.2, 
                "bottom": 0.2, 
            },
        },
        "timeScale": {
            "timeVisible": True,
            "secondsVisible": False
        },
        "crosshair": {
            "mode": 1
        }
    }
    
    series = [
        {
            "type": 'Candlestick',
            "data": candle_data,
            "options": {
                "upColor": '#26a69a',
                "downColor": '#ef5350',
                "borderVisible": False,
                "wickUpColor": '#26a69a',
                "wickDownColor": '#ef5350'
            },
            "markers": markers
        },
        {
            "type": 'Histogram',
            "data": volume_data,
            "options": {
                "priceFormat": {"type": 'volume'},
                "priceScaleId": '', # Overlay
                "scaleMargins": {
                    "top": 0.8, # Push to bottom
                    "bottom": 0,
                }
            }
        },
        {
            "type": 'Line',
            "data": ma20_data,
            "options": {"color": '#ff9800', "lineWidth": 1, "title": "MA20"}
        },
        {
            "type": 'Line',
            "data": ma50_data,
            "options": {"color": '#2196f3', "lineWidth": 1, "title": "MA50"}
        },
        {
             "type": 'Line',
             "data": bb_upper,
             "options": {"color": 'rgba(43, 255, 255, 0.25)', "lineWidth": 1}
        },
        {
             "type": 'Line',
             "data": bb_lower,
             "options": {"color": 'rgba(43, 255, 255, 0.25)', "lineWidth": 1}
        },
        {
             "type": 'Line',
             "data": st_up,
             "options": {"color": '#00e676', "lineWidth": 2, "title": "SuperTrend"}
        },
        {
             "type": 'Line',
             "data": st_down,
             "options": {"color": '#ff5252', "lineWidth": 2}
        }
    ]
    
    if active_risk:
         if 'sl' in active_risk:
             sl_data = [{"time": x["time"], "value": active_risk['sl']} for x in candle_data]
             series.append({
                 "type": 'Line',
                 "data": sl_data,
                 "options": {"color": '#ff1744', "lineStyle": 2, "lineWidth": 1, "title": "SL"}
             })
         if 'tp' in active_risk:
             tp_data = [{"time": x["time"], "value": active_risk['tp']} for x in candle_data]
             series.append({
                 "type": 'Line',
                 "data": tp_data,
                 "options": {"color": '#00e676', "lineStyle": 2, "lineWidth": 1, "title": "TP"}
             })

    renderLightweightCharts(chartOptions, series)
