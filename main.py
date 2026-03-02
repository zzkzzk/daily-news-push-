import requests
import os
import json
from datetime import datetime

NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

# =============================
# 新闻分类
# =============================
categories = [
    {'cn': '国际政治', 'q': '中国 OR China OR world politics OR geopolitics OR Taiwan OR Ukraine'},
    {'cn': '财经经济', 'q': '中国经济 OR China economy OR global market OR finance OR trade war'},
    {'cn': '科技前沿', 'q': '中国科技 OR AI China OR chip OR semiconductor OR quantum OR Huawei'},
    {'cn': '体育赛事', 'q': '中国体育 OR Olympics OR football OR basketball OR 奥运 OR 世界杯'},
    {'cn': '文化娱乐', 'q': '中国文化 OR entertainment OR movie OR music OR festival OR celebrity'},
    {'cn': '社会民生', 'q': '中国社会 OR education OR housing OR employment OR population OR 民生'},
    {'cn': '健康医疗', 'q': '中国医疗 OR health China OR cancer OR vaccine OR aging OR 疫情'},
    {'cn': '环境气候', 'q': '中国环境 OR climate change OR carbon OR renewable OR 碳中和 OR pollution'}
]

news_list = []
seen_links = set()

# =============================
# 获取新闻
# =============================
for cat in categories:
    url = "https://newsdata.io/api/1/latest"
    params = {
        'apikey': NEWSDATA_API_KEY,
        'q': cat['q'],
        'language': 'zh',
        'size': 5,
        'removeduplicate': '1'
    }

    try:
        resp = requests.get(url, params=params, timeout=20)
        data = resp.json()

        if data.get('status') != 'success':
            continue

        valid = 0
        for art in data.get('results', []):
            if valid >= 2:
                break

            link = art.get('link', '')
            if link in seen_links:
                continue
            seen_links.add(link)

            title = (art.get('title') or '').strip()
            desc = (art.get('description') or art.get('content') or '').strip()
            img_url = art.get('image_url', '')

            if len(title) < 10 or len(desc) < 40:
                continue

            news_list.append({
                'category': cat['cn'],
                'title': title,
                'desc': desc,
                'link': link,
                'img_url': img_url if img_url.startswith('https') else ''
            })

            valid += 1

    except Exception as e:
        print(f"获取失败: {e}")

print(f"收集到新闻：{len(news_list)} 条")

if not news_list:
    exit()

# =============================
# 单次批量调用智谱（深度内容版）
# =============================
def batch_zhipu(news_items):

    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = []
    for i, item in enumerate(news_items):
        payload.append({
            "id": i,
            "category": item["category"],
            "title": item["title"],
            "desc": item["desc"]
        })

    system_prompt = """
你是一位国际顶级报刊主编。

请为每条新闻生成：

official（≤220字权威摘要）
professional（220-280字，深度专业解析，两段，必须简体中文）
vernacular（180-220字，通俗易懂，两段，必须简体中文）

要求：
1. professional 必须有宏观背景 + 影响分析
2. vernacular 必须像高质量公众号深度解读
3. 不能空泛
4. 不能套话
5. 必须全部简体中文（除官方摘要可保留专有名词）

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

    r = requests.post(url, headers=headers, json=body, timeout=90)
    r.raise_for_status()

    content = r.json()["choices"][0]["message"]["content"]
    return json.loads(content)

analysis_list = batch_zhipu(news_list)

# =============================
# 高端报刊级 HTML 设计
# =============================
today = datetime.now().strftime('%Y年%m月%d日')

msg = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日新闻</title>
<style>
body {{
    margin:0;
    font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial;
    background:#0f172a;
    color:#111;
}}
.wrapper {{
    background:#ffffff;
    max-width:100%;
}}
.hero {{
    background:linear-gradient(135deg,#0f172a,#1e293b);
    color:white;
    padding:60px 24px 40px;
    text-align:center;
}}
.hero h1 {{
    margin:0;
    font-size:34px;
    letter-spacing:2px;
}}
.hero p {{
    opacity:0.8;
    margin-top:10px;
}}

.section {{
    padding:30px 22px;
}}

.category {{
    font-size:22px;
    font-weight:700;
    margin:30px 0 20px;
    border-left:5px solid #2563eb;
    padding-left:10px;
}}

.article {{
    margin-bottom:40px;
}}

.article img {{
    width:100%;
    border-radius:8px;
    margin-bottom:15px;
}}

.title {{
    font-size:20px;
    font-weight:700;
    margin-bottom:15px;
}}

.block {{
    margin:15px 0;
    line-height:1.9;
    font-size:15.5px;
}}

.label {{
    font-weight:700;
    color:#2563eb;
    display:block;
    margin-bottom:6px;
}}

.footer {{
    text-align:center;
    padding:25px;
    background:#f1f5f9;
    font-size:13px;
}}
</style>
</head>
<body>
<div class="wrapper">
<div class="hero">
<h1>GLOBAL DAILY BRIEF</h1>
<p>{today} · 深度精选</p>
</div>
<div class="section">
"""

current_cat = None

for item, analysis in zip(news_list, analysis_list):

    if item["category"] != current_cat:
        msg += f'<div class="category">{item["category"]}</div>'
        current_cat = item["category"]

    img_tag = f'<img src="{item["img_url"]}" onerror="this.style.display=\'none\'">' if item["img_url"] else ""

    msg += f"""
    <div class="article">
        {img_tag}
        <div class="title">{item["title"]}</div>

        <div class="block">
            <span class="label">官方摘要</span>
            {analysis['official']}
        </div>

        <div class="block">
            <span class="label">专业解析</span>
            {analysis['professional']}
        </div>

        <div class="block">
            <span class="label">白话解读</span>
            {analysis['vernacular']}
        </div>

        <div class="block">
            <a href="{item['link']}" target="_blank">阅读原文 →</a>
        </div>
    </div>
    """

msg += """
</div>
<div class="footer">
NewsData.io 聚合 · 智谱AI深度解析
</div>
</div>
</body>
</html>
"""

print("HTML长度：", len(msg))

# =============================
# PushPlus 推送
# =============================
push_url = "https://www.pushplus.plus/send"

payload = {
    "token": PUSHPLUS_TOKEN,
    "title": f"每日新闻 {today}",
    "content": msg,
    "template": "html"
}

r = requests.post(push_url, json=payload, timeout=40)
print("推送状态:", r.status_code)
print("返回:", r.text)

print("执行完成")
