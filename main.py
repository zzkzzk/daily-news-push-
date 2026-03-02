import requests
import os
import json
import re
import time
from datetime import datetime

NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN")

TARGET_PER_CATEGORY = 3
MAX_TOTAL = 24

categories = [
    {"cn": "国际政治", "q": "China geopolitics OR Taiwan OR Ukraine OR world politics"},
    {"cn": "财经经济", "q": "China economy OR market OR finance OR trade"},
    {"cn": "科技前沿", "q": "China AI OR chip OR semiconductor OR Huawei"},
    {"cn": "体育赛事", "q": "China sports OR Olympics OR football"},
    {"cn": "文化娱乐", "q": "China movie OR celebrity OR entertainment"},
    {"cn": "社会民生", "q": "China education OR housing OR society"},
    {"cn": "健康医疗", "q": "China health OR hospital OR vaccine"},
    {"cn": "环境气候", "q": "China climate OR carbon OR pollution"}
]

news_list = []
seen_links = set()

# ==============================
# 强化新闻抓取（多轮补齐机制）
# ==============================
for cat in categories:

    collected = 0
    page = 0

    while collected < TARGET_PER_CATEGORY and page < 3:

        try:
            resp = requests.get(
                "https://newsdata.io/api/1/latest",
                params={
                    "apikey": NEWSDATA_API_KEY,
                    "q": cat["q"],
                    "language": "zh",
                    "size": 10,
                    "page": page
                },
                timeout=25
            )

            data = resp.json()

            if data.get("status") != "success":
                break

            for art in data.get("results", []):

                if collected >= TARGET_PER_CATEGORY:
                    break

                link = art.get("link") or ""
                if not link or link in seen_links:
                    continue
                seen_links.add(link)

                title = (art.get("title") or "").strip()
                desc = (art.get("description") or art.get("content") or "").strip()

                if len(title) < 10 or len(desc) < 80:
                    continue

                img = art.get("image_url")
                if not isinstance(img, str) or not img.startswith("http"):
                    img = ""

                news_list.append({
                    "category": cat["cn"],
                    "title": title,
                    "desc": desc,
                    "link": link,
                    "img_url": img
                })

                collected += 1

            page += 1

        except Exception as e:
            print("抓取异常:", e)
            break

print("收集到新闻：", len(news_list))

if len(news_list) == 0:
    print("没有获取到新闻")
    exit()

# 控制最大总数
news_list = news_list[:MAX_TOTAL]

# ==============================
# 智谱单次批量调用（生产级容错）
# ==============================
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
你是一位世界级新闻深度主编。

为每条新闻生成：

official（150-220字）
professional（不少于250字，两段，简体中文）
vernacular（不少于200字，两段，简体中文）

必须全部简体中文。
只返回JSON数组。
"""

    body = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
        "temperature": 0.7,
        "max_tokens": 8000
    }

    for retry in range(3):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=120)
            r.raise_for_status()

            content = r.json()["choices"][0]["message"]["content"]
            content = re.sub(r"```json|```", "", content).strip()

            result = json.loads(content)

            safe = []
            for i in range(len(items)):
                if i < len(result) and isinstance(result[i], dict):
                    safe.append({
                        "official": result[i].get("official", "暂无摘要"),
                        "professional": result[i].get("professional", "暂无专业解析"),
                        "vernacular": result[i].get("vernacular", "暂无白话解读")
                    })
                else:
                    safe.append({
                        "official": "暂无摘要",
                        "professional": "暂无专业解析",
                        "vernacular": "暂无白话解读"
                    })

            return safe

        except Exception as e:
            print("智谱异常重试:", retry + 1, e)
            time.sleep(3)

    # 彻底失败兜底
    return [{
        "official": "暂无摘要",
        "professional": "暂无专业解析",
        "vernacular": "暂无白话解读"
    } for _ in items]


analysis_list = call_zhipu_batch(news_list)

# ==============================
# 产品级排版
# ==============================
today = datetime.now().strftime("%Y年%m月%d日")

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
    background:#f3f4f6;
}}
.header {{
    background:#111827;
    color:white;
    padding:40px 20px;
    text-align:center;
}}
.header h1 {{
    margin:0;
    font-size:30px;
}}
.container {{
    padding:20px;
}}
.card {{
    background:white;
    padding:22px;
    margin-bottom:28px;
    border-radius:14px;
    box-shadow:0 6px 20px rgba(0,0,0,0.06);
}}
.card img {{
    width:100%;
    border-radius:10px;
    margin-bottom:15px;
}}
.category {{
    font-size:14px;
    color:#2563eb;
    font-weight:600;
}}
.title {{
    font-size:20px;
    font-weight:700;
    margin:10px 0 15px;
}}
.section {{
    margin-top:14px;
    line-height:1.9;
    font-size:15.5px;
}}
.label {{
    font-weight:700;
    margin-bottom:6px;
    display:block;
}}
.footer {{
    text-align:center;
    padding:20px;
    font-size:13px;
    color:#666;
}}
</style>
</head>
<body>
<div class="header">
<h1>全球每日深度精选</h1>
<p>{today}</p>
</div>
<div class="container">
"""

for item, analysis in zip(news_list, analysis_list):

    img_html = f'<img src="{item["img_url"]}">' if item["img_url"] else ""

    html += f"""
    <div class="card">
        <div class="category">{item["category"]}</div>
        {img_html}
        <div class="title">{item["title"]}</div>

        <div class="section">
            <span class="label">官方摘要</span>
            {analysis["official"]}
        </div>

        <div class="section">
            <span class="label">专业解析</span>
            {analysis["professional"]}
        </div>

        <div class="section">
            <span class="label">白话解读</span>
            {analysis["vernacular"]}
        </div>

        <div class="section">
            <a href="{item["link"]}">阅读原文</a>
        </div>
    </div>
    """

html += """
</div>
<div class="footer">
NewsData 数据来源 · 智谱AI深度生成
</div>
</body>
</html>
"""

# ==============================
# PushPlus 推送
# ==============================
for i in range(3):
    try:
        r = requests.post(
            "https://www.pushplus.plus/send",
            json={
                "token": PUSHPLUS_TOKEN,
                "title": f"每日深度新闻 {today}",
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
        print("推送失败重试:", i + 1, e)
        time.sleep(3)

print("执行完成")
