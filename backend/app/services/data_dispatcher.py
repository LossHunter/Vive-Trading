import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import UpbitAPIConfig
from app.db.database import SessionLocal, LLMPromptData, LLMTradingSignal

logger = logging.getLogger(__name__)


USERS_TEMPLATE = [
    {"userId": 1, "username": "GPT", "colors": "#3b82f6", "logo": "GPT_Logo.png", "why": "Time is a precious resource."},
    {"userId": 2, "username": "Gemini", "colors": "#22c55e", "logo": "Gemini_LOGO.png", "why": "Consistency is key."},
    {"userId": 3, "username": "Grok", "colors": "#f59e0b", "logo": "Grok_LOGO.png", "why": "Be fearless in pursuit of goals."},
    {"userId": 4, "username": "DeepSeek", "colors": "#ef4444", "logo": "DeepSeek_LOGO.png", "why": "Your potential is limitless."},
    {"userId": 5, "username": "USER", "colors": "#ef4470", "logo": "USERR.png", "why": "Your potential is limitless."},
]


def _load_account_payload(raw) -> list[dict]:
    """raw가 어떤 형태로 들어와도 배열 형태로 변환"""
    if raw is None:
        return []  # 데이터 없으면 [] 반환
    if isinstance(raw, str):
        try:
            return json.loads(raw)  # 파싱 실패하면 경고 로그 남기고 [] 반환
        except json.JSONDecodeError:
            logger.warning("account_data_json을 JSON으로 파싱할 수 없습니다.")
            return []
    if isinstance(raw, dict):
        if "accounts" in raw:
            return raw["accounts"]  # "accounts" 키가 있으면 raw["accounts"]
        if "users" in raw:
            return raw["users"]  # "users" 키가 있으면 raw["users"]
        return [raw]
    return list(raw)


def _build_wallet_rows(prompt: LLMPromptData, signals: list[LLMTradingSignal]) -> list[dict]:
    """프롬프트와 시그널을 기반으로 지갑 데이터 생성"""
    account_rows = _load_account_payload(prompt.account_data_json)  # 사용자별 잔고 데이터
    
    # 코인별 시그널 상세 정보 매핑 (signal, justification, created_at 모두 포함)
    signal_details = {
        sig.coin.upper(): {
            "signal": sig.signal.lower() if sig.signal else "hold",
            "justification": sig.justification or "No justification provided.",
            "created_at": sig.created_at
        }
        for sig in signals
    }
    
    # 기본 시그널 (BTC 또는 첫 번째 시그널) - 모든 사용자에게 적용될 기본값
    default_signal = None
    if "BTC" in signal_details:
        default_signal = signal_details["BTC"]
    elif "KRW-BTC" in signal_details:
        default_signal = signal_details["KRW-BTC"]
    elif signal_details:
        default_signal = signal_details[list(signal_details.keys())[0]]
    
    # time: 시그널의 created_at 사용 (없으면 프롬프트 시간)
    if default_signal and default_signal.get("created_at"):
        time_str = default_signal["created_at"].strftime("%Y/%m/%d")
    else:
        time_str = (prompt.generated_at or prompt.created_at or datetime.now(timezone.utc)).strftime("%Y/%m/%d")
    
    account_by_user = {row.get("userId"): row for row in account_rows}

    wallets: list[dict] = []
    for template in USERS_TEMPLATE:
        """위의 USERS_TEMPLATE 기반으로 지갑 1개씩 만들어서 리스트로 반환"""
        base = template.copy()
        base["time"] = time_str

        entry = account_by_user.get(template["userId"], {})
        balances = entry.get("balances") or entry

        def read(name: str) -> float:  # 잔고 데이터 읽기
            return float(balances.get(name) or balances.get(name.upper()) or 0.0)

        btc = read("btc")
        eth = read("eth")
        doge = read("doge")
        sol = read("sol")
        xrp = read("xrp")
        non = float(
            balances.get("non")
            or balances.get("krw")
            or balances.get("cash")
            or entry.get("cash")
            or 0.0
        )

        # 사용자별 주요 코인 결정 (기본값: BTC)
        primary_coin = entry.get("primary_coin", "BTC").upper()
        
        # 해당 코인의 시그널 가져오기 (없으면 기본 시그널)
        user_signal = signal_details.get(primary_coin) or default_signal or {}
        
        # why: LlmTradingSignal의 justification 사용
        base["why"] = user_signal.get("justification", template["why"])
        
        # position: LlmTradingSignal의 signal 사용
        base["position"] = user_signal.get("signal", "hold")
        
        base.update(  # 수치 필드 업데이트
            {
                "btc": btc,
                "eth": eth,
                "doge": doge,
                "sol": sol,
                "xrp": xrp,
                "non": non,
            }
        )

        total = entry.get("total") or entry.get("evaluation", {}).get("total")
        if total is None:
            total = btc + eth + doge + sol + xrp + non
        base["total"] = float(total)

        wallets.append(base)

    return wallets


