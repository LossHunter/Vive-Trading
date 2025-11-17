from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import pickle
import os

router = APIRouter()

# Version 체크용 모델
class VersionCheck(BaseModel):
    version: str

DB_PATH = os.path.join(os.path.dirname(__file__), "../database/db.pkl")

@router.post("/versioncheck")
async def versionCheck(version_check: VersionCheck):
    version = version_check.version

    # 클라이언트 날짜 파싱
    try:
        version_date = datetime.fromisoformat(version)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid version date format")

    # DB 읽기
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="Database file not found")

    try:
        with open(DB_PATH, 'rb') as f:
            try:
                datalist = pickle.load(f)
            except EOFError:
                datalist = []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading DB: {str(e)}")

    if not datalist or not isinstance(datalist, list):
        raise HTTPException(status_code=500, detail="Database is empty or invalid format")

    # 마지막 날짜 확인
    try:
        last_time_str = datalist[-1][0]["time"]
        last_date = datetime.fromisoformat(last_time_str.replace('/', '-'))  # 슬래시 교정
    except (KeyError, IndexError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"Invalid last date in DB: {str(e)}")

    diff_days = (last_date - version_date).days

    return diff_days > 7