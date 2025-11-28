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

# === 設定 ===
API_KEY = "" # APIキー
HUME_WS_URL = "wss://api.hume.ai/v0/stream/models"

DEVICE_ID = 1  # マイク番号
CHUNK_DURATION = 1.0  # 1秒ごとに区切る
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

# === Flask API 設定 ===
app = Flask(__name__)

# 最新の感情データを保存するグローバル変数
latest_emotion_data = {"status": "waiting_for_audio", "message": "まだ音声データを受信していません"}

@app.route("/emotion/latest")
def get_latest_emotion():
    """最新の感情データをJSONで返すAPI"""
    return jsonify(latest_emotion_data)

def run_flask():
    """Flaskサーバーを起動する関数"""
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# === ターゲット感情（指定順序） ===
# Anger, Disgust, Fear, Happiness, Sadness, Surprise, Neutral
TARGET_EMOTIONS = [
    "Anger", "Disgust", "Fear", "Happiness", "Sadness", "Surprise", "Neutral"
]

# === 感情マッピング定義 ===
# Joy -> Happiness
# Trust, Anticipation -> Neutral (または文脈によりHappiness等へ統合)
# 以前の「3要素は-0.2して...」の結果をベースに、7感情へ再配分しています。
EMOTION_MAP = {
    "Admiration": {"Neutral":1.0}, # Trust -> Neutral
    "Adoration": {"Neutral":1.0}, # Trust -> Neutral
    "Aesthetic Appreciation": {"Happiness":0.2, "Surprise":0.1, "Neutral":0.7}, # Joy->Happy, Ant->Neu
    "Amusement": {"Happiness":1.0}, # Joy->Happy
    "Anger": {"Anger":1.0},
    "Anxiety": {"Fear":0.5, "Neutral":0.5}, # Ant->Neu
    "Awe": {"Fear":0.5, "Surprise":0.5},
    "Awkwardness": {"Fear":1.0},
    "Boredom": {"Disgust":0.5, "Anger":0.5},
    "Calmness": {"Fear":0.2, "Sadness":0.1, "Neutral":0.7}, # Ant->Neu
    "Concentration": {"Neutral":1.0}, # Ant->Neu
    "Confusion": {"Fear":0.5, "Surprise":0.5},
    "Contemplation": {"Neutral":1.0}, # Trust+Ant -> Neu
    "Contentment": {"Happiness":1.0}, # Joy->Happy
    "Craving": {"Neutral":1.0}, # Ant->Neu
    "Desire": {"Neutral":1.0}, # Ant->Neu
    "Determination": {"Happiness":0.5, "Neutral":0.5}, # Joy->Happy, Ant->Neu
    "Disappointment": {"Surprise":0.5, "Sadness":0.5},
    "Disgust": {"Disgust":1.0},
    "Distress": {"Sadness":0.5, "Disgust":0.5},
    "Doubt": {"Fear":0.1, "Disgust":0.2, "Neutral":0.7}, # Ant->Neu
    "Embarrassment": {"Fear":0.5, "Disgust":0.5},
    "Empathic Pain": {"Sadness":0.5, "Disgust":0.5},
    "Entrancement": {"Happiness":0.1, "Neutral":0.9}, # Joy->Happy, Trust+Ant -> Neu
    "Envy": {"Sadness":0.5, "Anger":0.5},
    "Excitement": {"Happiness":1.0}, # Joy->Happy
    "Fear": {"Fear":1.0},
    "Guilt": {"Happiness":0.5, "Fear":0.5}, # Joy->Happy
    "Horror": {"Fear":1.0},
    "Interest": {"Happiness":0.5, "Neutral":0.5}, # Joy->Happy, Ant->Neu
    "Joy": {"Happiness":1.0}, # Joy->Happy
    "Love": {"Happiness":0.5, "Neutral":0.5}, # Joy->Happy, Trust->Neu
    "Nostalgia": {"Neutral":0.5, "Sadness":0.5}, # Trust->Neu
    "Pain": {"Fear":0.5, "Disgust":0.5},
    "Pride": {"Anger":0.5, "Happiness":0.5}, # Joy->Happy
    "Realization": {"Happiness":0.1, "Neutral":0.9}, # Joy->Happy, Trust+Ant -> Neu
    "Relief": {"Neutral":1.0}, # Trust->Neu
    "Romance": {"Happiness":1.0}, # Joy->Happy
    "Sadness": {"Sadness":1.0},
    "Satisfaction": {"Happiness":1.0}, # Joy->Happy
    "Shame": {"Fear":0.5, "Disgust":0.5},
    "Surprise (negative)": {"Surprise":1.0},
    "Surprise (positive)": {"Surprise":1.0},
    "Sympathy": {"Surprise":0.5, "Sadness":0.5},
    "Tiredness": {"Sadness":1.0},
    "Triumph": {"Happiness":1.0}, # Joy->Happy
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
                                # 指定の7感情の入れ物を用意
                                emotion_scores = {k: 0.0 for k in TARGET_EMOTIONS}

                                for hume_emotion in emotions_raw:
                                    name = hume_emotion["name"]
                                    score = hume_emotion["score"]

                                    if name in EMOTION_MAP:
                                        mapping = EMOTION_MAP[name]
                                        for target_name, weight in mapping.items():
                                            if target_name in emotion_scores:
                                                emotion_scores[target_name] += score * weight

                                # --- パーセンテージ計算 ---
                                total_score = sum(emotion_scores.values())
                                if total_score == 0:
                                    total_score = 1.0 

                                # 表示用データ作成（固定順序）
                                # 指定された順序でリストを作成します
                                formatted_emotions = [
                                    {
                                        "name": name,
                                        "percent": f"{round((emotion_scores[name] / total_score) * 100, 1)}%"
                                    }
                                    for name in TARGET_EMOTIONS
                                ]

                                display_data = {
                                    "time": {
                                        "begin": round(segment_count * CHUNK_DURATION, 1),
                                        "end": round((segment_count + 1) * CHUNK_DURATION, 1)
                                    },
                                    "emotions": formatted_emotions
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