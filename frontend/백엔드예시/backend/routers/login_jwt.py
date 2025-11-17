from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.jwt_service import TokenJwt
from fastapi.responses import JSONResponse
import httpx
import asyncio

router = APIRouter()

class Token(BaseModel):
    token: str

@router.post("/GoogleLogin")
async def google_login(code: Token):
    jwt_service = TokenJwt(code.token)
    try:
        payload, jwt_token = await jwt_service.generation()
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google Access Token")
    
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "http://localhost:8320/api/signin",
                    json=payload
                )
                res.raise_for_status()
            break
        except httpx.RequestError as e:
            print(f"Payload 전송 실패 (시도 {attempt}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(0.5) 
            else:
                return JSONResponse(status_code=500, content={"success": False, "message": "Payload 전송 실패"})

    response = JSONResponse(content={"message": "로그인 성공"})
    response.set_cookie(
        key="jwt",
        value=jwt_token,
        httponly=True,
        samesite="lax", # 테스트용으로 None
        secure=False
    )

    return response

@router.post("/logout")
async def logout():
    response = JSONResponse(content={"message": "로그아웃 완료"})
    response.delete_cookie(key="jwt", path="/")
    print("로그아웃 완료")
    return response
