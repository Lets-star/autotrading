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
                # Handle specific error codes more gracefully
                ret_code = response['retCode']
                ret_msg = response.get('retMsg', 'Unknown error')
                
                if ret_code == 401:
                    logger.error(f"Authentication error fetching positions: {ret_msg}. Please check API keys and testnet/mainnet configuration.")
                elif ret_code == 10003:  # Invalid request
                    logger.warning(f"Invalid request for positions: {ret_msg}")
                else:
                    logger.error(f"Error fetching positions (code {ret_code}): {ret_msg}")
                
                return []
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "unauthorized" in error_str:
                logger.error(f"Authentication exception fetching positions: {e}. Please check API keys and testnet/mainnet configuration.")
            elif "http status code is not 200" in error_str:
                logger.error(f"HTTP error fetching positions: {e}. This may indicate incorrect testnet/mainnet settings.")
            else:
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
