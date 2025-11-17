from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from services.jwt_service import TokenJwt
from fastapi.responses import JSONResponse
import httpx
import asyncio
import jwt
router = APIRouter()

class Token(BaseModel):
    token: str

@router.post("/getUser")
async def google_login(request: Request):
    token = request.cookies.get("jwt") 
    user = None
    if token:
        try:
            payload = jwt.decode(token, "dev_secret_key_12345", algorithms=["HS256"], leeway=10)
            user = payload["sub"]
        except jwt.ExpiredSignatureError:
            print("JWT 만료 → user=None으로 처리 후 계속 진행")
        except jwt.InvalidTokenError:
            print("JWT 만료 → user=None으로 처리 후 계속 진행")

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "http://localhost:8320/api/findID",
                    json={"sub" : user}
                )
                res.raise_for_status()
                data = res.json()
            break
        except httpx.RequestError as e:
            print(f"Payload 전송 실패 (시도 {attempt}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(0.5) 
            else:
                return JSONResponse(status_code=500, content={"success": False, "message": "Payload 전송 실패"})
    
    return data['data']
