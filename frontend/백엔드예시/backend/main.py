from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
 
from routers import chartdata, wandb, versioncheck, login_jwt, data, getUser

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://34.64.168.33", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 라우터 등록
app.include_router(wandb.router, prefix="/api")
app.include_router(versioncheck.router, prefix="/api")
app.include_router(data.router, prefix="/api")
app.include_router(chartdata.router, prefix="/ws")
app.include_router(login_jwt.router, prefix="/api")
app.include_router(getUser.router, prefix="/api")