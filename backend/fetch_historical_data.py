import asyncio
import argparse
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import sys
import os

# Add backend directory to sys.path to allow imports from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.upbit_collector import UpbitAPICollector
from app.services.upbit_storage import UpbitDataStorage
from app.services.indicator_service import calculate_indicators_for_date_range
from app.db.database import SessionLocal
from app.core.config import UpbitAPIConfig

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def fetch_candles_chunk(
    collector: UpbitAPICollector,
    market: str,
    unit: str, # 'minute3' or 'day'
    to_date: Optional[datetime] = None,
    count: int = 200
) -> List[dict]:
    """Fetch a chunk of candles"""
    if to_date:
        # Convert UTC to KST (UTC+9) for Upbit API
        to_kst = to_date.astimezone(timezone(timedelta(hours=9)))
        to_str = to_kst.strftime("%Y-%m-%d %H:%M:%S")
    else:
        to_str = None
    
    if unit == 'minute3':
        return await collector.get_candles_minute3(market, count=count, to=to_str)
    elif unit == 'day':
        return await collector.get_candles_day(market, count=count, to=to_str)
    return []

async def collect_historical_data(
    start_time: datetime,
    end_time: datetime,
    markets: List[str]
):
    """Collect historical data for the given period"""
    db = SessionLocal()
    storage = UpbitDataStorage(db)
    
    try:
        async with UpbitAPICollector() as collector:
            for market in markets:
                logger.info(f"🚀 Starting collection for {market} ({start_time} ~ {end_time})")
                
                # 1. Collect 3-minute candles
                logger.info(f"  [Minute3] Fetching candles...")
                current_to = end_time
                total_minute3 = 0
                
                while current_to > start_time:
                    # Fetch candles
                    candles = await fetch_candles_chunk(collector, market, 'minute3', current_to, count=200)
                    
                    if not candles:
                        logger.warning(f"  [Minute3] No more candles found before {current_to}")
                        break
                    
                    # Save to DB
                    saved = storage.save_candles_minute3(candles, market)
                    total_minute3 += saved
                    
                    # Update 'to' for next batch (timestamp of the oldest candle)
                    # Candles are returned in reverse chronological order (newest first)
                    # We need the oldest one to fetch previous batch
                    oldest_candle = candles[-1]
                    oldest_time_str = oldest_candle['candle_date_time_utc']
                    oldest_time = datetime.fromisoformat(oldest_time_str)
                    if oldest_time.tzinfo is None:
                        oldest_time = oldest_time.replace(tzinfo=timezone.utc)
                    
                    # If oldest candle is already before start_time, we might be done after this batch
                    # But we continue until the loop condition is met or no data
                    current_to = oldest_time
                    
                    logger.info(f"  [Minute3] Saved {saved} candles. Next fetch before: {current_to}")
                    
                    # Rate limit
                    await asyncio.sleep(0.1) 
                    
                    if current_to <= start_time:
                        break
                
                logger.info(f"  ✅ [Minute3] Completed. Total saved: {total_minute3}")

                # 2. Collect Day candles
                logger.info(f"  [Day] Fetching candles...")
                current_to = end_time
                total_day = 0
                
                while current_to > start_time:
                    candles = await fetch_candles_chunk(collector, market, 'day', current_to, count=200)
                    
                    if not candles:
                        break
                        
                    saved = storage.save_candles_day(candles, market)
                    total_day += saved
                    
                    oldest_candle = candles[-1]
                    oldest_time_str = oldest_candle['candle_date_time_utc']
                    oldest_time = datetime.fromisoformat(oldest_time_str)
                    if oldest_time.tzinfo is None:
                        oldest_time = oldest_time.replace(tzinfo=timezone.utc)
                    
                    current_to = oldest_time
                    
                    logger.info(f"  [Day] Saved {saved} candles. Next fetch before: {current_to}")
                    await asyncio.sleep(0.1)
                    
                    if current_to <= start_time:
                        break
                
                logger.info(f"  ✅ [Day] Completed. Total saved: {total_day}")
                
                # 3. Calculate Indicators
                logger.info(f"  🧮 Calculating indicators...")
                # We need to calculate for the fetched range. 
                # Adding some buffer before start_time for indicators that need history (like EMA, RSI)
                # The service handles fetching previous data if available in DB.
                
                await calculate_indicators_for_date_range(
                    db, 
                    market, 
                    start_time, 
                    end_time, 
                    interval='both'
                )
                logger.info(f"  ✅ Indicators calculated.")
                
    except Exception as e:
        logger.error(f"❌ Error during collection: {e}", exc_info=True)
    finally:
        db.close()

def parse_arguments():
    parser = argparse.ArgumentParser(description="Fetch historical data from Upbit")
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start time (YYYY-MM-DD HH:MM:SS, UTC)"
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End time (YYYY-MM-DD HH:MM:SS, UTC)"
    )
    parser.add_argument(
        "--markets",
        type=str,
        default=None,
        help="Comma-separated list of markets (e.g., KRW-BTC,KRW-ETH). Default: All main markets"
    )
    return parser.parse_args()

async def main():
    args = parse_arguments()
    
    try:
        start_time = datetime.strptime(args.start, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        end_time = datetime.strptime(args.end, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        logger.error("❌ Invalid date format. Use YYYY-MM-DD HH:MM:SS")
        return

    if args.markets:
        markets = args.markets.split(",")
    else:
        markets = UpbitAPIConfig.MAIN_MARKETS
        
    logger.info("=" * 60)
    logger.info(f"📅 Historical Data Collection")
    logger.info(f"   Period: {start_time} ~ {end_time}")
    logger.info(f"   Markets: {markets}")
    logger.info("=" * 60)
    
    await collect_historical_data(start_time, end_time, markets)
    
    logger.info("✨ All tasks completed.")

if __name__ == "__main__":
    asyncio.run(main())