async def get_wallet_data(db: Session, target_prompt: LLMPromptData | None = None) -> list[dict]:
    """가장 최신 프롬프트 기반으로 5명 지갑 데이터 생성"""
    prompt = target_prompt or (  # target_prompt가 있으면 그대로 사용
        db.query(LLMPromptData)  # 없으면 LLMPromptData에서 가장 최신 기록 가져옴
        .order_by(LLMPromptData.generated_at.desc(), LLMPromptData.id.desc())
        .first()
    )
    if not prompt:  # 프롬프트 없으면 기본 USER_TEMPLATE 반환
        logger.warning("llm_prompt_data가 없어 기본 템플릿만 반환합니다.")
        return [row.copy() for row in USERS_TEMPLATE]

    signals = (  # 프롬프트에 연결된 트레이딩 시그널 목록 가져옴
        db.query(LLMTradingSignal)
        .filter(LLMTradingSignal.prompt_id == prompt.id)
        .all()
    )
    return _build_wallet_rows(prompt, signals)


async def get_wallet_data_30days(db: Session) -> list[dict]:
    """최근 30개의 프롬프트를 이용해 지갑 데이터 반환: 최근 30일 동안의 지갑 상태 변화 보기위함"""
    prompts = (  # LLMPromptData 테이블에서 가장 최근에 생성된 30개의 프롬프트 가져옴
        db.query(LLMPromptData)
        .order_by(LLMPromptData.generated_at.desc(), LLMPromptData.id.desc())
        .limit(30)
        .all()
    )
    if not prompts:
        return [row.copy() for row in USERS_TEMPLATE]

    signal_map: dict[int, list[LLMTradingSignal]] = defaultdict(list)
    signals = (
        db.query(LLMTradingSignal)
        .filter(LLMTradingSignal.prompt_id.in_([p.id for p in prompts]))
        .all()
    )
    for sig in signals:  # prompt_id 기준으로 시그널 묶기
        signal_map[sig.prompt_id].append(sig)

    data: list[dict] = []
    for prompt in prompts:
        data.extend(_build_wallet_rows(prompt, signal_map.get(prompt.id, [])))
    return data


async def broadcast_wallet_data_periodically(manager, wallet_broadcast_interval: int = 10) -> None:
    """최신 지갑 데이터를 배열 그대로 WebSocket으로 브로드캐스트"""
    while True:
        try:
            await asyncio.sleep(wallet_broadcast_interval)
            db = SessionLocal()
            try:
                wallets = await get_wallet_data(db)
                await manager.broadcast(json.dumps(wallets))
                logger.debug("✅ 지갑 데이터 전송 완료 (%s명)", len(wallets))
            finally:
                db.close()
        except asyncio.CancelledError:
            logger.info("🛑 지갑 데이터 전송 중지")
            raise
        except Exception as exc:
            logger.error("❌ 지갑 데이터 전송 오류: %s", exc)
            await asyncio.sleep(60)
