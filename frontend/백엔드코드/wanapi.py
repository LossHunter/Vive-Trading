import os
from dotenv import load_dotenv
import pandas as pd
import json 
import wandb

class Wand_DB():
    def __init__(self):
        load_dotenv()
        self.WANDB_API_KEY = os.environ.get("WANDB_API_KEY") 

        if not self.WANDB_API_KEY:
            self.is_ready = False
        else:
            self.is_ready = True
        
        self.WANDB_PROJECT_URL = os.environ.get("WANDB_PROJECT_URL")
        if not self.WANDB_PROJECT_URL:
            self.is_ready = False
            
        self.run_names_to_check = ["distant-silence-3", "trim-paper-2", "splendid-pine-1"]

    def get_chart_data(self, target_run):
        all_metrics = list(target_run.summary.keys())
        user_metrics = [k for k in all_metrics if not k.startswith('_')]

        if not user_metrics:
            return []

        chart_results = []

        for metric_to_fetch in user_metrics:
            try:
                history_df = target_run.history(keys=[metric_to_fetch, "_step"])
                if not history_df.empty:
                    
                    metric_values = history_df[metric_to_fetch].tolist()
                    chart_results.append({
                        "metric_name": metric_to_fetch,
                        "chart_data": metric_values
                    })
            except Exception:
                continue

        return chart_results
    
    def call_back(self):
        if not self.is_ready:
            print("API 키 또는 URL 오류로 인해 실행을 중단합니다.")
            return

        api = wandb.Api()
        all_runs_data = []

        for run_name in self.run_names_to_check:
            print(f"--- 🔍 {run_name} 확인 중 ---")
            
            try:
                runs = api.runs(
                    f"{self.WANDB_PROJECT_URL}",
                    filters={"display_name": run_name} 
                )
                
                if not runs:
                    continue

                target_run = runs[0]
                chart_data_list = self.get_chart_data(target_run) 

                for chart in chart_data_list:
                    all_runs_data.append({
                        "run_name": run_name,
                        "metric_name": chart["metric_name"],
                        "chart_data": chart["chart_data"]
                    })
            
            except wandb.errors.CommError as e:
                print(f"❌ W&B API 통신 오류 발생: {e}")
            except Exception as e:
                print(f"❌ 예상치 못한 오류 발생: {e}")

        return all_runs_data

# wanapi = Wand_DB()
# all_runs_data = wanapi.call_back()

# for data in all_runs_data:
#     print(json.dumps(data, ensure_ascii=False, indent=4))

# print(len(all_runs_data))