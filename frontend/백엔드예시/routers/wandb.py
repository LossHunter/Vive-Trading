from fastapi import APIRouter
from services.wanapi import Wand_DB
import requests

router = APIRouter()


# API: WandB Runs 가져오기
@router.get("/wandb_runs")
async def get_wandb_runs_endpoint():
    try:   
        wand_db = Wand_DB()
        datalist = wand_db.call_back()
        return datalist
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}