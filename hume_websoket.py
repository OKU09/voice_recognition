import asyncio
import websockets
import base64
import json
import sounddevice as sd

# === (1) HumeのAPIキー ===
API_KEY = "flNbQ4RkpfsxlPJlqg0GLvKnb69pUepBtiwu5vYgoGmJZHnz"  # ←あなたの「Project API Key」をここに！

# === (2) WebSocketエンドポイント ===
HUME_WS_URL = "wss://api.hume.ai/v0/stream/models"

# === (3) 音声設定 ===
SAMPLE_RATE = 16000  # Hume推奨
CHUNK_DURATION = 0.5  # 秒
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)


async def stream_audio():
    """
    マイク入力をHume APIにストリーミングし、
    感情解析の結果をリアルタイムで受信する。
    """
    # WebSocket接続を開く
    async with websockets.connect(
        HUME_WS_URL,
        extra_headers={"Authorization": f"Bearer {API_KEY}.strip()"}
    ) as ws:
        print("Connected to Hume AI Real-time API")

        # モデルの設定を送信
        config = {
            "models": {
                "prosody": {},   # 声の抑揚・感情
                "burst": {},     # 音声の短い特徴
            }
        }
        await ws.send(json.dumps(config))
        print("Sent model configuration")

        loop = asyncio.get_running_loop()

        # 音声入力ストリームを開く
        def callback(indata, frames, time_info, status):
            if status:
                print(status)
            audio_bytes = indata.tobytes()
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            payload = json.dumps({"data": audio_b64})
            
            asyncio.run_coroutine_threadsafe(ws.send(payload), loop)

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=callback):
            print("Listening... Press Ctrl+C to stop.")

            # サーバーからのメッセージを逐次受信
            try:
                while True:
                    message = await ws.recv()
                    data = json.loads(message)

                    # 結果部分を表示
                    if "models" in data:
                        emotions = data["models"].get("prosody", {}).get("predictions", [])
                        if emotions:
                            print(json.dumps(emotions[-1], indent=2, ensure_ascii=False))
            except KeyboardInterrupt:
                print("\n Stopped streaming.")


if __name__ == "__main__":
    asyncio.run(stream_audio())
