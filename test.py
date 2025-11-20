import requests

API_KEY = ""
url = "https://api.hume.ai/v0/models"

res = requests.get(url, headers={"Authorization": f"Bearer {API_KEY}"})
print(res.status_code)
print(res.text)