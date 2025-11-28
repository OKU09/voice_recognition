import asyncio
import websockets
import base64
import json
import sounddevice as sd
import numpy as np
import io
import wave
from flask import Flask, jsonify
import threading

<<<<<<< HEAD
# === (1) HumeのAPIキー ===
API_KEY = ""  # ←あなたの「Project API Key」をここに！
=======
# === 設定 ===
API_KEY = "1D46K9RzoijBjfFj3fPlTM82CmexgJ4Yk45GHsMIrGS4J0sU" # そのまま使用します
HUME_WS_URL = "wss://api.hume.ai/v0/stream/models"
>>>>>>> dev

DEVICE_ID = 1  # マイク番号
CHUNK_DURATION = 1.0  # 1秒ごとに区切る
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

# === Flask API 設定 ===
app = Flask(__name__)

# 最新の感情データを保存するグローバル変数（スレッド間で共有）
# 初期値を入れておくと、サーバー起動確認がしやすくなります
latest_emotion_data = {"status": "waiting_for_audio", "message": "まだ音声データを受信していません"}

@app.route("/emotion/latest")
def get_latest_emotion():
    """最新の感情データをJSONで返すAPI"""
    return jsonify(latest_emotion_data)

def run_flask():
    """Flaskサーバーを起動する関数"""
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

# === プルチックの基本8感情 ===
PLUTCHIK_EMOTIONS = [
    "Joy", "Trust", "Fear", "Surprise", 
    "Sadness", "Disgust", "Anger", "Anticipation"
]

EMOTION_MAP = {
    "Admiration": {"Trust":1.0},
    "Adoration": {"Trust":1.0},
    "Aesthetic Appreciation": {"Joy":0.4, "Surprise":0.3, "Anticipation":0.3},
    "Amusement": {"Joy":1.0},
    "Anger": {"Anger":1.0},
    "Anxiety": {"Fear":0.5, "Anticipation":0.5},
    "Awe": {"Fear":0.5, "Surprise":0.5},
    "Awkwardness": {"Fear":1.0},
    "Boredom": {"Disgust":0.5, "Anger":0.5},
    "Calmness": {"Fear":0.4, "Sadness":0.3, "Anticipation":0.3},
    "Concentration": {"Anticipation":1.0},
    "Confusion": {"Fear":0.5, "Surprise":0.5},
    "Contemplation": {"Trust":0.5, "Anticipation":0.5},
    "Contentment": {"Joy":1.0},
    "Craving": {"Anticipation":1.0},
    "Desire": {"Anticipation":1.0},
    "Determination": {"Joy":0.5, "Anticipation":0.5},
    "Disappointment": {"Surprise":0.5, "Sadness":0.5},
    "Disgust": {"Disgust":1.0},
    "Distress": {"Sadness":0.5, "Disgust":0.5},
    "Doubt": {"Fear":0.3, "Disgust":0.4, "Anticipation":0.3},
    "Embarrassment": {"Fear":0.5, "Disgust":0.5},
    "Empathic Pain": {"Sadness":0.5, "Disgust":0.5},
    "Entrancement": {"Joy":0.3, "Trust":0.4, "Anticipation":0.3},
    "Envy": {"Sadness":0.5, "Anger":0.5},
    "Excitement": {"Joy":1.0},
    "Fear": {"Fear":1.0},
    "Guilt": {"Joy":0.5, "Fear":0.5},
    "Horror": {"Fear":1.0},
    "Interest": {"Joy":0.5, "Anticipation":0.5},
    "Joy": {"Joy":1.0},
    "Love": {"Joy":0.5, "Trust":0.5},
    "Nostalgia": {"Trust":0.5, "Sadness":0.5},
    "Pain": {"Fear":0.5, "Disgust":0.5},
    "Pride": {"Anger":0.5, "Joy":0.5},
    "Realization": {"Joy":0.3, "Trust":0.3, "Anticipation":0.4},
    "Relief": {"Trust":1.0},
    "Romance": {"Joy":1.0},
    "Sadness": {"Sadness":1.0},
    "Satisfaction": {"Joy":1.0},
    "Shame": {"Fear":0.5, "Disgust":0.5},
    "Surprise (negative)": {"Surprise":1.0},
    "Surprise (positive)": {"Surprise":1.0},
    "Sympathy": {"Surprise":0.5, "Sadness":0.5},
    "Tiredness": {"Sadness":1.0},
    "Triumph": {"Joy":1.0},
}

