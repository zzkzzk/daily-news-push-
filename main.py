import requests
import os
import time
import json
from datetime import datetime

# =============================
# 环境变量
# =============================
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

        if data.get('status') != 'success' or not data.get('results'):
            continue

        valid_count = 0
        for art in data['results']:
            if valid_count >= 2:
                break

            link = art.get('link', '')
            if link in seen_links:
                continue
            seen_links.add(link)

            title = (art.get('title') or '').strip()
            desc = (art.get('description') or art.get('content') or '').strip()
            img_url = art.get('image_url', '')

            if len(title) < 10 or len(desc) < 40 or 'http' not in link:
                continue

            if len(title) > 80:
                title = title[:78] + '…'

            news_list.append({
                'category': cat['cn'],
                'title': title,
                'desc': desc[:260],
                'link': link,
                'img_url': img_url if img_url.startswith('https') else '',
                'lang': art.get('language', 'zh')
            })

            valid_count += 1

    except Exception as e:
        print(f"[{cat['cn']}] 获取失败: {e}")

print(f"收集到新闻：{len(news_list)} 条")

if not news_list:
    print("没有获取到新闻，程序终止")
    exit()

# =============================
# 单次批量调用智谱（强制简体）
# =============================
def batch_zhipu(news_items):

    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }

    news_payload = []
    for idx, item in enumerate(news_items):
        news_payload.append({
            "id": idx,
            "category": item["category"],
            "title": item["title"],
            "desc": item["desc"]
        })

    system_prompt = """
你是一位资深中文报纸副总编辑。

我会给你一个JSON数组，每个元素是一条新闻。

请为每条新闻生成三个字段：
official  （≤160字摘要，可保留原有专有名词）
professional（110-130字，两段，必须全部使用简体中文）
vernacular（90-110字，两段，必须全部使用简体中文）

除official外，其余部分必须严格使用简体中文，不允许出现繁体字。

必须返回标准JSON数组，不允许解释，不允许markdown，不允许额外文字。
"""

    body = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(news_payload, ensure_ascii=False)}
        ],
        "temperature": 0.6,
        "max_tokens": 4000
    }

    response = requests.post(url, headers=headers, json=body, timeout=60)
    response.raise_for_status()

    result = response.json()
    content = result["choices"][0]["message"]["content"].strip()

    return json.loads(content)

print("开始批量调用智谱…")
analysis_list = batch_zhipu(news_list)
print("智谱返回完成")

# =============================
# HTML 构建（全宽手机优化）
# =============================
today = datetime.now().strftime('%Y年%m月%d日')

msg = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日新闻早报 {today}</title>
<style>
body {{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto;
    background:#f3f4f6;
    margin:0;
    padding:8px 6px;   /* 仅保留轻微边距 */
}}
.container {{
    width:100%;
    max-width:100%;
    margin:0 auto;
    background:#fff;
    border-radius:12px;
    overflow:hidden;
}}
.header {{
    background:linear-gradient(135deg,#1d4ed8,#60a5fa);
    color:white;
    padding:36px 20px 20px;
    text-align:center;
}}
.content {{
    padding:16px;
}}
h2 {{
    font-size:20px;
    margin:26px 0 14px;
    border-left:4px solid #3b82f6;
    padding-left:8px;
}}
.card {{
    border:1px solid #e5e7eb;
    border-radius:10px;
    margin-bottom:20px;
    overflow:hidden;
}}
.card img {{
    width:100%;
    height:auto;
    display:block;
}}
.card-body {{
    padding:18px;
}}
.title {{
    font-size:18px;
    font-weight:700;
    margin-bottom:12px;
}}
.section {{
    font-size:14.5px;
    margin:12px 0;
    line-height:1.7;
}}
.link {{
    text-align:right;
    margin-top:10px;
    font-size:14px;
}}
.footer {{
    background:#f1f5f9;
    padding:16px;
    text-align:center;
    font-size:13px;
}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>每日新闻早报</h1>
<div>{today}</div>
</div>
<div class="content">
"""

current_cat = None

for item, analysis in zip(news_list, analysis_list):

    if item['category'] != current_cat:
        msg += f"<h2>{item['category']}</h2>"
        current_cat = item['category']

    img_tag = ""
    if item['img_url']:
        img_tag = f'<img src="{item["img_url"]}" alt="配图" onerror="this.style.display=\'none\';">'

    msg += f"""
    <div class="card">
        {img_tag}
        <div class="card-body">
            <div class="title">{item['title']}</div>
            <div class="section"><strong>官方摘要：</strong><br>{analysis['official']}</div>
            <div class="section"><strong>专业解析：</strong><br>{analysis['professional']}</div>
            <div class="section"><strong>白话解读：</strong><br>{analysis['vernacular']}</div>
            <div class="link"><a href="{item['link']}" target="_blank">阅读原文 →</a></div>
        </div>
    </div>
    """

msg += """
</div>
<div class="footer">
来源：NewsData.io 聚合
</div>
</div>
</body>
</html>
"""

print(f"HTML 内容约 {len(msg.encode('utf-8'))/1024:.1f} KB")

# =============================
# PushPlus 推送
# =============================
push_url = "https://www.pushplus.plus/send"

payload = {
    "token": PUSHPLUS_TOKEN,
    "title": f"每日新闻早报 {today}",
    "content": msg,
    "template": "html"
}

r = requests.post(push_url, json=payload, timeout=30)
print("推送状态:", r.status_code)
print("返回:", r.text)

print("执行完成")
