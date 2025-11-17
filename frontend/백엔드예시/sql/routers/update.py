from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class UpdateData(BaseModel):
    userid: str
    number: int
    updatedata : dict

@router.post("/update")
async def data_update(data : UpdateData):
    check = True
    userid = data.userid
    number = data.number 
    updatedata = data.updatedata

    if check:
        return True
    else :
        return False