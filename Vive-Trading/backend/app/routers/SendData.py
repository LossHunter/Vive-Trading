from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import APIRouter, Request
import jwt
from datetime import datetime, timezone

from app.db.database import get_db, init_db, test_connection, SessionLocal

from sqlalchemy.orm import Session

from app.services.wallet_service import get_wallet_data_30days
from app.db.database import get_db
import json
from fastapi.responses import JSONResponse

from app.db.database import AccountInformation
from sqlalchemy import desc
    

def Mapping(mapping_data):
    datainput = {}
    for data in mapping_data:
        userid = str(data["userid"])
        # ORM 객체 속성 접근
        if userid not in datainput:
            datainput[userid] = []
        # 딕셔너리로 변환해서 append
        datainput[userid].append({
            "userId": data["userid"],
            "username": data["username"],
            "usemodel": data["usemodel"],
            "colors": data["colors"],
            "logo": data["logo"],
            "position": data["position"],
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
    for key, val in datainput.items():
        senddata.append(val)
    
    return senddata

class Time(BaseModel):
    latest_time: datetime

router = APIRouter()

@router.post("/wallet")
async def datalist(request: Request, getdata:Time, db: Session = Depends(get_db)):
    time = getdata.latest_time

    if time is 0:
        time = datetime.min.replace(tzinfo=timezone.utc)

    # token = request.cookies.get("jwt")
    # try:
    #     payload = jwt.decode(token, "dev_secret_key_12345", algorithms=["HS256"], leeway=10)
    #     user = payload["sub"]
    # except (jwt.ExpiredSignatureError,jwt.InvalidTokenError):
    #     print("JWT 만료 → user=None으로 처리 후 계속 진행")

    ids = ["1", "2", "3", "4"]

    user_colors_map = {
            "1": "#3b82f6",  # GPT
            "2": "#22c55e",  # Gemini
            "3": "#f59e0b",  # Grok
            "4": "#ef4444",  # DeepSeek
        }
    
    result = []
    try:
        for i in range(len(ids)):
            history_list = db.query(AccountInformation) \
                .filter(AccountInformation.user_id == ids[i]) \
                .filter(AccountInformation.created_at > time) \
                .order_by(AccountInformation.created_at.asc()).all() # 역순으로 테스트

            # "userId": data["userid"],
            # "username": data["username"],
            # "usemodel": data["usemodel"],
            # "colors": data["colors"],
            # "logo": data["logo"],
            # "position": data["position"],
            # "time": data["time"],
            # "why" : data["why"],
            # "bit": data["btc"],
            # "eth": data["eth"],
            # "doge": data["doge"],
            # "sol": data["sol"],
            # "xrp": data["xrp"],
            # "non": data["non"],
            # "total": data["total"],

            if len(history_list) > 0:
                for history in history_list:
                    result.append({
                        "userid": history.user_id,
                        "username": history.username,
                        "usemodel": history.model_name,
                        "colors": user_colors_map[str(i + 1)],
                        "logo": history.logo,
                        "why" : history.why,
                        "position" : history.position,
                        "btc" : float(history.btc),
                        "eth" : float(history.eth),
                        "doge" : float(history.doge),
                        "sol" : float(history.sol),
                        "xrp" : float(history.xrp),
                        "non" : int(history.krw),
                        "total" : int(history.total),
                        "time": history.created_at.isoformat()
                    })
           
    except Exception as e: 
        print("ERROR : 00001: " , e)
        return JSONResponse(content={"data" : "Nodata", "time" : "null"})

    try:
        send = Mapping(result)
    except Exception as e: 
        print("ERROR : 00005 : ", e)
        return JSONResponse(content={"data" : "Nodata", "time" : "null"})

    try:
        if len(send) > 0 :
            send_latest_time = datetime.min.replace(tzinfo=timezone.utc)
            for user_list in send:  # send는 사용자별 리스트
                for item in user_list:
                    # item["time"]가 datetime이면 그대로, 문자열이면 fromisoformat
                    t = item["time"]
                    if isinstance(t, str):
                        t = datetime.fromisoformat(t)
                    if send_latest_time < t:
                        send_latest_time = t
            send_latest_time_str = send_latest_time.isoformat()

            print(len(send))
            print(send_latest_time_str)
            data_bytes = json.dumps(send, ensure_ascii=False).encode('utf-8')
            print(f"Payload size: {len(data_bytes)} bytes")   
            print("데이터 전성 성공")

            return JSONResponse(content={"data": send, "time" : send_latest_time_str})
        else:
            print("ERROR : 00006 : ", "전송데이터가 없습니다.")
            return JSONResponse(content={"data" : "Nodata", "time" : "null"})
    except Exception as e: 
        print("ERROR : 00004 : ", e)
        return JSONResponse(content={"data" : "Nodata", "time" : "null"})

      

    