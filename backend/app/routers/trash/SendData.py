# from fastapi import APIRouter, Depends
# from pydantic import BaseModel
# from sqlalchemy.orm import Session
# from fastapi import APIRouter, Request, HTTPException
# import jwt
# import logging
# from datetime import datetime

# from app.services.wallet_service import get_wallet_data_list_other,get_account_information_list
# from app.db.database import get_db
# import json
# from fastapi.responses import JSONResponse

# logging.basicConfig( # 로그출력 형식
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)


# router = APIRouter()

# ## POST 방식으로 전환
# ## USERD ID 보안 문제
# # 오류 수정
# # 맵핑 잘못되어 있음
# # def Mapping(wallet_data):
# #     datainput = {}
# #     for data in wallet_data:
# #         userid = data["userId"]
# #         if userid not in datainput:
# #             datainput[userid] = []
# #         datainput[userid].append(data)
    
# #     ## 날짜 역순
# #     # for key, val in datainput.items():
# #     #     datainput[key] = list(reversed(val))
        
# #     senddata = list(datainput.values())
# #     return senddata

# def Mapping(wallet_data):
#     datainput = {}
#     for data in wallet_data:
#         userId = str(data["userId"])
#         # ORM 객체 속성 접근
#         if userId not in datainput:
#             datainput[userId] = []
#         # 딕셔너리로 변환해서 append
#         datainput[userId].append({
#             "userId": data["userId"],
#             "username": data["username"],
#             "usemodel": data["usemodel"],
#             "colors": data["colors"],
#             "logo": data["logo"],
#             "time": data["time"],
#             "why" : data["why"],
#             "bit": data["bit"],
#             "eth": data["eth"],
#             "doge": data["doge"],
#             "sol": data["sol"],
#             "xrp": data["xrp"],
#             "non": data["non"],
#             "total": data["total"],
#         })
    
#     # 역순 정렬
#     for key, val in datainput.items():
#         datainput[key] = list(reversed(val))
        
#     senddata = list(datainput.values())
#     return senddata

# # LastTime 의미x => 삭제
# # def DateCheck(time):
# #     ts_s = time / 1000

# #     return True

# # OpenDB 지우면서 LastTime이 의미없어지 check 로 변경
# class Time(BaseModel):
#     latest_time: str

# @router.post("/wallet")
# async def datalist(request: Request, getdata:Time, db: Session = Depends(get_db)):
#     time = getdata.latest_time
#     token = request.cookies.get("jwt")
    
#     ## 테스트용으로 HTTP ONLY 쿠키는 안받아오는걸로..

#     user = None
#     payload = None

#     try:
#         payload = jwt.decode(token, "dev_secret_key_12345", algorithms=["HS256"], leeway=10)
#         user = payload["sub"]
#     except (jwt.ExpiredSignatureError,jwt.InvalidTokenError):
#         # 리플레쉬 토큰 또는 로그인 모달로 재이동하도록 진행
#         print("JWT 만료 → user=None으로 처리 후 계속 진행")

#     try:
#         wallet_data = await get_account_information_list(db)
#         data = Mapping(wallet_data=wallet_data)
#     except Exception as e:
#         logger.error(f"❌ 지갑 데이터 조회 오류: {e}")
#         raise HTTPException(status_code=500, detail=f"지갑 데이터 조회 중 오류 발생: {str(e)}")

#     send_latest_time = None

#     for user_list in data:
#         for item in user_list:
#             t_str = str(item["time"])
#             t = datetime.strptime(t_str, "%Y%m%d%H%M%S")  # YYYYMMDDHHMMSS
#             if send_latest_time is None or t > send_latest_time:
#                 send_latest_time = t

#     send_latest_time_str = send_latest_time.strftime("%Y%m%d%H%M%S")

#     # 송신 데이터 수량 확인
#     data_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
#     print(f"Payload size: {len(data_bytes)} bytes")

#     if send_latest_time:
#         return JSONResponse(content={"data": data, "time" : send_latest_time_str})
#     else:
#         return JSONResponse(content={"data" : "Nodata", "time" : "null"})