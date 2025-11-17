from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class FindAllData(BaseModel):
    userid: str
    tablename : str

@router.post("/findAll")
async def data_findAll(data : FindAllData):
    userid = data.userid
    tablename = data.tablename

    check = True
    if check:
        return True
    else :
        return False