async def stream_audio():
    # 【重要】関数内でグローバル変数を書き換えるためにこの宣言が必須です
    global latest_emotion_data
    
    loop = asyncio.get_running_loop()
    running = True
    segment_count = 0

    try:
        async with websockets.connect(
            HUME_WS_URL,
            extra_headers={"X-Hume-Api-Key": API_KEY}
        ) as ws:
            print("=== 接続成功 ===")
            print("APIサーバー: http://localhost:5000/emotion/latest")
            print("------------------------------------------------")

            models_config = {
                "prosody": {}, 
                "burst": {},
            }

            def callback(indata, frames, time_info, status):
                if not running: return

                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(SAMPLE_RATE)
                    wav_file.writeframes(indata.tobytes())
                
                wav_bytes = wav_buffer.getvalue()
                audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
                
                payload = json.dumps({"data": audio_b64, "models": models_config})
                try:
                    asyncio.run_coroutine_threadsafe(ws.send(payload), loop)
                except RuntimeError:
                    pass

            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                device=DEVICE_ID,
                callback=callback
            ):
                while running:
                    try:
                        message = await ws.recv()
                        data = json.loads(message)

                        if "error" in data:
                            print(f"\nError: {data['error']}")
                            continue

                        # === ターミナル表示処理 ===
                        if "prosody" in data:
                            predictions = data["prosody"].get("predictions", [])
                            if predictions:
                                emotions_raw = predictions[0]["emotions"]
                                
                                # --- 集計処理開始 ---
                                plutchik_scores = {k: 0.0 for k in PLUTCHIK_EMOTIONS}

                                for hume_emotion in emotions_raw:
                                    name = hume_emotion["name"]
                                    score = hume_emotion["score"]

                                    if name in EMOTION_MAP:
                                        mapping = EMOTION_MAP[name]
                                        for p_name, weight in mapping.items():
                                            plutchik_scores[p_name] += score * weight

                                # --- パーセンテージ計算 ---
                                total_score = sum(plutchik_scores.values())
                                if total_score == 0:
                                    total_score = 1.0 

                                # 表示用データ作成（降順ソート）
                                sorted_plutchik = sorted(
                                    plutchik_scores.items(), 
                                    key=lambda x: x[1], 
                                    reverse=True
                                )

                                display_data = {
                                    "time": {
                                        "begin": round(segment_count * CHUNK_DURATION, 1),
                                        "end": round((segment_count + 1) * CHUNK_DURATION, 1)
                                    },
                                    "plutchik_emotions": [
                                        {
                                            "name": name,
                                            "percent": f"{round((score / total_score) * 100, 1)}%"
                                        } 
                                        for name, score in sorted_plutchik
                                    ]
                                }

                                # 【更新】グローバル変数を更新
                                latest_emotion_data = display_data
                                
                                segment_count += 1

                                # コンソール確認用
                                print("\n" + json.dumps(display_data, indent=2, ensure_ascii=False))

                    except websockets.exceptions.ConnectionClosed:
                        print("\nConnection closed by server.")
                        break

    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        running = False
        print("\n終了しました")

if __name__ == "__main__":
    # Flaskを別スレッドで起動
    api_thread = threading.Thread(target=run_flask)
    api_thread.daemon = True
    api_thread.start()
    try:
        asyncio.run(stream_audio())
    except KeyboardInterrupt:
        pass