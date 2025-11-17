from fastapi import APIRouter
from pydantic import BaseModel
import os
import pickle
from datetime import datetime

router = APIRouter()

class InsertData(BaseModel):
    sub: str
    email: str
    name: str
    exp: int

folder_path = "./table/users"

@router.post("/signin")
async def data_insert(data: InsertData):
    file_name = f"{data.sub}.pkl"
    file_path = os.path.join(folder_path, file_name)

    current_time = datetime.now()
    formatted_time = current_time.strftime("%Y%m%d%H%M")

    content = {
        "userId": f"{data.sub}",
        "username": f"{data.name}",
        "usemodel":"",
        "colors": "#000",
        "logo": "",
        "time": f"{formatted_time}",
        "why": "",
        "position": "",
        "bit":0,
        "eth":0,
        "doge":0,
        "sol":0,
        "xrp":0,
        "non":0,
        "total": 0
    }

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    if not os.path.exists(file_path):
        with open(file_path, "wb") as f:
            pickle.dump(content, f)
        created = True
    else:
        created = False

    return created
