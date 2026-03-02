import requests
import os
import json
import re
import time
from datetime import datetime

NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN")

TARGET_TOTAL = 15
news_list = []
seen_links = set()

# =========================
# 多策略抓取
# =========================
queries = [
    "China",
    "中国",
    "world",
    "economy",
    "technology",
    "politics",
    "finance",
    "AI",
    "market"
]

for q in queries:

    if len(news_list) >= TARGET_TOTAL:
        break

    try:
        resp = requests.get(
            "https://newsdata.io/api/1/latest",
            params={
                "apikey": NEWSDATA_API_KEY,
                "q": q,
                "size": 10
            },
            timeout=20
        )

        data = resp.json()

        if data.get("status") != "success":
            print("API状态异常:", data)
            continue

        for art in data.get("results", []):

            if len(news_list) >= TARGET_TOTAL:
                break

            link = art.get("link") or ""
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            title = (art.get("title") or "").strip()
            desc = (art.get("description") or art.get("content") or "").strip()

            if len(title) < 6:
                continue

            img = art.get("image_url")
            if not isinstance(img, str) or not img.startswith("http"):
                img = ""

            news_list.append({
                "category": "综合新闻",
                "title": title,
                "desc": desc if desc else title,
                "link": link,
                "img_url": img
            })

    except Exception as e:
        print("抓取异常:", e)

print("收集到新闻：", len(news_list))

# 如果仍然没有新闻，使用 fallback 查询
if len(news_list) == 0:
    print("启动fallback策略")

    resp = requests.get(
        "https://newsdata.io/api/1/latest",
        params={
            "apikey": NEWSDATA_API_KEY,
            "size": 15
        },
        timeout=20
    )

    data = resp.json()
    for art in data.get("results", []):

        link = art.get("link") or ""
        if not link:
            continue

        news_list.append({
            "category": "今日要闻",
            "title": art.get("title") or "无标题",
            "desc": art.get("description") or "",
            "link": link,
            "img_url": art.get("image_url") or ""
        })

print("最终新闻数量：", len(news_list))

if len(news_list) == 0:
    print("NewsData今日无可用数据，可能额度耗尽")
    exit()

# =========================
# 智谱批量处理
# =========================
def call_zhipu_batch(items):

    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = [
        {"id": i, "title": item["title"], "desc": item["desc"]}
        for i, item in enumerate(items)
    ]

    body = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content":
             "为每条新闻生成 official(150字)、professional(不少于250字)、vernacular(不少于200字)。全部简体中文。返回JSON数组。"},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
        "temperature": 0.7,
        "max_tokens": 8000
    }

    try:
        r = requests.post(url, headers=headers, json=body, timeout=120)
        r.raise_for_status()

        content = r.json()["choices"][0]["message"]["content"]
        content = re.sub(r"```json|```", "", content).strip()

        return json.loads(content)

    except Exception as e:
        print("智谱异常:", e)

    return [{
        "official": "暂无摘要",
        "professional": "暂无专业解析",
        "vernacular": "暂无白话解读"
    } for _ in items]


analysis_list = call_zhipu_batch(news_list)

# =========================
# 简洁产品排版
# =========================
today = datetime.now().strftime("%Y年%m月%d日")

html = f"<h2>每日新闻 {today}</h2>"

for item, analysis in zip(news_list, analysis_list):

    html += f"""
    <hr>
    <h3>{item['title']}</h3>
    <p><b>官方摘要：</b>{analysis.get('official','')}</p>
    <p><b>专业解析：</b>{analysis.get('professional','')}</p>
    <p><b>白话解读：</b>{analysis.get('vernacular','')}</p>
    <p><a href="{item['link']}">阅读原文</a></p>
    """

# =========================
# 推送
# =========================
requests.post(
    "https://www.pushplus.plus/send",
    json={
        "token": PUSHPLUS_TOKEN,
        "title": f"每日新闻 {today}",
        "content": html,
        "template": "html"
    }
)

print("执行完成")
