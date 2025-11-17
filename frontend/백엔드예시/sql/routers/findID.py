from fastapi import APIRouter
from pydantic import BaseModel
import os
import pickle
import glob
from fastapi.responses import JSONResponse

router = APIRouter()
DATABASE_PATH = "./table/users"

class FindID(BaseModel):
    sub: str

# 여러 pickle 객체 안전하게 읽기
def load_all_pickle(file_path):
    items = []
    with open(file_path, "rb") as f:
        while True:
            try:
                obj = pickle.load(f)
                items.append(obj)
            except EOFError:
                break
            except pickle.UnpicklingError:
                break
    return items

@router.post("/findID")
async def data_find(user: FindID):
    target_user = user.sub

    file_paths = glob.glob(os.path.join(DATABASE_PATH, "*.pkl"))

    for file_path in file_paths: 
        file_name = os.path.basename(file_path)
        if file_name == f"{target_user}.pkl":
            data = load_all_pickle(file_path=file_path)
            return JSONResponse(content={"exists": True, "data": data})

    return False
