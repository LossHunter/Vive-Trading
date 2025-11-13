import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
import requests
from wanapi import Wand_DB
from fastapi.middleware.gzip import GZipMiddleware
from fastapi import Query
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

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
    async def data_generator():
        db_path = "/mnt/c/Users/Hong/Desktop/project/backend/db.json"
        with open(db_path, 'r', encoding='utf-8') as f:
            datalist = json.load(f)

        for item in datalist:
            yield json.dumps(item) + "\n"
    return StreamingResponse(data_generator(), media_type="text/plain")


@app.websocket("/ws/chartdata")
async def websocket_endpoint(websocket: WebSocket, lastTime: str = Query(None)):
    db_path = "/mnt/c/Users/Hong/Desktop/project/backend/db.json"
    await websocket.accept()
    client_host, client_port = websocket.client
    client_date_endpoint = lastTime or ""
    try:
        while True:
            with open(db_path, 'r', encoding='utf-8') as f:
                datalist = json.load(f)
            
            new_data = [item for item in datalist if item[0]["time"] > client_date_endpoint]

            if new_data:
                for data in new_data:
                    await websocket.send_json(data)
                client_date_endpoint = new_data[-1][0]["time"]
                print(f"클라이언트 : {client_host}, Port : {client_port} Day : {client_date_endpoint} 데이터 전송 성공")
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        logging.warning("클라이언트 연결 종료")