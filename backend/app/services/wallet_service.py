"""
지갑 데이터 서비스 모듈
지갑 데이터 조회 및 WebSocket 브로드캐스트를 담당합니다.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Dict, Optional, TYPE_CHECKING

# SQLAlchemy ORM & 함수
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, desc, and_, Integer, Column, literal_column, select
from sqlalchemy.sql import over

# 앱 설정 및 유틸
from app.core.config import UpbitAPIConfig, LLMAccountConfig
from app.core.schedule_utils import calculate_wait_seconds_until_next_scheduled_time

# DB 모델
from app.db.database import (
    SessionLocal,
    UpbitAccounts,
    UpbitTicker,
    LLMTradingSignal,
    AccountInformation
)

if TYPE_CHECKING:
    from app.services.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


def get_account_id_from_user_id(user_id: int) -> str:
    """
    userId를 account_id로 변환
    account_id 형식: 00000000-0000-0000-0000-000000000001 (마지막 숫자가 userId)
    
    Args:
        user_id: 사용자 ID (1, 2, 3, 4)
    
    Returns:
        str: account_id (UUID 형식)
    """
    
    return f"00000000-0000-0000-0000-{user_id:012d}"


def get_account_id_for_user(user_id: int) -> str:
    """
    userId를 account_id(UUID)로 변환
    
    Args:
        user_id: 사용자 ID (1-4)
    
    Returns:
        str: UUID 형식의 account_id
    """
    # userId와 모델 매핑
    user_model_map = {
        1: "google/gemma-3-27b-it",    # user_id 1 → gemma → suffix "1"
        2: "openai/gpt-oss-120b",       # user_id 2 → gpt → suffix "2"
        3: "Qwen/Qwen3-30B-A3B-Thinking-2507-FP8",  # user_id 3 → qwen → suffix "3"
        4: "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",  # user_id 4 → deepseek → suffix "4"
    }
    
    model_name = user_model_map.get(user_id)
    if not model_name:
        raise ValueError(f"Invalid user_id: {user_id}")
    
    return LLMAccountConfig.get_account_id_for_model(model_name)


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
    # 사용자 정보 (4개만)
    users = [
        {"userId": 1, "username": "Gemma", "colors": "#22c55e", "logo": "Gemma_LOGO.png", "why": "Consistency is key."},
        {"userId": 2, "username": "GPT", "colors": "#3b82f6", "logo": "GPT_Logo.png", "why": "Time is a precious resource."},
        {"userId": 3, "username": "Qwen3", "colors": "#f59e0b", "logo": "Qwen3_LOGO.png", "why": "Be fearless in pursuit of goals."},
        {"userId": 4, "username": "DeepSeek", "colors": "#ef4444", "logo": "DeepSeek_LOGO.png", "why": "Your potential is limitless."},
    ]
    
    # 조회할 날짜 설정
    if target_date is None:
        target_date = datetime.now(timezone.utc)
    
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
    
    # account_id와 collected_at이 동일한 데이터를 묶어서 최신 것만 조회
    # 먼저 모든 계정 데이터 조회
    all_accounts = db.query(UpbitAccounts).filter(
        UpbitAccounts.collected_at >= start_of_day,
        UpbitAccounts.collected_at < end_of_day
    ).order_by(desc(UpbitAccounts.collected_at), desc(UpbitAccounts.id)).all()
    
    if not all_accounts:
        all_accounts = db.query(UpbitAccounts).order_by(
            desc(UpbitAccounts.collected_at), desc(UpbitAccounts.id)
        ).all()
    
    # account_id와 collected_at으로 그룹화하고, 각 그룹에서 최신 것(id가 가장 큰 것)만 선택
    # collected_at을 초 단위로 반올림하여 비교 (마이크로초 차이 무시)
    grouped_accounts = {}
    for account in all_accounts:
        # account_id와 collected_at이 None인 경우 처리
        account_id = account.account_id if account.account_id else "default"
        
        # collected_at을 초 단위로 반올림 (마이크로초 차이 무시)
        if account.collected_at:
            # 초 단위로 반올림 (마이크로초 제거)
            collected_at_rounded = account.collected_at.replace(microsecond=0)
            collected_at_key = collected_at_rounded.isoformat()
        else:
            collected_at_key = "unknown"
        
        currency = account.currency.upper() if account.currency else ""
        
        # 그룹 키: (account_id, collected_at(초 단위), currency)
        group_key = (account_id, collected_at_key, currency)
        
        # 같은 그룹에서 id가 더 큰 것이 있으면 스킵 (이미 최신 것만 남김)
        if group_key not in grouped_accounts:
            grouped_accounts[group_key] = account
        elif account.id > grouped_accounts[group_key].id:
            grouped_accounts[group_key] = account
    
    # account_id별로 최신 collected_at 찾기 (초 단위로 반올림된 값 기준)
    account_latest_collected = {}
    for (account_id, collected_at_key, currency), account in grouped_accounts.items():
        if account.collected_at:
            collected_at_rounded = account.collected_at.replace(microsecond=0)
            if account_id not in account_latest_collected:
                account_latest_collected[account_id] = collected_at_rounded
            elif collected_at_rounded > account_latest_collected[account_id]:
                account_latest_collected[account_id] = collected_at_rounded
    
    # 각 사용자별 최신 llm_trading_signal 조회
    # account_id와 userId 매핑: account_id의 마지막 숫자가 userId
 #   from app.services.order_execution_service import get_account_id_from_user_id
    
    user_signals = {}
    for user in users:
        # userId를 account_id로 변환
        account_id = get_account_id_from_user_id(user["userId"])
        
        # 해당 account_id의 최신 signal 조회
        latest_signal = db.query(LLMTradingSignal).filter(
            LLMTradingSignal.account_id == account_id
        ).order_by(desc(LLMTradingSignal.created_at)).first()
        
        if latest_signal:
            user_signals[user["userId"]] = {
                "justification": latest_signal.justification,
                "signal": latest_signal.signal
            }
        else:
            # signal이 없으면 기본값 사용
            user_signals[user["userId"]] = {
                "justification": user["why"],  # 기본값: 하드코딩된 why
                "signal": "hold"  # 기본값: hold
            }
    
    # 각 사용자별 지갑 데이터 생성
    wallet_data = []
    
    for user in users:

        # userId를 account_id로 변환
        user_account_id = get_account_id_from_user_id(user["userId"])

        # 해당 사용자의 account_id에 대한 최신 collected_at 찾기
        user_latest_collected = None
        for (acc_id, collected_at_key, currency), account in grouped_accounts.items():
            if acc_id == user_account_id and account.collected_at:
                collected_at_rounded = account.collected_at.replace(microsecond=0)
            if user_latest_collected is None or collected_at_rounded > user_latest_collected:
                user_latest_collected = collected_at_rounded
    
    # 해당 사용자의 account_id와 최신 collected_at의 데이터만 필터링
        accounts = [
            acc for (acc_id, collected_at_key, currency), acc in grouped_accounts.items()
            if acc_id == user_account_id 
            and acc.collected_at 
            and acc.collected_at.replace(microsecond=0) == user_latest_collected
        ]
        # # 전체에서 최신 collected_at 찾기 (모든 account_id 중)
        # if account_latest_collected:
        #     latest_collected_at = max(account_latest_collected.values())
        # else:
        #     latest_collected_at = None
        
        # # 최신 collected_at의 데이터만 필터링 (account_id와 collected_at이 일치하는 것)
        # # collected_at을 초 단위로 반올림하여 비교
        # accounts = [
        #     acc for (acc_id, collected_at_key, currency), acc in grouped_accounts.items()
        #     if acc.collected_at and acc.collected_at.replace(microsecond=0) == latest_collected_at
        # ]
        
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
                # "KRW-BTC" 형식에서 "BTC"만 추출
                if "-" in currency:
                    currency = currency.split("-")[1]
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
        
        # llm_trading_signal에서 why와 position 조회
        user_signal = user_signals.get(user["userId"], {})
        why = user_signal.get("justification", user["why"])  # signal의 justification 사용, 없으면 기본값
        position = user_signal.get("signal", "hold")  # signal의 signal 값을 그대로 사용, 없으면 기본값 "hold"
        
        wallet_data.append({
            "userId": user["userId"],
            "username": user["username"],
            "colors": user["colors"],
            "logo": user["logo"],
            "time": date_str,
            "why": why,  # llm_trading_signal의 justification 사용
            "position": position,  # llm_trading_signal의 signal 사용
            "btc": coin_balances["BTC"],
            "eth": coin_balances["ETH"],
            "doge": coin_balances["DOGE"],
            "sol": coin_balances["SOL"],
            "xrp": coin_balances["XRP"],
            "non": coin_balances["KRW"],
            "total": total
        })
    
    return wallet_data

async def get_wallet_data_list_other(db: Session) -> List[Dict]:
    """
    각 유저별 30일치 지갑 데이터를 평탄화된 형태로 생성
    각 유저의 30일치 데이터를 하나의 배열로 평탄화하여 반환합니다.
    
    Args:
        db: 데이터베이스 세션
    
    Returns:
        List[Dict]: 평탄화된 지갑 데이터 리스트
        [
            {
                "userId": 1,
                "username": "GPT",
                "usemodel": "GPT",
                "colors": "#3b82f6",
                "logo": "GPT_Logo.png",
                "time": 202511010000,  # YYYYMMDDHHmm 형식
                "why": "",
                "position": "",
                "bit": 0,
                "eth": 0,
                "doge": 0,
                "sol": 0,
                "xrp": 0,
                "non": 100000000,
                "total": 100000000
            },
            {
                "userId": 1,
                "username": "GPT",
                "usemodel": "GPT",
                "colors": "#3b82f6",
                "logo": "GPT_Logo.png",
                "time": 202511010015,
                "why": "",
                "position": "",
                "bit": 0,
                "eth": 0,
                "doge": 0,
                "sol": 0,
                "xrp": 0,
                "non": 100000000,
                "total": 100000000
            },
            ...
        ]
    """

    # 30일치 데이터 수집
    all_wallet_data = []
    for days_ago in range(30):
        target_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        daily_data = await get_wallet_data(db, target_date)
        all_wallet_data.extend(daily_data)
    
    # 평탄화된 형태로 변환
    result = []
    for wallet_item in all_wallet_data:
        # time 형식 변환: "2024/11/17" -> 202411170000 (YYYYMMDDHHmm)
        time_str = wallet_item["time"]  # "2024/11/17" 형식
        try:
            # 날짜 파싱
            date_obj = datetime.strptime(time_str, "%Y/%m/%d")
            # YYYYMMDDHHmm 형식으로 변환 (시간은 00:00으로 설정)
            time_int = int(date_obj.strftime("%Y%m%d%H%M"))
        except ValueError:
            # 파싱 실패 시 현재 시간 사용
            time_int = int(datetime.now(timezone.utc).strftime("%Y%m%d%H%M"))
        
        # usemodel은 username과 동일하게 설정
        usemodel = wallet_item["username"]
        
        result.append({
            "userId": wallet_item["userId"],
            "username": wallet_item["username"],
            "usemodel": usemodel,
            "colors": wallet_item["colors"],
            "logo": wallet_item["logo"],
            "time": time_int,
            "why": "", # 빈 문자열
            "position": "", # 빈 문자열
            "bit": wallet_item["btc"], # btc를 bit로 변환
            "eth": wallet_item["eth"],
            "doge": wallet_item["doge"],
            "sol": wallet_item["sol"],
            "xrp": wallet_item["xrp"],
            "non": wallet_item["non"],
            "total": wallet_item["total"]
        })
    
    return result


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
        target_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        daily_data = await get_wallet_data(db, target_date)
        all_wallet_data.extend(daily_data)
    
    return all_wallet_data

async def save_account_information(db: Session, target_date: Optional[datetime] = None) -> int:
    """
    AccountInformation 테이블에 지갑 데이터 저장
    get_wallet_data를 사용하여 지갑 데이터를 조회하고 AccountInformation 테이블에 저장합니다.
    
    Args:
        db: 데이터베이스 세션
        target_date: 조회할 날짜 (None이면 현재 날짜)
    
    Returns:
        int: 저장된 레코드 수
    """
    try:
        # 지갑 데이터 조회
        wallet_data = await get_wallet_data(db, target_date)
        
        if not wallet_data:
            logger.warning("⚠️ 저장할 지갑 데이터가 없습니다.")
            return 0
        
        saved_count = 0
        
        # 현재 시각 (UTC)
        current_time = datetime.now(timezone.utc)


        
        for wallet_item in wallet_data:
            try:
                # AccountInformation 레코드 생성
                account_info = AccountInformation(
                    user_id=str(wallet_item["userId"]),
                    username=wallet_item["username"],
                    model_name=wallet_item["username"],
                    logo=wallet_item["logo"],
                    why=wallet_item.get("why", ""),
                    position=wallet_item.get("position", "hold"),
                    btc=Decimal(str(wallet_item["btc"])),
                    eth=Decimal(str(wallet_item["eth"])),
                    doge=Decimal(str(wallet_item["doge"])),
                    sol=Decimal(str(wallet_item["sol"])),
                    xrp=Decimal(str(wallet_item["xrp"])),
                    krw=Decimal(str(wallet_item["non"])),  # non은 KRW 잔액
                    total=Decimal(str(wallet_item["total"])),
                    created_at=current_time
                )
                
                db.add(account_info)
                saved_count += 1
                
            except Exception as e:
                logger.error(f"❌ AccountInformation 저장 실패 (userId={wallet_item.get('userId')}): {e}")
                continue
        
        # 일괄 커밋
        db.commit()
        
        logger.info(f"✅ AccountInformation 저장 완료: {saved_count}개 레코드")
        return saved_count
        
    except Exception as e:
        logger.error(f"❌ AccountInformation 저장 중 오류 발생: {e}")
        db.rollback()
        return 0

async def get_account_information_list(db: Session, days: int = 30) -> List[Dict]:
    """
    AccountInformation 테이블에서 30일치 데이터 조회
    get_wallet_data_list_other와 동일한 형식으로 반환
    
    Args:
        db: 데이터베이스 세션
        days: 조회할 일수 (기본: 30일)
    
    Returns:
        List[Dict]: 평탄화된 지갑 데이터 리스트 (get_wallet_data_list_other와 동일한 형식)
    """
    try:
        # 최근 N일치 데이터 조회
        # cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # records = db.query(AccountInformation).filter(
        #     AccountInformation.created_at >= cutoff_date
        # ).order_by(AccountInformation.created_at.asc()).all()
        
        # 최근 n일치 데이터 조회
        # sub = (
        #     db.query(
        #         func.date_trunc('day', AccountInformation.created_at).label("day"),
        #         func.max(AccountInformation.created_at).label("max_time")
        #     )
        #     .group_by(func.date_trunc('day', AccountInformation.created_at))
        #     .order_by(func.date_trunc('day', AccountInformation.created_at).desc())
        #     .limit(30)
        #     .subquery()
        # )

        # records = (
        #     db.query(AccountInformation)
        #     .join(sub, AccountInformation.created_at == sub.c.max_time)
        #     .order_by(AccountInformation.created_at.asc())
        #     .all()
        # )


        #정시 기준 매 1시간마다의 마지막 데이터.
        # sub = (
        #     db.query(
        #         func.date_trunc('hour', AccountInformation.created_at).label("hour"),
        #         func.max(AccountInformation.created_at).label("max_time")
        #     )
        #     .group_by(func.date_trunc('hour', AccountInformation.created_at))
        #     .order_by(func.date_trunc('hour', AccountInformation.created_at).asc())
        #     .limit(30)
        #     .subquery()
        # )

        # records = (
        #     db.query(AccountInformation)
        #     .join(sub, AccountInformation.created_at == sub.c.max_time)
        #     .order_by(AccountInformation.created_at.asc())
        #     .all()
        # )

        subquery = (
            db.query(
                AccountInformation,
                func.row_number()
                .over(
                    partition_by=AccountInformation.username,  # username별 그룹
                    order_by=AccountInformation.created_at.desc()  # 최신순
                )
                .label("rn")
            )
            .subquery()
        )

        # 2. rn <= 30 조건으로 필터링
        records = (
            db.query(subquery)
            .filter(subquery.c.rn <= 30)
            .order_by(subquery.c.username, subquery.c.created_at.asc())  # username별 오름차순 정렬
            .all()
        )

        user_colors_map = {
            1: "#3b82f6",  # GPT
            2: "#22c55e",  # Gemini
            3: "#f59e0b",  # Grok
            4: "#ef4444",  # DeepSeek
        }

        result = []
        for record in records:
            # created_at을 YYYYMMDDHHmm 형식으로 변환
            time_int = int(record.created_at.strftime("%Y%m%d%H%M"))
            
            # userId에 해당하는 colors 가져오기
            user_id = int(record.user_id) if record.user_id and record.user_id.isdigit() else 0
            colors = user_colors_map.get(user_id, "")  # userId에 해당하는 color, 없으면 빈 문자열
            

            result.append({
                "userId": int(record.user_id) if record.user_id and record.user_id.isdigit() else 0,
                "username": record.username or "",
                "usemodel": record.model_name or record.username or "",
                "colors": colors,  # account_information에는 없음
                "logo": record.logo or "",
                "time": time_int,
                "why": record.why or "",
                "position": record.position or "",
                "bit": float(record.btc) if record.btc else 0.0,  # btc를 bit로 변환
                "eth": float(record.eth) if record.eth else 0.0,
                "doge": float(record.doge) if record.doge else 0.0,
                "sol": float(record.sol) if record.sol else 0.0,
                "xrp": float(record.xrp) if record.xrp else 0.0,
                "non": float(record.krw) if record.krw else 0.0,  # krw를 non으로 변환
                "total": float(record.total) if record.total else 0.0
            })
        
        return result
        
    except Exception as e:
        logger.error(f"❌ AccountInformation 조회 오류: {e}")
        return []


async def collect_account_information_periodically():
    """
    AccountInformation 주기적 수집
    매 분 0초에 지갑 데이터를 조회하여 AccountInformation 테이블에 저장합니다.
    """
    while True:
        try:
            # 다음 정분까지 대기
            wait_seconds = calculate_wait_seconds_until_next_scheduled_time('minute', 1)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            
            db = SessionLocal()
            try:
                saved_count = await save_account_information(db)
                if saved_count > 0:
                    logger.info(f"✅ AccountInformation 수집 완료: {saved_count}개 레코드 저장")
                else:
                    logger.debug("⏭️ AccountInformation 수집: 저장할 데이터 없음")
            finally:
                db.close()
        
        except asyncio.CancelledError:
            logger.info("🛑 AccountInformation 수집 중지")
            break
        except Exception as e:
            logger.error(f"❌ AccountInformation 수집 오류: {e}")
            await asyncio.sleep(60)

def _map_wallet_data_by_user(wallet_data: List[Dict]) -> List[List[Dict]]:
    """
    지갑 데이터를 userId별로 그룹화
    SendData.py의 Mapping 함수와 동일한 로직
    
    Args:
        wallet_data: 평탄화된 지갑 데이터 리스트
    
    Returns:
        List[List[Dict]]: userId별로 그룹화된 배열의 배열
    """
    datainput = {}
    for data in wallet_data:
        userid = data["userId"]
        if userid not in datainput:
            datainput[userid] = []
        datainput[userid].append(data)
    
    senddata = list(datainput.values())
    return senddata


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
                wallet_data = await get_account_information_list(db)
                
                mapped_data = _map_wallet_data_by_user(wallet_data)
                
                # 프론트엔드가 기대하는 형식으로 직접 전송 (배열의 배열)
                await manager.broadcast(json.dumps(mapped_data))


                logger.debug(f"✅ 지갑 데이터 전송 완료 ({len(wallet_data)}명, 정분 기준)")
            finally:
                db.close()
        
        except asyncio.CancelledError:
            logger.info("🛑 지갑 데이터 전송 중지")
            break
        except Exception as e:
            logger.error(f"❌ 지갑 데이터 전송 오류: {e}")
            await asyncio.sleep(60)