import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import UpbitAPIConfig, WalletConfig
from app.db.database import SessionLocal, UpbitAccounts, UpbitTicker

from .connection_manager import manager

logger = logging.getLogger(__name__)


async def get_wallet_data(db: Session, target_date: Optional[datetime] = None) -> List[Dict]:
    """
    지갑 데이터 생성: upbit_accounts 테이블에서 데이터를 조회하여 지갑 정보 생성

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

    # 날짜 문자열 (일 기준)
    date_str = target_date.strftime("%Y/%m/%d")

    # 해당 날짜의 시작과 끝 시간 계산
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    # 해당 날짜의 티커 가격 조회 (각 마켓별 해당 날짜의 최신 가격)
    ticker_prices: Dict[str, float] = {}
    for market in UpbitAPIConfig.MAIN_MARKETS:
        ticker = (
            db.query(UpbitTicker)
            .filter(
                UpbitTicker.market == market,
                UpbitTicker.collected_at >= start_of_day,
                UpbitTicker.collected_at < end_of_day,
            )
            .order_by(desc(UpbitTicker.collected_at))
            .first()
        )

        # 해당 날짜에 데이터가 없으면 전체 최신 데이터 사용
        if not ticker:
            ticker = (
                db.query(UpbitTicker)
                .filter(UpbitTicker.market == market)
                .order_by(desc(UpbitTicker.collected_at))
                .first()
            )

        if ticker and ticker.trade_price:
            # 마켓 코드에서 화폐 코드 추출 (예: KRW-BTC -> BTC)
            currency = market.split("-")[1] if "-" in market else market
            ticker_prices[currency] = float(ticker.trade_price)

    # 각 사용자별 지갑 데이터 생성
    wallet_data: List[Dict] = []

    for user in users:
        # upbit_accounts에서 해당 날짜의 계정 정보 조회
        # account_id는 UUID 타입이므로 필터링하지 않고, 모든 계정을 조회한 후 사용자별로 매핑
        # 현재는 account_id가 없거나 NULL인 경우를 처리하기 위해 전체 조회
        accounts = (
            db.query(UpbitAccounts)
            .filter(
                UpbitAccounts.collected_at >= start_of_day,
                UpbitAccounts.collected_at < end_of_day,
            )
            .order_by(desc(UpbitAccounts.collected_at))
            .all()
        )

        # 해당 날짜에 데이터가 없으면 전체 최신 데이터 사용
        if not accounts:
            accounts = db.query(UpbitAccounts).order_by(desc(UpbitAccounts.collected_at)).all()

        # 코인 수량 초기화
        btc = eth = doge = sol = xrp = non = 0.0 # KRW 현금 잔액
        # 계정 정보에서 코인 수량 추출 (같은 currency가 여러 개면 가장 최신 것 사용)
        seen_currencies = set()
        for account in accounts:
            currency = (account.currency or "").upper()
            if currency in seen_currencies:
                continue        
            seen_currencies.add(currency)

            balance = float(account.balance) if account.balance else 0.0

            if currency == "BTC":
                btc = balance
            elif currency == "ETH":
                eth = balance
            elif currency == "DOGE":
                doge = balance
            elif currency == "SOL":
                sol = balance
            elif currency == "XRP":
                xrp = balance
            elif currency == "KRW":
                non = balance

        # 전체 잔액 계산 (코인 가치 + 현금)
        total = (
            (btc * ticker_prices.get("BTC", 0))
            + (eth * ticker_prices.get("ETH", 0))
            + (doge * ticker_prices.get("DOGE", 0))
            + (sol * ticker_prices.get("SOL", 0))
            + (xrp * ticker_prices.get("XRP", 0))
            + non
        )

        wallet_data.append(
            {
                "userId": user["userId"],
                "username": user["username"],
                "colors": user["colors"],
                "logo": user["logo"],
                "time": date_str,
                "why": user["why"],
                "btc": btc,
                "eth": eth,
                "doge": doge,
                "sol": sol,
                "xrp": xrp,
                "non": non,
                "total": total,
            }
        )

    return wallet_data


async def get_wallet_data_30days(db: Session) -> List[Dict]:
    """최근 30일치 지갑 데이터 생성
    
        Args:
            db: 데이터베이스 세션
        
        Returns:
            List[Dict]: 30일치 지갑 데이터 리스트
    """
    all_wallet_data: List[Dict] = []

    # 최근 30일 데이터 생성
    for days_ago in range(30):
        target_date = datetime.utcnow() - timedelta(days=days_ago)
        daily_data = await get_wallet_data(db, target_date)
        all_wallet_data.extend(daily_data)
    return all_wallet_data


async def broadcast_wallet_data_periodically() -> None:
    """지갑 데이터 주기적 전송: WebSocket으로 지갑 데이터를 주기적으로 브로드캐스트"""
    while True:
        try:
            await asyncio.sleep(WalletConfig.WALLET_BROADCAST_INTERVAL)

            db = SessionLocal()
            try:
                wallet_data = await get_wallet_data(db)
                payload = json.dumps(
                    {
                        "type": "wallet",
                        "data": wallet_data,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                # WebSocket으로 브로드캐스트
                await manager.broadcast(payload)
                logger.debug("✅ 지갑 데이터 전송 완료 (%s명)", len(wallet_data))
            finally:
                db.close()

        except asyncio.CancelledError: 
            logger.info("🛑 지갑 데이터 전송 중지")
            raise
        except Exception as exc:
            logger.error("❌ 지갑 데이터 전송 오류: %s", exc)
            await asyncio.sleep(60) # 오류 발생 시 1분 대기 후 재시도
 