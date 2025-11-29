import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

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
    """
    if df.empty:
        return go.Figure()
        
    df = calculate_indicators(df)
    
    # Create subplots: 1. Main Chart (Candles + Indicators), 2. Volume
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.05, 
        subplot_titles=(title, 'Volume'),
        row_heights=[0.8, 0.2]
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='OHLC'
    ), row=1, col=1)
    
    # MAs
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MA20'], line=dict(color='orange', width=1), name='MA 20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MA50'], line=dict(color='blue', width=1), name='MA 50'), row=1, col=1)
    
    # Bollinger Bands
    # Upper
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['BB_upper'], 
        line=dict(color='rgba(128,128,128,0.5)', width=1, dash='dot'), 
        name='BB Upper', showlegend=False
    ), row=1, col=1)
    # Lower
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['BB_lower'], 
        line=dict(color='rgba(128,128,128,0.5)', width=1, dash='dot'), 
        fill='tonexty', fillcolor='rgba(128,128,128,0.1)',
        name='Bollinger Bands'
    ), row=1, col=1)
    
    # SuperTrend (ATR Channels)
    # Plot TrendUp (Green Line) where trend is 1
    # Plot TrendDown (Red Line) where trend is -1
    # We can use masked arrays
    
    st_up = df.copy()
    st_up.loc[st_up['ST_trend'] != 1, 'ST_lower'] = np.nan
    
    st_down = df.copy()
    st_down.loc[st_down['ST_trend'] != -1, 'ST_upper'] = np.nan
    
    fig.add_trace(go.Scatter(
        x=st_up['timestamp'], y=st_up['ST_lower'], 
        line=dict(color='green', width=2), name='SuperTrend Up'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=st_down['timestamp'], y=st_down['ST_upper'], 
        line=dict(color='red', width=2), name='SuperTrend Down'
    ), row=1, col=1)

    # Volume
    # Color volume bars based on price change
    colors = ['green' if r['close'] >= r['open'] else 'red' for i, r in df.iterrows()]
    fig.add_trace(go.Bar(
        x=df['timestamp'], y=df['volume'], 
        marker_color=colors, name='Volume'
    ), row=2, col=1)
    
    # Add Trades if provided
    if trades:
        # Separate Long and Short Entries/Exits
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
        
        # Plot Entries
        if long_entries:
            le_df = pd.DataFrame(long_entries)
            fig.add_trace(go.Scatter(
                x=le_df['t'], y=le_df['p'],
                mode='markers', marker=dict(symbol='triangle-up', size=12, color='green', line=dict(width=1, color='black')),
                name='Long Entry'
            ), row=1, col=1)
            
        if short_entries:
            se_df = pd.DataFrame(short_entries)
            fig.add_trace(go.Scatter(
                x=se_df['t'], y=se_df['p'],
                mode='markers', marker=dict(symbol='triangle-down', size=12, color='red', line=dict(width=1, color='black')),
                name='Short Entry'
            ), row=1, col=1)
            
        # Plot Exits
        if long_exits:
            lx_df = pd.DataFrame(long_exits)
            # Differentiate profit/loss with symbol or color? 
            # Let's keep it simple: X for exit
            fig.add_trace(go.Scatter(
                x=lx_df['t'], y=lx_df['p'],
                mode='markers', marker=dict(symbol='x', size=8, color='black'),
                name='Long Exit',
                hovertext=[f"PnL: {x['pnl']:.2f}" for x in long_exits]
            ), row=1, col=1)
            
        if short_exits:
            sx_df = pd.DataFrame(short_exits)
            fig.add_trace(go.Scatter(
                x=sx_df['t'], y=sx_df['p'],
                mode='markers', marker=dict(symbol='x', size=8, color='black'),
                name='Short Exit',
                hovertext=[f"PnL: {x['pnl']:.2f}" for x in short_exits]
            ), row=1, col=1)
            
    # Active Risk Levels (TP/SL) for Live Dashboard
    if active_risk:
        current_time = df['timestamp'].iloc[-1]
        # Extend line a bit back or across whole chart? 
        # Usually horizontal line across recent history or whole chart is fine.
        
        if 'sl' in active_risk:
            fig.add_hline(y=active_risk['sl'], line_dash="dash", line_color="red", annotation_text="SL", annotation_position="top right")
        if 'tp' in active_risk:
            fig.add_hline(y=active_risk['tp'], line_dash="dash", line_color="green", annotation_text="TP", annotation_position="bottom right")
    
    # Layout adjustments
    fig.update_layout(
        xaxis_rangeslider_visible=False, 
        height=height,
        hovermode='x unified',
        template='plotly_dark', # Use dark theme as it usually looks better for trading
        margin=dict(l=10, r=10, t=30, b=10)
    )
    
    return fig
