from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import APIRouter, Request, HTTPException
import jwt
from main import get_wallet_data_list_other
from app.db.database import get_db
import logging

logging.basicConfig( # 로그출력 형식
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


router = APIRouter()

## POST 방식으로 전환
## USERD ID 보안 문제
def Mapping(wallet_data):
    datainput = {}
    for data in wallet_data:
        userid = data["userId"]
        if userid not in datainput:
            datainput[userid] = []
        datainput[userid].append(data)
    
    ## 날짜 역순
    for key, val in datainput.items():
        datainput[key] = list(reversed(val))
        
    senddata = list(datainput.values())
    return senddata

class UserId(BaseModel):
    userid: int

@router.post("/wallet")
async def datalist(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("jwt")
    
    ## 테스트용으로 HTTP ONLY 쿠키는 안받아오는걸로..

    user = None
    payload = None

    if token:
        try:
            payload = jwt.decode(token, "dev_secret_key_12345", algorithms=["HS256"], leeway=10)
            user = payload["sub"]
        except jwt.ExpiredSignatureError:
            # 리플레쉬 토큰 또는 로그인 모달로 재이동하도록 진행
            print("JWT 만료 → user=None으로 처리 후 계속 진행")
        except jwt.InvalidTokenError:
            print("JWT 만료 → user=None으로 처리 후 계속 진행")
    else :
        user = None

    ## DB 접근 필히 비동기로 접근 할 것
    try:
        wallet_data = await get_wallet_data_list_other(db)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"지갑 데이터 조회 중 오류 발생: {str(e)}")
    
    data = Mapping(wallet_data=wallet_data)

    return data