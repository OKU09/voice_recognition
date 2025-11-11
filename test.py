import asyncio
import websockets

API_KEY = "あなたのAPIキー"
url = "wss://api.hume.ai/v0/stream/prosody"

async def test():
    try:
        async with websockets.connect(
            url,
            extra_headers={"Authorization": f"Bearer {API_KEY.strip()}"}
        ) as ws:
            print("✅ 接続成功！")
    except Exception as e:
        print("❌ 接続失敗:", e)

asyncio.run(test())

