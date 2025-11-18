import asyncio
from fastapi import APIRouter
from app.services.wanapi import Wand_DB

router = APIRouter()

@router.get("/wandb_runs")
async def get_wandb_runs_endpoint():
    try:
        wand_db = Wand_DB()
        loop = asyncio.get_running_loop()
        datalist = await loop.run_in_executor(None, wand_db.call_back)
        return datalist
    except Exception as e:
        return {"error": str(e)}