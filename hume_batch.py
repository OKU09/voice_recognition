import time
import requests
import os
import json

# ---- (1) APIキーの取得 ----
# 環境変数から取得（安全）
# API_KEY = os.environ.get("HUME_API_KEY")

# 実験用：直接書いても動く（ただし安全ではない）
API_KEY = ""   # <----ここに自身のAPIキーを書いてください！！！

BASE_URL = "https://api.hume.ai/v0/batch/jobs"
HEADERS = {"X-Hume-Api-Key": API_KEY}


# ---- (2) ジョブ送信（ローカルファイルをアップロード） ----
def submit_job_local(file_paths):
    files = []
    # 音声ファイルを添付
    for path in file_paths:
        files.append(('file', (os.path.basename(path), open(path, 'rb'), 'audio/mpeg')))

    # ←ここがポイント：'json'キーをfilesに含める
    payload = {
        "models": {"prosody": {}, "burst": {}},
        "notify": False
    }
    files.append(('json', (None, json.dumps(payload), 'application/json')))

    resp = requests.post(BASE_URL, headers=HEADERS, files=files)
    print("Response text:", resp.text)  # ←デバッグ出力
    resp.raise_for_status()

    job_id = resp.json()["job_id"]
    print("Submitted job:", job_id)
    return job_id

# ---- (3) ステータス確認 ----
def check_status(job_id):
    resp = requests.get(f"{BASE_URL}/{job_id}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()["state"]["status"]

# ---- (4) 結果取得 ----
def get_predictions(job_id):
    resp = requests.get(f"{BASE_URL}/{job_id}/predictions", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

# ---- (5) メイン ----
def main():
    # ローカルファイルを指定
    audio_files = ["g_24.mp3"]  # ←録音した音声ファイル名に変更！！

    job_id = submit_job_local(audio_files)

    # 完了待ち
    while True:
        status = check_status(job_id)
        print("Status:", status)
        if status == "COMPLETED":
            break
        elif status == "FAILED":
            raise RuntimeError("Job failed")
        time.sleep(5)

    results = get_predictions(job_id)
    print(json.dumps(results, indent=2, ensure_ascii=False))

    # 保存
    with open(f"results_{job_id}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
