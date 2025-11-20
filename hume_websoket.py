import asyncio
import websockets
import base64
import json
import sounddevice as sd
import numpy as np
import io
import wave
import sys

# === 設定 ===
API_KEY = ""
HUME_WS_URL = "wss://api.hume.ai/v0/stream/models"

DEVICE_ID = 1  # マイク番号
CHUNK_DURATION = 1.0  # 1秒ごとに区切る
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

async def stream_audio():
    loop = asyncio.get_running_loop()
    running = True
    segment_count = 0

    try:
        async with websockets.connect(
            HUME_WS_URL,
            extra_headers={"X-Hume-Api-Key": API_KEY}
        ) as ws:
            print("=== 接続成功 ===")
            print("------------------------------------------------")

            models_config = {
                "prosody": {}, 
                "burst": {},
            }

            def callback(indata, frames, time_info, status):
                if not running: return
                
                # 送信中の表示（JSON表示の邪魔にならないよう控えめに）
                # volume = np.linalg.norm(indata) / len(indata) * 1000
                # sys.stdout.write(".") 
                # sys.stdout.flush()

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
                                # 時間計算
                                begin_time = segment_count * CHUNK_DURATION
                                end_time = (segment_count + 1) * CHUNK_DURATION
                                segment_count += 1

                                emotions_raw = predictions[0]["emotions"]
                                
                                # スコア順にソートして、上位10個だけ取り出す
                                sorted_emotions = sorted(emotions_raw, key=lambda x: x["score"], reverse=True)
                                top_10_emotions = sorted_emotions[:10]

                                # 表示用のオブジェクトを作成
                                display_data = {
                                    "time": {
                                        "begin": round(begin_time, 1),
                                        "end": round(end_time, 1)
                                    },
                                    "emotions_top10": [
                                        {"name": e["name"], "score": round(e["score"], 5)} 
                                        for e in top_10_emotions
                                    ]
                                }

                                # JSONとして整形して表示
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
    try:
        asyncio.run(stream_audio())
    except KeyboardInterrupt:
        pass