from fastapi import FastAPI, APIRouter

app = FastAPI()
router = APIRouter(prefix="/api")


@router.get("/")
async def root():
    return {"message": "Hello World from Backend"}


@router.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@router.get("/test")
async def test_endpoint():
    return {"message": "github action test complete"}


app.include_router(router)
