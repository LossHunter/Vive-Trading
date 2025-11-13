from model import Model
import time
import json
import os
from datetime import datetime, timedelta

date = "2025/11/02"
init_asst = 10_000_000
prices = {
            "btc": 151_109_000,
            "eth": 4_924_000,
            "doge": 247,
            "sol": 231_800,
            "xrp": 3_290
        }

model = Model(init_asst, prices)

file_path = r'C:\Users\Hong\Desktop\project\backend\db.json'

date_endpoint = ""

if not os.path.exists(file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump([], f)

while True:
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            datalist = json.load(f)
        except json.JSONDecodeError:
            datalist = []

        if datalist:
            date_str = datalist[-1][0]["time"]
            date_obj = datetime.strptime(date_str, "%Y/%m/%d")
            next_date_obj = date_obj + timedelta(days=1)
            date_endpoint = next_date_obj.strftime("%Y/%m/%d")
        else:
            date_endpoint = date

    datalist.append(model.main(date_endpoint))

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(datalist, f, ensure_ascii=False, indent=2)

    time.sleep(20)
