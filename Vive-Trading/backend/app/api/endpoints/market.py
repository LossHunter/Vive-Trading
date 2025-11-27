from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def read_market_root():
    return {"message": "Market endpoint root"}

@router.get("/price/{ticker}")
async def get_market_price(ticker: str):
    return {"message": f"Getting price for {ticker}"}
