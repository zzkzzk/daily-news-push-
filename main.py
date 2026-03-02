import requests
import os
import json
import re
from datetime import datetime

# =============================
# 环境变量
# =============================
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

# =============================
# 新闻分类（main逻辑，均衡专业）
# =============================
categories = [
    {'cn': '国际政治', 'q': '中国 OR China OR world politics OR geopolitics OR Taiwan OR Ukraine OR 中美关系'},
    {'cn': '财经经济', 'q': '中国经济 OR China economy OR global market OR finance OR trade OR 股市 OR inflation'},
    {'cn': '科技前沿', 'q': 'AI OR 人工智能 OR chip OR semiconductor OR Huawei OR 量子 OR 新能源'},
    {'cn': '社会民生', 'q': '中国社会 OR education OR housing OR employment OR population OR 民生'},
    {'cn': '文化娱乐', 'q': '中国文化 OR entertainment OR movie OR music OR celebrity OR 奥运'},
    {'cn': '健康环境', 'q': 'health China OR climate change OR carbon OR renewable OR 碳中和 OR pollution OR 医疗'},
]

news_list = []
seen_links = set()

# =============================
# 获取新闻（main的图片+分类逻辑）
# =============================
print("开始抓取新闻...")
for cat in categories:
    if len(news_list) >= 18:
        break

    url = "https://newsdata.io/api/1/latest"
    params = {
        'apikey': NEWSDATA_API_KEY,
        'q': cat['q'],
        'language': 'zh',
        'size': 7,
        'removeduplicate': '1'
    }

    try:
        resp = requests.get(url, params=params, timeout=25)
        data = resp.json()

        if data.get('status') != 'success' or not data.get('results'):
            continue

        valid_count = 0
        for art in data['results']:
            if valid_count >= 3 or len(news_list) >= 18:
                break

            link = art.get('link', '')
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            title = (art.get('title') or '').strip()
            desc = (art.get('description') or art.get('content') or '').strip()
            img_url = art.get('image_url', '')

            if len(title) < 8 or len(desc) < 35 or 'http' not in link:
                continue

            if len(title) > 88:
                title = title[:85] + '…'

            news_list.append({
                'category': cat['cn'],
                'title': title,
                'desc': desc[:300],
                'link': link,
                'img_url': img_url if isinstance(img_url, str) and img_url.startswith('http') else ''
            })

            valid_count += 1

    except Exception as e:
        print(f"[{cat['cn']}] 获取失败: {e}")

print(f"成功收集 {len(news_list)} 条新闻")

# 02风格的fallback
if len(news_list) < 5:
    print("新闻过少，启动02 fallback...")
    try:
        resp = requests.get(
            "https://newsdata.io/api/1/latest",
            params={"apikey": NEWSDATA_API_KEY, "size": 15},
            timeout=20
        )
        data = resp.json()
        for art in data.get("results", [])[:8]:
            link = art.get("link") or ""
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            title = (art.get("title") or "无标题").strip()
            desc = (art.get("description") or "").strip()
            news_list.append({
                'category': '今日要闻',
                'title': title[:85] + '…' if len(title) > 85 else title,
                'desc': desc[:300],
                'link': link,
                'img_url': art.get("image_url") or ""
            })
    except Exception as e:
        print("fallback失败:", e)

if not news_list:
    print("未能获取任何新闻，退出")
    exit()

# =============================
# 智谱批量处理（02的丰富文字风格）
# =============================
def batch_zhipu(items):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = [
        {"id": i, "category": item["category"], "title": item["title"], "desc": item["desc"]}
        for i, item in enumerate(items)
    ]

    system_prompt = """你是一位资深中文报纸副总编辑。

为每条新闻生成三个字段（全部简体中文）：
- official：约150字高质量官方摘要（客观中性，可保留专有名词）
- professional：不少于250字专业深度解析（分2-3段，带背景、影响、趋势分析）
- vernacular：不少于200字生动白话解读（分2段，像给朋友聊天一样通俗易懂）

必须返回标准JSON数组，不要任何解释、markdown或额外文字。"""

    body = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
        "temperature": 0.65,
        "max_tokens": 8500
    }

    try:
        r = requests.post(url, headers=headers, json=body, timeout=130)
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


print("调用智谱生成丰富解读...")
analysis_list = batch_zhipu(news_list)

# =============================
# HTML构建（02的简洁线性排版 + main的图片逻辑）
# =============================
today = datetime.now().strftime('%Y年%m月%d日')

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日新闻早报 {today}</title>
<style>
    body {{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9fa;margin:0;padding:10px 8px;line-height:1.75;}}
    .container {{max-width:100%;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.07);}}
    .header {{background:linear-gradient(135deg,#1e40af,#3b82f6);color:white;padding:42px 20px 26px;text-align:center;}}
    .header h1 {{margin:0;font-size:27px;}}
    .date {{font-size:15.5px;opacity:0.95;margin-top:8px;}}
    .content {{padding:20px 18px;}}
    .news-item {{margin-bottom:38px;}}
    .title {{font-size:20px;font-weight:700;color:#1e3a8a;margin:18px 0 14px;line-height:1.45;}}
    .img-container {{margin:14px -18px 20px -18px;}}
    .img-container img {{width:100%;height:auto;display:block;border-radius:10px;}}
    .section {{margin:17px 0;font-size:15.4px;}}
    .section strong {{color:#1e40af;}}
    .link {{text-align:right;margin-top:14px;}}
    hr {{border:none;border-top:1px solid #e5e7eb;margin:34px 0 28px;}}
    .footer {{background:#f1f5f9;padding:22px;text-align:center;font-size:13.5px;color:#64748b;}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>每日新闻早报</h1>
<div class="date">{today}</div>
</div>
<div class="content">
"""

for item, analysis in zip(news_list, analysis_list):
    img_html = ""
    if item.get('img_url'):
        img_html = f'<div class="img-container"><img src="{item["img_url"]}" alt="配图"></div>'

    html += f"""
    <div class="news-item">
        {img_html}
        <div class="title">{item['title']}</div>
        
        <div class="section"><strong>官方摘要：</strong><br>{analysis.get('official','暂无')}</div>
        <div class="section"><strong>专业解析：</strong><br>{analysis.get('professional','暂无')}</div>
        <div class="section"><strong>白话解读：</strong><br>{analysis.get('vernacular','暂无')}</div>
        
        <div class="link"><a href="{item['link']}" target="_blank">阅读原文 →</a></div>
    </div>
    <hr>
"""

html += """
</div>
<div class="footer">
来源：NewsData.io · 智谱AI深度解读 · 每日自动推送
</div>
</div>
</body>
</html>
"""

# =============================
# PushPlus推送
# =============================
print("推送中...")
push_url = "https://www.pushplus.plus/send"
payload = {
    "token": PUSHPLUS_TOKEN,
    "title": f"每日新闻早报 {today}",
    "content": html,
    "template": "html"
}

r = requests.post(push_url, json=payload, timeout=35)
print(f"推送状态: {r.status_code}")
print("执行完成！")
