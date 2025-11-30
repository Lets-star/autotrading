import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from trading_bot.data_feeds.bybit_fetcher import BybitDataFetcher

logger = logging.getLogger(__name__)

class PositionTracker:
    def __init__(self, fetcher: BybitDataFetcher, storage_file: str = "data/positions.json"):
        self.fetcher = fetcher
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        
    def fetch_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        try:
            # category="linear" for USDT perps usually
            params = {"category": "linear", "settleCoin": "USDT"}
            if symbol:
                params["symbol"] = symbol
                
            response = self.fetcher.session.get_positions(**params)
            
            if response['retCode'] == 0:
                positions = response['result']['list']
                # Filter for active positions (size > 0)
                active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
                self.save_positions(active_positions)
                return active_positions
            else:
                logger.error(f"Error fetching positions: {response['retMsg']}")
                return []
        except Exception as e:
            logger.error(f"Exception fetching positions: {e}")
            return []

    def save_positions(self, positions: List[Dict[str, Any]]):
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(positions, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving positions: {e}")
            
    def get_stored_positions(self) -> List[Dict[str, Any]]:
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return []
        return []
