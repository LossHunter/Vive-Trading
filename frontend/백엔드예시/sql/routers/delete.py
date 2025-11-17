from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class DeleteData(BaseModel):
    userid: str
    number: int
    
@router.post("/delete")
async def data_delete(data: DeleteData):
    userid = data.userid
    number = data.number
    
    check = True

    if check:
        return True
    else :
        return False