import requests
import os
import json
import re
from datetime import datetime

NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

categories = [
    {'cn': '国际政治', 'q': 'China OR world politics OR geopolitics OR Taiwan OR Ukraine'},
    {'cn': '财经经济', 'q': 'China economy OR finance OR trade OR market'},
    {'cn': '科技前沿', 'q': 'China tech OR AI OR chip OR semiconductor OR Huawei'},
    {'cn': '体育赛事', 'q': 'China sports OR Olympics OR football'},
    {'cn': '文化娱乐', 'q': 'China entertainment OR movie OR celebrity'},
    {'cn': '社会民生', 'q': 'China society OR education OR housing'},
    {'cn': '健康医疗', 'q': 'China health OR vaccine OR hospital'},
    {'cn': '环境气候', 'q': 'China climate OR carbon OR pollution'}
]

news_list = []
seen_links = set()

# =============================
# 获取新闻（稳定版）
# =============================
for cat in categories:
    try:
        resp = requests.get(
            "https://newsdata.io/api/1/latest",
            params={
                'apikey': NEWSDATA_API_KEY,
                'q': cat['q'],
                'language': 'zh',
                'size': 5,
                'removeduplicate': '1'
            },
            timeout=20
        )

        data = resp.json()

        for art in data.get('results', [])[:2]:

            link = art.get('link') or ""
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            title = (art.get('title') or "").strip()
            desc = (art.get('description') or art.get('content') or "").strip()

            img_url = art.get('image_url')
            if not isinstance(img_url, str):
                img_url = ""
            if not img_url.startswith("http"):
                img_url = ""

            if len(title) < 8 or len(desc) < 40:
                continue

            news_list.append({
                "category": cat["cn"],
                "title": title,
                "desc": desc,
                "link": link,
                "img_url": img_url
            })

    except Exception as e:
        print("获取失败:", e)

print("收集到新闻：", len(news_list))

if not news_list:
    exit()

# =============================
# 智谱批量调用（超稳定清洗版）
# =============================
def call_zhipu_batch(items):

    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = []
    for i, item in enumerate(items):
        payload.append({
            "id": i,
            "title": item["title"],
            "desc": item["desc"]
        })

    system_prompt = """
请为每条新闻生成：

official（≤220字）
professional（不少于220字，两段，简体中文）
vernacular（不少于180字，两段，简体中文）

只返回JSON数组。
"""

    body = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
        "temperature": 0.7,
        "max_tokens": 7000
    }

    r = requests.post(url, headers=headers, json=body, timeout=120)
    r.raise_for_status()

    content = r.json()["choices"][0]["message"]["content"]

    # 去除 ```json 包裹
    content = re.sub(r"```json|```", "", content).strip()

    try:
        result = json.loads(content)
    except:
        print("JSON解析失败，使用空结构")
        result = []

    # 强制字段补全
    safe_list = []
    for i in range(len(items)):
        if i < len(result) and isinstance(result[i], dict):
            safe_list.append({
                "official": result[i].get("official", "暂无摘要"),
                "professional": result[i].get("professional", "暂无专业解析"),
                "vernacular": result[i].get("vernacular", "暂无白话解读")
            })
        else:
            safe_list.append({
                "official": "暂无摘要",
                "professional": "暂无专业解析",
                "vernacular": "暂无白话解读"
            })

    return safe_list


analysis_list = call_zhipu_batch(news_list)

# =============================
# 高级排版
# =============================
today = datetime.now().strftime('%Y年%m月%d日')

html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{
    margin:0;
    font-family:-apple-system,BlinkMacSystemFont;
    background:#f5f7fa;
}}
.container {{
    max-width:100%;
    padding:20px;
}}
.title {{
    font-size:28px;
    font-weight:700;
    margin-bottom:30px;
}}
.card {{
    background:white;
    padding:20px;
    margin-bottom:30px;
    border-radius:12px;
    box-shadow:0 5px 15px rgba(0,0,0,0.05);
}}
.card img {{
    width:100%;
    border-radius:8px;
    margin-bottom:15px;
}}
.section-title {{
    font-weight:700;
    margin-top:15px;
}}
</style>
</head>
<body>
<div class="container">
<div class="title">每日深度新闻 · {today}</div>
"""

for item, analysis in zip(news_list, analysis_list):

    img_html = f'<img src="{item["img_url"]}">' if item["img_url"] else ""

    html += f"""
    <div class="card">
        {img_html}
        <h3>{item['title']}</h3>

        <div class="section-title">官方摘要</div>
        <p>{analysis['official']}</p>

        <div class="section-title">专业解析</div>
        <p>{analysis['professional']}</p>

        <div class="section-title">白话解读</div>
        <p>{analysis['vernacular']}</p>

        <a href="{item['link']}">阅读原文</a>
    </div>
    """

html += "</div></body></html>"

# =============================
# PushPlus 推送（带重试）
# =============================
for i in range(3):
    try:
        r = requests.post(
            "https://www.pushplus.plus/send",
            json={
                "token": PUSHPLUS_TOKEN,
                "title": f"每日新闻 {today}",
                "content": html,
                "template": "html"
            },
            timeout=40
        )

        print("推送状态:", r.status_code)
        print(r.text)

        if r.status_code == 200:
            break

    except Exception as e:
        print(f"推送失败，重试 {i+1}/3 次...", e)
