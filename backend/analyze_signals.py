import sys
import os
from uuid import UUID
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from app.db.database import LLMTradingSignal, Base
from app.core.config import DatabaseConfig

# Database connection
DATABASE_URL = DatabaseConfig.get_connection_string()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def analyze_signals():
    db = SessionLocal()
    try:
        # Simulation Account ID (from test.py)
        # "account_id_suffix": "1" -> 00000000-0000-0000-0000-000000000001
        account_id = UUID("00000000-0000-0000-0000-000000000001")
        
        print(f"Analyzing signals for account: {account_id}")
        
        # Fetch recent signals
        signals = db.query(LLMTradingSignal).filter(
            LLMTradingSignal.account_id == account_id
        ).order_by(desc(LLMTradingSignal.created_at)).limit(20).all()
        
        if not signals:
            print("No signals found for this account.")
            return

        print(f"Found {len(signals)} recent signals.")
        print("-" * 80)
        
        for i, signal in enumerate(signals):
            print(f"[{i+1}] Time: {signal.created_at} | Coin: {signal.coin} | Signal: {signal.signal}")
            print(f"    Confidence: {signal.confidence}")
            print(f"    Price: {signal.current_price}")
            print(f"    Target: {signal.profit_target} | Stop: {signal.stop_loss}")
            print(f"    Justification: {signal.justification}")
            if signal.thinking:
                print(f"    Thinking (first 200 chars): {signal.thinking[:200]}...")
            print("-" * 80)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    analyze_signals()
