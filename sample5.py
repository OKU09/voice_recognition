import requests
import time

while True:
    try:
        res = requests.get("http://localhost:5000/emotion/latest").json()
        print("最新の感情値:", res)
    except Exception as e:
        print("取得失敗:", e)

    time.sleep(0.5)