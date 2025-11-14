"""
지갑 데이터 서비스 모듈
지갑 데이터 조회 및 WebSocket 브로드캐스트를 담당합니다.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, TYPE_CHECKING
from sqlalchemy.orm import Session
from sqlalchemy import desc

from config import WalletConfig, UpbitAPIConfig
from database import SessionLocal, UpbitAccounts, UpbitTicker

if TYPE_CHECKING:
    from main import ConnectionManager

logger = logging.getLogger(__name__)


async def get_wallet_data(db: Session, target_date: Optional[datetime] = None) -> List[Dict]:
    """
    지갑 데이터 생성
    upbit_accounts 테이블에서 데이터를 조회하여 지갑 정보를 생성합니다.
    
    Args:
        db: 데이터베이스 세션
        target_date: 조회할 날짜 (None이면 현재 날짜)
    
    Returns:
        List[Dict]: 지갑 데이터 리스트 (4개 사용자)
    """
    # 사용자 정보 (4개만, 하드코딩, 나중에 다른 테이블에서 가져올 예정)
    users = [
        {"userId": 1, "username": "GPT", "colors": "#3b82f6", "logo": "GPT_Logo.png", "why": "Time is a precious resource."},
        {"userId": 2, "username": "Gemini", "colors": "#22c55e", "logo": "Gemini_LOGO.png", "why": "Consistency is key."},
        {"userId": 3, "username": "Grok", "colors": "#f59e0b", "logo": "Grok_LOGO.png", "why": "Be fearless in pursuit of goals."},
        {"userId": 4, "username": "DeepSeek", "colors": "#ef4444", "logo": "DeepSeek_LOGO.png", "why": "Your potential is limitless."},
    ]
    
    # 조회할 날짜 설정
    if target_date is None:
        target_date = datetime.utcnow()
    
    date_str = target_date.strftime("%Y/%m/%d")
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    
    # 해당 날짜의 티커 가격 조회
    ticker_prices = {}
    for market in UpbitAPIConfig.MAIN_MARKETS:
        ticker = db.query(UpbitTicker).filter(
            UpbitTicker.market == market,
            UpbitTicker.collected_at >= start_of_day,
            UpbitTicker.collected_at < end_of_day
        ).order_by(desc(UpbitTicker.collected_at)).first()
        
        if not ticker:
            ticker = db.query(UpbitTicker).filter(
                UpbitTicker.market == market
            ).order_by(desc(UpbitTicker.collected_at)).first()
        
        if ticker and ticker.trade_price:
            currency = market.split("-")[1] if "-" in market else market
            ticker_prices[currency] = float(ticker.trade_price)
    
    # 각 사용자별 지갑 데이터 생성
    wallet_data = []
    
    for user in users:
        accounts = db.query(UpbitAccounts).filter(
            UpbitAccounts.collected_at >= start_of_day,
            UpbitAccounts.collected_at < end_of_day
        ).order_by(desc(UpbitAccounts.collected_at)).all()
        
        if not accounts:
            accounts = db.query(UpbitAccounts).order_by(desc(UpbitAccounts.collected_at)).all()
        
        # 코인 수량 초기화
        coin_balances = {
            "BTC": 0.0,
            "ETH": 0.0,
            "DOGE": 0.0,
            "SOL": 0.0,
            "XRP": 0.0,
            "KRW": 0.0
        }
        
        # 계정 정보에서 코인 수량 추출
        seen_currencies = set()
        for account in accounts:
            if account.currency:
                currency = account.currency.upper()
            else:
                currency = ""
            
            if currency in seen_currencies:
                continue
            seen_currencies.add(currency)
            
            balance = float(account.balance) if account.balance else 0.0
            
            if currency in coin_balances:
                coin_balances[currency] = balance
        
        # 전체 잔액 계산
        total = (
            (coin_balances["BTC"] * ticker_prices.get("BTC", 0)) +
            (coin_balances["ETH"] * ticker_prices.get("ETH", 0)) +
            (coin_balances["DOGE"] * ticker_prices.get("DOGE", 0)) +
            (coin_balances["SOL"] * ticker_prices.get("SOL", 0)) +
            (coin_balances["XRP"] * ticker_prices.get("XRP", 0)) +
            coin_balances["KRW"]
        )
        
        wallet_data.append({
            "userId": user["userId"],
            "username": user["username"],
            "colors": user["colors"],
            "logo": user["logo"],
            "time": date_str,
            "why": user["why"],
            "btc": coin_balances["BTC"],
            "eth": coin_balances["ETH"],
            "doge": coin_balances["DOGE"],
            "sol": coin_balances["SOL"],
            "xrp": coin_balances["XRP"],
            "non": coin_balances["KRW"],
            "total": total
        })
    
    return wallet_data


async def get_wallet_data_30days(db: Session) -> List[Dict]:
    """
    30일치 지갑 데이터 생성
    최근 30일간의 지갑 데이터를 생성합니다.
    
    Args:
        db: 데이터베이스 세션
    
    Returns:
        List[Dict]: 30일치 지갑 데이터 리스트
    """
    all_wallet_data = []
    
    for days_ago in range(30):
        target_date = datetime.utcnow() - timedelta(days=days_ago)
        daily_data = await get_wallet_data(db, target_date)
        all_wallet_data.extend(daily_data)
    
    return all_wallet_data


async def broadcast_wallet_data_periodically(manager: "ConnectionManager"):
    """
    지갑 데이터 주기적 전송 (정분 기준)
    WebSocket으로 지갑 데이터를 매 분 0초에 브로드캐스트합니다.
    
    Args:
        manager: WebSocket ConnectionManager 인스턴스
    """
    while True:
        try:
            # 다음 정분까지 대기
            wait_seconds = calculate_wait_seconds_until_next_scheduled_time('minute', 1)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            
            db = SessionLocal()
            try:
                wallet_data = await get_wallet_data(db)
                
                await manager.broadcast(json.dumps({
                    "type": "wallet",
                    "data": wallet_data,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
                
                logger.debug(f"✅ 지갑 데이터 전송 완료 ({len(wallet_data)}명, 정분 기준)")
            finally:
                db.close()
        
        except asyncio.CancelledError:
            logger.info("🛑 지갑 데이터 전송 중지")
            break
        except Exception as e:
            logger.error(f"❌ 지갑 데이터 전송 오류: {e}")
            await asyncio.sleep(60)

