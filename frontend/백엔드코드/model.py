import time
import random
from datetime import datetime, timedelta
import json

class Model():
    def __init__(self, init_asst, prices):
        self.datalist = []
        
        self.init_asst = init_asst

        self.position = ["buy", "hold", "sell"]

        self.prices = prices

        self.why = [
            "Life is full of surprises.", "Never give up on your dreams.", "Every day is a new opportunity.",
            "Quality over quantity.", "Consistency is key.", "Time is a precious resource.",
            "Life is what you make it.", "Strive for progress, not perfection.", "Be fearless in pursuit of goals.",
            "Seek progress, not approval.", "Embrace failures as lessons.", "Your potential is limitless."
        ]
        
        # 유저별 코인 포트폴리오
        self.user_1_coin = self.generate_random_portfolio()
        self.user_2_coin = self.generate_random_portfolio()
        self.user_3_coin = self.generate_random_portfolio()
        self.user_4_coin = self.generate_random_portfolio()
    
    def main(self, datetime):
        # 하루치 데이터 생성
        self.generate_prices()

        total_1 = self.coin_sum(**self.user_1_coin)
        total_2 = self.coin_sum(**self.user_2_coin)
        total_3 = self.coin_sum(**self.user_3_coin)
        total_4 = self.coin_sum(**self.user_4_coin)

        # datalist 생성
        self.datalist = [
            {
                "userId": 1,
                "username": "GPT",
                "colors": "#3b82f6",
                "logo": "GPT_Logo.png",
                "time": datetime,
                "why": random.choice(self.why),
                "position": random.choice(self.position),
                **self.user_1_coin,
                "total": total_1
            },
            {
                "userId": 2,
                "username": "Gemini",
                "colors": "#22c55e",
                "logo": "Gemini_LOGO.png",
                "time": datetime,
                "why": random.choice(self.why),
                "position": random.choice(self.position),
                **self.user_2_coin,
                "total": total_2
            },
            {
                "userId": 3,
                "username": "Grok",
                "colors": "#f59e0b",
                "logo": "Grok_LOGO.png",
                "time": datetime,
                "why": random.choice(self.why),
                "position": random.choice(self.position),
                **self.user_3_coin,
                "total": total_3
            },
            {
                "userId": 4,
                "username": "DeepSeek",
                "colors": "#ef4444",
                "logo": "DeepSeek_LOGO.png",
                "time": datetime,
                "why": random.choice(self.why),
                "position": random.choice(self.position),
                **self.user_4_coin,
                "total": total_4
            }
        ]

        return self.datalist
        
    def generate_random_portfolio(self):
        portfolio = {}
        remaining = self.init_asst
        for coin, price in self.prices.items():
            if coin == "non":
                continue
            max_qty = remaining / price  # float으로 계산
            qty = random.uniform(0, max_qty) if max_qty > 0 else 0
            portfolio[coin] = qty
            remaining -= qty * price
        portfolio["non"] = remaining
        return portfolio

    def coin_sum(self, btc, eth, doge, sol, xrp, non):
        return round((self.prices["btc"]*btc + self.prices["eth"]*eth +
                self.prices["doge"]*doge + self.prices["sol"]*sol +
                self.prices["xrp"]*xrp + non),0)

    def generate_prices(self):
        for key in self.prices:
            self.prices[key] *= random.uniform(0.9, 1.1)




