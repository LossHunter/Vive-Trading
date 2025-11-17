from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
import pickle
import os
import asyncio
from fastapi import APIRouter

router = APIRouter()

DB_PATH = os.path.join(os.path.dirname(__file__), "../database/db.pkl")

# WebSocket API
@router.websocket("/chartdata")
async def websocket_endpoint(websocket: WebSocket, lastTime: str = Query(None)):

    await websocket.accept()
    client_host, client_port = websocket.client
    client_date_endpoint = lastTime or ""
    try:
        while True:
            if not os.path.exists(DB_PATH):
                await asyncio.sleep(0.5)
                continue

            with open(DB_PATH, 'rb') as f:
                try:
                    datalist = pickle.load(f)
                except EOFError:
                    datalist = []

            # 새로운 데이터 필터링
            new_data = [item for item in datalist if item[0]["time"] > client_date_endpoint]

            if new_data:
                for data in new_data:
                    await websocket.send_json(data)
                client_date_endpoint = new_data[-1][0]["time"]
                print(f"클라이언트 : {client_host}, Port : {client_port} Day : {client_date_endpoint} 데이터 전송 성공")
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        print("클라이언트 연결 종료")
