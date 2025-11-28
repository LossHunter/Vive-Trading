import logging
from sqlalchemy import text
from app.db.database import SessionLocal

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_sequences():
    db = SessionLocal()
    try:
        tables = [
            "upbit_day_candles",
            "upbit_candles_minute3",
            "upbit_rsi",
            "upbit_indicators",
            "upbit_trades",
            "upbit_ticker",
            "upbit_orderbook"
        ]
        
        for table in tables:
            logger.info(f"🔧 Fixing sequence for {table}...")
            # Get max id
            result = db.execute(text(f"SELECT MAX(id) FROM {table}")).scalar()
            max_id = result if result is not None else 0
            
            # Reset sequence
            seq_name = f"{table}_id_seq"
            next_val = max_id + 1
            db.execute(text(f"SELECT setval('{seq_name}', {next_val}, false)"))
            logger.info(f"✅ Sequence {seq_name} reset to {next_val}")
            
        db.commit()
        logger.info("✨ All sequences fixed successfully.")
        
    except Exception as e:
        logger.error(f"❌ Error fixing sequences: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_sequences()
