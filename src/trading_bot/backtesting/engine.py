import pandas as pd
from typing import Dict, Any, List, Optional
from trading_bot.scoring.service import ScoringService
from trading_bot.risk.service import RiskService
from trading_bot.data_feeds.binance_fetcher import BinanceDataFetcher
from trading_bot.data_feeds.bybit_fetcher import BybitDataFetcher
from trading_bot.logger import get_logger

logger = get_logger(__name__)

class BacktestEngine:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, active_timeframes: Optional[List[str]] = None, data_source: str = "bybit", testnet: bool = False):
        self.active_timeframes = active_timeframes or ['1h']
        self.scoring = ScoringService(active_timeframes=self.active_timeframes)
        self.risk = RiskService()
        self.data_source = data_source.lower()
        self.testnet = testnet
        
        if self.data_source == "binance":
             # Fallback to Bybit if Binance is requested but we know it fails, 
             # or just warn. User said "Use only Bybit".
             # For now, let's allow it but default to Bybit in the signature.
             logger.warning("Binance data source requested but might be blocked. Consider using 'bybit'.")
             self.fetcher = BinanceDataFetcher(api_key=api_key, api_secret=api_secret)
        else:
             self.fetcher = BybitDataFetcher(api_key=api_key, api_secret=api_secret, testnet=testnet)
             logger.info(f"Using Bybit Data Fetcher with testnet={testnet}")
             
        self.trades = []
        self.balance = 10000.0
        self.position = None 
        self.debug_logs = []
    
    def _interval_to_timedelta(self, interval: str) -> pd.Timedelta:
        if interval.endswith('m'):
            return pd.Timedelta(minutes=int(interval[:-1]))
        elif interval.endswith('h'):
            return pd.Timedelta(hours=int(interval[:-1]))
        elif interval.endswith('d'):
            return pd.Timedelta(days=int(interval[:-1]))
        elif interval == '1week':
             return pd.Timedelta(weeks=1)
        return pd.Timedelta(minutes=1)

    def run(self, symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500, debug: bool = False) -> Dict[str, Any]:
        """
        Run the backtest simulation.
        """
        self.trades = []
        self.balance = 10000.0
        self.position = None
        self.debug_logs = []
        
        logger.info(f"Starting backtest for {symbol} {interval} with {limit} candles")
        
        # Fetch data
        df = self.fetcher.fetch_history(symbol, interval, limit)
        if df.empty:
            logger.error(f"No data returned from {self.data_source}")
            return {"error": f"No data returned from {self.data_source}"}
            
        logger.info(f"Fetched {len(df)} candles")
        if debug:
            self.debug_logs.append(f"Fetched {len(df)} candles for {symbol} {interval}")

        # Fetch data for other active timeframes
        mtf_data_full = {}
        mtf_deltas = {}
        main_delta = self._interval_to_timedelta(interval)

        for tf in self.active_timeframes:
            if tf == interval:
                continue
            tf_df = self.fetcher.fetch_history(symbol, tf, limit)
            if not tf_df.empty:
                mtf_data_full[tf] = tf_df
                mtf_deltas[tf] = self._interval_to_timedelta(tf)
                if debug:
                    self.debug_logs.append(f"Fetched {len(tf_df)} candles for timeframe {tf}")
            
        # Iterate
        # Need at least 21 candles for SMA (Scoring Service Requirement)
        if len(df) < 21:
             return {"error": "Insufficient data for strategy (need > 21 candles)"}

        processed_candles = 0
        signals_count = 0
        
        for i in range(21, len(df)):
            processed_candles += 1
            # Window of data up to i
            window = df.iloc[:i+1]
            
            # Prepare MTF data
            current_open_time = window.iloc[-1]['timestamp']
            current_close_time = current_open_time + main_delta
            
            step_mtf_data = {}
            # Add current timeframe
            step_mtf_data[interval] = window
            
            # Add other timeframes
            for tf, tf_df in mtf_data_full.items():
                tf_delta = mtf_deltas[tf]
                # Filter: Closed candles
                valid_mask = (tf_df['timestamp'] + tf_delta) <= current_close_time
                filtered_df = tf_df[valid_mask]
                
                if not filtered_df.empty:
                    step_mtf_data[tf] = filtered_df

            signal = self.scoring.calculate_signals(window, mtf_data=step_mtf_data)
            
            current_price = signal.get('price') # Warning: calculate_signals might not return price explicitly in 'details', it returns action/score/details. 
            # We need to extract price from window if not present.
            if not current_price:
                 current_price = window.iloc[-1]['close']
            
            timestamp = window.iloc[-1]['timestamp'] # signal.get('timestamp') might be missing too
            
            score = signal.get('score', 0)
            action = signal.get('action', 'HOLD')
            
            # Log first 10 candles in debug mode
            if debug and processed_candles <= 10:
                self.debug_logs.append(f"Candle {timestamp}: Score={score:.4f}, Action={action}")
                if 'details' in signal:
                     self.debug_logs.append(f"  Details: {signal['details']}")

            if action in ['BUY', 'SELL']:
                signals_count += 1
                if debug:
                    self.debug_logs.append(f"Signal generated at {timestamp}: {action}, Score={score:.4f}")

            # Check for exit if in position
            if self.position:
                # Simple logic: Exit if opposite signal
                if (self.position['type'] == 'LONG' and action == 'SELL') or \
                   (self.position['type'] == 'SHORT' and action == 'BUY'):
                    self._close_position(current_price, timestamp)
                    if debug:
                        self.debug_logs.append(f"Closed position at {timestamp} due to opposite signal")
            
            # Check for entry
            if not self.position and action in ['BUY', 'SELL']:
                # Validate with risk
                # Use risk limit amount from RiskService if available, otherwise default
                trade_size = 1000.0
                if hasattr(self.risk, 'risk_limit_amount') and self.risk.risk_limit_amount > 0:
                     if trade_size > self.risk.risk_limit_amount:
                         trade_size = self.risk.risk_limit_amount

                # Pass more context to validate_order if possible
                risk_valid, risk_reason = self.risk.validate_order({"amount": trade_size, "price": current_price, "symbol": symbol})
                
                if risk_valid: 
                    self._open_position(action, current_price, timestamp, trade_size)
                    if debug:
                        self.debug_logs.append(f"Opened {action} position at {timestamp} @ {current_price} (Size: {trade_size})")
                else:
                    if debug:
                         self.debug_logs.append(f"Risk validation failed for {action} at {timestamp}: {risk_reason}")

        # Close any open position at the end
        if self.position:
            last_price = df.iloc[-1]['close']
            last_time = df.iloc[-1]['timestamp']
            self._close_position(last_price, last_time)
            if debug:
                self.debug_logs.append(f"Closed remaining position at {last_time}")
                    
        return self._generate_report(df, processed_candles, signals_count)

    def _open_position(self, signal_type: str, price: float, timestamp: pd.Timestamp, size_usdt: float):
        amount = size_usdt / price
        self.position = {
            'type': 'LONG' if signal_type == 'BUY' else 'SHORT',
            'entry_price': price,
            'amount': amount, 
            'timestamp': timestamp,
            'size_usdt': size_usdt
        }
        
    def _close_position(self, price: float, timestamp: pd.Timestamp):
        # Calculate PnL
        entry = self.position['entry_price']
        amount = self.position['amount']
        
        if self.position['type'] == 'LONG':
            pnl = (price - entry) * amount
        else:
            pnl = (entry - price) * amount
            
        self.balance += pnl
        
        trade_record = {
            'entry_time': self.position['timestamp'],
            'exit_time': timestamp,
            'type': self.position['type'],
            'entry_price': entry,
            'exit_price': price,
            'pnl': pnl,
            'balance': self.balance,
            'return_pct': (pnl / self.position['size_usdt']) * 100
        }
        self.trades.append(trade_record)
        self.position = None

    def _generate_report(self, df: pd.DataFrame, processed_candles: int, signals_count: int) -> Dict[str, Any]:
        win_rate = 0.0
        equity_curve = []
        if self.trades:
            wins = len([t for t in self.trades if t['pnl'] > 0])
            win_rate = (wins / len(self.trades)) * 100
            equity_curve = [t['balance'] for t in self.trades]
            
        return {
            "initial_balance": 10000.0,
            "final_balance": self.balance,
            "total_pnl": self.balance - 10000.0,
            "win_rate": win_rate,
            "trade_count": len(self.trades),
            "trades": self.trades,
            "equity_curve": equity_curve,
            "data": df,
            "processed_candles": processed_candles,
            "signals_count": signals_count,
            "debug_logs": self.debug_logs
        }

