import pandas as pd
from typing import Dict, Any, List, Optional
from trading_bot.scoring.service import ScoringService
from trading_bot.risk.service import RiskService
from trading_bot.data_feeds.bybit_fetcher import BybitDataFetcher
from trading_bot.logger import get_logger

logger = get_logger(__name__)

class BacktestEngine:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.scoring = ScoringService()
        self.risk = RiskService()
        self.fetcher = BybitDataFetcher(api_key=api_key, api_secret=api_secret)
        self.trades = []
        self.balance = 10000.0
        self.position = None 
    
    def run(self, symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500) -> Dict[str, Any]:
        """
        Run the backtest simulation.
        """
        self.trades = []
        self.balance = 10000.0
        self.position = None
        
        logger.info(f"Starting backtest for {symbol} {interval} with {limit} candles")
        
        # Fetch data
        df = self.fetcher.fetch_history(symbol, interval, limit)
        if df.empty:
            logger.error("No data returned from Bybit")
            return {"error": "No data returned from Bybit"}
            
        logger.info(f"Fetched {len(df)} candles")
            
        # Iterate
        # Need at least 21 candles for SMA (Scoring Service Requirement)
        if len(df) < 21:
             return {"error": "Insufficient data for strategy (need > 21 candles)"}

        for i in range(21, len(df)):
            # Window of data up to i
            window = df.iloc[:i+1]
            signal = self.scoring.calculate_signals(window)
            
            current_price = signal.get('price')
            timestamp = signal.get('timestamp')
            
            if not current_price:
                continue

            # Check for exit if in position
            if self.position:
                # Simple logic: Exit if opposite signal
                if (self.position['type'] == 'LONG' and signal['action'] == 'SELL') or \
                   (self.position['type'] == 'SHORT' and signal['action'] == 'BUY'):
                    self._close_position(current_price, timestamp)
            
            # Check for entry
            if not self.position and signal['action'] in ['BUY', 'SELL']:
                # Validate with risk
                # Assuming fixed trade size of 1000 USDT for simulation
                trade_size = 1000.0
                if self.risk.validate_order({"amount": trade_size}): 
                    self._open_position(signal['action'], current_price, timestamp, trade_size)
        
        # Close any open position at the end
        if self.position:
            last_price = df.iloc[-1]['close']
            last_time = df.iloc[-1]['timestamp']
            self._close_position(last_price, last_time)
                    
        return self._generate_report(df)

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

    def _generate_report(self, df: pd.DataFrame) -> Dict[str, Any]:
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
            "data": df
        }
