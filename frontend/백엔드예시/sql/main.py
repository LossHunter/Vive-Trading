from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from routers import delete, find, findAll, insert, update, findID

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 라우터 등록
app.include_router(delete.router, prefix="/api")
app.include_router(find.router, prefix="/api")
app.include_router(findID.router, prefix="/api")
app.include_router(findAll.router, prefix="/api")
app.include_router(insert.router, prefix="/api")
app.include_router(update.router, prefix="/api")
