from fastapi import APIRouter
from pydantic import BaseModel
import os
from fastapi.responses import JSONResponse
import json
import httpx
import asyncio
from fastapi import APIRouter, Request, HTTPException
import jwt

router = APIRouter()

DB_PATH = os.path.join(os.path.dirname(__file__), "../database/db.pkl")


class UserId(BaseModel):
    userid: int

@router.post("/data")
async def stream_datalist(request: Request):
    token = request.cookies.get("jwt")  # 쿠키에서 JWT 가져오기
    user = None
    payload = None

    if token:
        try:
            payload = jwt.decode(token, "dev_secret_key_12345", algorithms=["HS256"], leeway=10)
            user = payload["sub"]
        except jwt.ExpiredSignatureError:
            print("JWT 만료 → user=None으로 처리 후 계속 진행")
        except jwt.InvalidTokenError:
            print("JWT 만료 → user=None으로 처리 후 계속 진행")
        
    convey = {
        "gpt":1,
        "gemini":2,
        "grok":3,
        "deepseek":4, 
        "user":user
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "http://localhost:8320/api/find",
                    json=convey
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
            
    return JSONResponse(content=data)

