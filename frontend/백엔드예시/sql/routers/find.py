from fastapi import APIRouter
from pydantic import BaseModel
import os
import pickle
import glob

router = APIRouter()

class FindData(BaseModel):
    gpt: int
    gemini: int
    grok: int
    deepseek: int
    user: str | None = None

DATABASE_PATH = "./table/users"

@router.post("/find")
async def data_find(data: FindData):
    gpt = data.gpt
    gemini = data.gemini
    grok = data.grok
    deepseek = data.deepseek
    user = data.user
    
    if user == None:         
        datapathlist = [gpt, gemini, grok, deepseek]
    else:
        datapathlist = [gpt, gemini, grok, deepseek, user]

    datalist=[]
    for data in datapathlist:
        dataset = []
        file_path = os.path.join(DATABASE_PATH, f"{data}.pkl")

        with open(file_path, "rb") as f:
            user_data = pickle.load(f)  
        
        dataset.append(user_data)

        datalist.append(dataset)


    check = True
    
    if check:
        return datalist
    else :
        return False
