import requests
from bs4 import BeautifulSoup

# 輸入網址
url = input("請輸入網址：")

# 發送 HTTP 請求
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})

# 解析 HTML
soup = BeautifulSoup(resp.text, "html.parser")

# 輸出解析後的完整 HTML 字串
print(soup.decode())