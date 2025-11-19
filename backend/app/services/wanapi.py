import os
import wandb
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI
from dotenv import load_dotenv

app = FastAPI()

@app.get("/wandb-test")
def google_test():
    return {
        "WANDB_API_KEY": os.getenv("WANDB_API_KEY"),
        "WANDB_PROJECT_URL": os.getenv("WANDB_PROJECT_URL"),
    }

class Wand_DB():
    def __init__(self):
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
        self.WANDB_API_KEY = os.environ.get("WANDB_API_KEY") 
        self.WANDB_PROJECT_URL = os.environ.get("WANDB_PROJECT_URL")

        # self.WANDB_API_KEY = os.environ.get("WANDB_API_KEY") 
        # self.WANDB_PROJECT_URL = os.environ.get("WANDB_PROJECT_URL")
        self.is_ready = bool(self.WANDB_API_KEY and self.WANDB_PROJECT_URL)
        self.run_names_to_check = ["distant-silence-3", "trim-paper-2", "splendid-pine-1"]

    def get_chart_data(self, target_run):
        user_metrics = [k for k in target_run.summary.keys() if not k.startswith('_')]
        chart_results = []

        for metric in user_metrics:
            try:
                history_df = target_run.history(keys=[metric, "_step"])
                if not history_df.empty:
                    chart_results.append({
                        "metric_name": metric,
                        "chart_data": history_df[metric].tolist()
                    })
            except Exception:
                continue
        return chart_results

    def fetch_run_data(self, run_name):
        try:
            api = wandb.Api()
            runs = api.runs(self.WANDB_PROJECT_URL, filters={"display_name": run_name})
            if not runs:
                return []

            target_run = runs[0]
            chart_data_list = self.get_chart_data(target_run)
            return [{"run_name": run_name, **chart} for chart in chart_data_list]

        except wandb.errors.CommError as e:
            print(f"❌ W&B API 통신 오류: {e}")
        except Exception as e:
            print(f"❌ 예상치 못한 오류: {e}")
        return []

    def call_back(self):
        if not self.is_ready:
            print("API 키 또는 URL 오류로 인해 실행을 중단합니다.")
            return []

        all_runs_data = []

        # ThreadPoolExecutor로 병렬 처리
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self.fetch_run_data, run_name): run_name for run_name in self.run_names_to_check}
            for future in as_completed(futures):
                result = future.result()
                all_runs_data.extend(result)

        return all_runs_data
