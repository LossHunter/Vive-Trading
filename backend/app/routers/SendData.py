from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import APIRouter, Request, HTTPException
import jwt
import logging
from datetime import datetime

from app.db.database import get_db, init_db, test_connection, SessionLocal, LLMPromptData, LLMTradingSignal

from sqlalchemy.orm import Session

from app.services.wallet_service import get_wallet_data_30days
from app.db.database import get_db
import json
from fastapi.responses import JSONResponse

from app.db.database import UpbitTicker, UpbitCandlesMinute3
from sqlalchemy import desc
    


logging.basicConfig( # 로그출력 형식
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def Mapping(mapping_data):
    datainput = {}
    for data in mapping_data:
        userId = str(data["userId"])
        # ORM 객체 속성 접근
        if userId not in datainput:
            datainput[userId] = []
        # 딕셔너리로 변환해서 append
        datainput[userId].append({
            "userId": data["userId"],
            "username": data["username"],
            # "usemodel": data["usemodel"], => 빠진거 같은데 상의 후 진행
            "colors": data["colors"],
            "logo": data["logo"],
            "time": data["time"],
            "why" : data["why"],
            "bit": data["btc"],
            "eth": data["eth"],
            "doge": data["doge"],
            "sol": data["sol"],
            "xrp": data["xrp"],
            "non": data["non"],
            "total": data["total"],
        })
    
    senddata = []
    # 역순 정렬
    for key, val in datainput.items():
        datainput[key] = list(reversed(val))
        
        senddata.append(datainput[key])
    
    return senddata

class Time(BaseModel):
    latest_time: str

router = APIRouter()

@router.post("/wallet")
async def datalist(request: Request, getdata:Time, db: Session = Depends(get_db)):
    time = getdata.latest_time
    token = request.cookies.get("jwt")

    try:
        payload = jwt.decode(token, "dev_secret_key_12345", algorithms=["HS256"], leeway=10)
        user = payload["sub"]
    except (jwt.ExpiredSignatureError,jwt.InvalidTokenError):
        # 리플레쉬 토큰 또는 로그인 모달로 재이동하도록 진행
        print("JWT 만료 → user=None으로 처리 후 계속 진행")

    db = SessionLocal()
    
    try:
        wallet_data_30days = await get_wallet_data_30days(db)
    
    # 최신 티커 데이터 조회
        tickers = db.query(UpbitTicker).order_by(desc(UpbitTicker.collected_at)).limit(100).all()
    
    # 최신 캔들 데이터 조회
        candles = db.query(UpbitCandlesMinute3).order_by(desc(UpbitCandlesMinute3.collected_at)).limit(100).all()
        db.close()
    except : 
        pass

    # 데이터를 JSON 형식으로 변환하여 스트리밍
    data_list = []
    
    # 30일치 지갑 데이터 추가
    for wallet in wallet_data_30days:
        data_list.append({
            "type": "wallet",
            "data": wallet
        })
    
    # 티커 데이터 추가
    for ticker in tickers:
        data_list.append({
            "type": "ticker",
            "market": ticker.market,
            "trade_price": float(ticker.trade_price) if ticker.trade_price else None,
            "collected_at": ticker.collected_at.isoformat() if ticker.collected_at else None
        })
    
    # 캔들 데이터 추가
    for candle in candles:
        data_list.append({
            "type": "candle",
            "market": candle.market,
            "trade_price": float(candle.trade_price) if candle.trade_price else None,
            "candle_date_time_utc": candle.candle_date_time_utc.isoformat() if candle.candle_date_time_utc else None
        })
    
    mapping_data = []

    for da in data_list:
        if "data" not in da:
            continue

        mapping_data.append(da["data"])

    sned = Mapping(mapping_data)

    send_latest_time = None

    for user_list in sned:
        for item in user_list:
            t_str = str(item["time"]).replace("/", "-")   # ← 여기 수정
            t = datetime.fromisoformat(t_str)
            if send_latest_time is None or t > send_latest_time:
                send_latest_time = t

    send_latest_time_str = send_latest_time.strftime("%Y%m%d%H%M%S")

    # 송신 데이터 수량 확인
    data_bytes = json.dumps(sned, ensure_ascii=False).encode('utf-8')
    print(f"Payload size: {len(data_bytes)} bytes")         
    
    if send_latest_time:
        return JSONResponse(content={"data": sned, "time" : send_latest_time_str})
    else:
        return JSONResponse(content={"data" : "Nodata", "time" : "null"})