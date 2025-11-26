import asyncio
import signal
import sys
from trading_bot.config import settings
from trading_bot.logger import setup_logging, get_logger
from trading_bot.data_feeds.service import DataFeedService
from trading_bot.scoring.service import ScoringService
from trading_bot.execution.service import ExecutionService
from trading_bot.risk.service import RiskService

setup_logging()
logger = get_logger("BotRunner")

class TradingBot:
    def __init__(self):
        self.data_feed = DataFeedService()
        self.scoring = ScoringService()
        self.risk = RiskService()
        self.execution = ExecutionService()
        self.running = False

    async def run(self):
        self.running = True
        await self.data_feed.start()
        
        logger.info("Trading Bot Loop Started")
        while self.running:
            try:
                # 1. Get Data
                data = await self.data_feed.get_latest_data()
                
                # 2. Calculate Signal
                signal = self.scoring.calculate_signals(data)
                
                # 3. Check Risk and Calculate Sizing
                if signal.get("action") == "BUY": 
                    # Placeholder for getting current market data for risk calculation
                    # In a real scenario, we'd have current price, ATR, liquidity from data feed
                    current_price = 100.0 # Placeholder
                    atr_value = 2.0 # Placeholder
                    liquidity = 100000.0 # Placeholder
                    
                    # Validate Setup
                    if self.risk.validate_trade_setup(current_open_trades=0, atr_value=atr_value, liquidity=liquidity):
                        
                        # Calculate Stops
                        stops = self.risk.calculate_stops(current_price, atr_value, side='buy')
                        
                        # Calculate Sizing
                        # Assume account balance is fetched from exchange
                        account_balance = 10000.0 # Placeholder
                        qty = self.risk.calculate_position_size(
                            account_balance=account_balance,
                            entry_price=current_price,
                            stop_loss_price=stops['stop_loss']
                        )
                        
                        if qty > 0:
                            # 4. Execute
                            order_params = {
                                "symbol": "BTCUSDT", # Placeholder
                                "side": "Buy",
                                "qty": qty,
                                "price": current_price,
                                "stop_loss": stops['stop_loss'],
                                "take_profit": stops['take_profit'],
                                "order_type": "Limit"
                            }
                            await self.execution.execute_order(order_params)
                
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
                await asyncio.sleep(5)

    async def shutdown(self):
        self.running = False
        await self.data_feed.stop()
        logger.info("Trading Bot Shutdown Complete")

async def main():
    bot = TradingBot()
    
    # Handle signals
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    
    def signal_handler():
        logger.info("Signal received, shutting down...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    bot_task = asyncio.create_task(bot.run())
    
    await stop_event.wait()
    await bot.shutdown()
    await bot_task

if __name__ == "__main__":
    asyncio.run(main())
