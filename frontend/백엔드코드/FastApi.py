import pandas as pd
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
import os
import requests
import os
from wanapi import Wand_DB

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost:53755",
        "http://localhost:53755",
        ],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 수정해야 될 부 분
# DB로 할 시 지워야 될 부분
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = "/mnt/c/Users/Hong/Desktop/project/backend/db.json"

date_endpoint = ""

@app.get("/api/wandb_runs")
async def get_wandb_runs_endpoint():
    try:   
        wand_db = Wand_DB()
        datalist = wand_db.call_back()
        return datalist
    
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

@app.get("/api/data_stream")
async def stream_datalist():
    global date_endpoint
    async def data_generator():
        # 수정해야 될 부 분
        # JSON 파일 대신 DB 읽어와 맵핑 후 반환
        # Read => find(x=>x.id == userid)
        # 클래스 함수로 외부 파일에 둬서 import 하기
        # db => find => 맵핑해서 => db.json 형식이랑 비슷하게? [] datalist 넣어주시면됨.
        with open(db_path, 'r', encoding='utf-8') as f:
            datalist = json.load(f)
        
        if datalist:
            date_endpoint = datalist[-1][0]["time"]

        for item in datalist:
            yield json.dumps(item) + "\n"
            await asyncio.sleep(0.05)  
    return StreamingResponse(data_generator(), media_type="text/plain")


@app.websocket("/ws/chartdata")
async def websocket_endpoint(websocket: WebSocket):
    global date_endpoint
    await websocket.accept()
    try:
        while True:
            # 수정해야 될 부 분
            # JSON 파일 대신 DB 읽어와 맵핑 후 반환
            # Read => find(x=>x.id == userid)
            # 클래스 함수로 외부 파일에 둬서 import 하기
            # 클래스 함수로 외부 파일에 둬서 import 하기
            # db => find => 맵핑해서 => db.json 형식이랑 비슷하게? [] datalist 넣어주시면됨.
            with open(db_path, 'r', encoding='utf-8') as f:
                datalist = json.load(f)
            
            # 밑 부분은 수정 X 
            new_data = [item for item in datalist if item[0]["time"] > date_endpoint]

            if new_data:
                for data in new_data:
                    await websocket.send_json(data)
                    await asyncio.sleep(0.1)
                date_endpoint = new_data[-1][0]["time"]

                print(f"현재 날짜 : {date_endpoint} data : 전송 성공")
            await asyncio.sleep(10) 

    except WebSocketDisconnect:
        logging.warning("클라이언트 연결 종료")