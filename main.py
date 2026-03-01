import requests
import os
import json
import time
from datetime import datetime

# 从环境变量获取密钥
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

categories = [
    {'cn': '国际政治',     'q': '中国 OR China OR world politics OR geopolitics OR Taiwan OR Ukraine'},
    {'cn': '财经经济',     'q': '中国经济 OR China economy OR global market OR finance OR trade war'},
    {'cn': '科技前沿',     'q': '中国科技 OR AI China OR chip OR semiconductor OR quantum OR Huawei'},
    {'cn': '体育赛事',     'q': '中国体育 OR Olympics OR football OR basketball OR 奥运 OR 世界杯'},
    {'cn': '文化娱乐',     'q': '中国文化 OR entertainment OR movie OR music OR festival OR celebrity'},
    {'cn': '社会民生',     'q': '中国社会 OR education OR housing OR employment OR population OR 民生'},
    {'cn': '健康医疗',     'q': '中国医疗 OR health China OR cancer OR vaccine OR aging OR 疫情'},
    {'cn': '环境气候',     'q': '中国环境 OR climate change OR carbon OR renewable OR 碳中和 OR pollution'}
]

news_list = []

for cat in categories:
    url = "https://newsdata.io/api/1/latest"
    params = {
        'apikey': NEWSDATA_API_KEY,
        'q': cat['q'],
        'language': 'zh',
        'size': 5,               # 多取一点，筛选更严格
        'removeduplicate': '1'
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        if data.get('status') != 'success' or not data.get('results'):
            continue

        valid_count = 0
        for art in data['results']:
            if valid_count >= 2:          # 每个板块最多2条
                break
            title = (art.get('title') or '').strip()
            desc = (art.get('description') or art.get('content') or '').strip()
            link = art.get('link', '')
            img_url = art.get('image_url', '')

            if len(title) < 10 or len(desc) < 40 or 'http' not in link:
                continue
            if len(title) > 80:           # 标题太长截断
                title = title[:78] + '…'

            news_list.append({
                'category': cat['cn'],
                'title': title,
                'desc': desc[:280],
                'link': link,
                'img_url': img_url if img_url and img_url.startswith('https') else '',
                'lang': art.get('language', 'zh')
            })
            valid_count += 1

    except Exception as e:
        print(f"[{cat['cn']}] 获取失败: {e}")

# 补齐（目标总数 14~18 条）
if len(news_list) < 14:
    extra_params = {
        'apikey': NEWSDATA_API_KEY,
        'q': '中国 OR China OR 热点 OR 要闻',
        'language': 'zh',
        'size': 15
    }
    try:
        resp = requests.get("https://newsdata.io/api/1/latest", params=extra_params, timeout=15)
        data = resp.json()
        if data.get('status') == 'success' and data.get('results'):
            for art in data['results']:
                if len(news_list) >= 18:
                    break
                title = (art.get('title') or '').strip()
                if len(title) < 12:
                    continue
                if any(n['link'] == art.get('link') for n in news_list):
                    continue
                news_list.append({
                    'category': '综合要闻',
                    'title': title[:78] + '…' if len(title) > 80 else title,
                    'desc': (art.get('description') or art.get('content') or '')[:260],
                    'link': art.get('link', ''),
                    'img_url': art.get('image_url', ''),
                    'lang': art.get('language', 'zh')
                })
    except Exception as e:
        print(f"补齐失败: {e}")

print(f"收集到新闻：{len(news_list)} 条")

# ────────────────────────────────────────────────
# 通义千问处理（加强长度控制）
# ────────────────────────────────────────────────
def qwen_process(item):
    text = f"语言：{item['lang']} 分类：{item['category']} 标题：{item['title']} 摘要：{item['desc'][:220]}"

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "qwen-turbo",
        "input": {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一位资深中文时政/财经类报纸副总编辑。用**简体中文**处理新闻，输出**严格**遵循以下格式，不得多余文字、空格、符号：\n\n"
                        "【官方摘要】\n不超过180字的精炼中文摘要（若原文非中文则先翻译再浓缩）\n\n"
                        "【专业解析】\n客观中性、社论风格，120–140字，2段\n\n"
                        "【白话解析】\n通俗接地气，像给朋友讲，100–120字，2段\n\n"
                        "禁止出现 markdown、代码、列表、感叹号滥用、口语化标题等。"
                    )
                },
                {"role": "user", "content": f"处理这条新闻：{text}"}
            ]
        },
        "parameters": {
            "max_tokens": 480,
            "temperature": 0.65,
            "top_p": 0.92
        }
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=25)
        result = r.json()
        output = result.get("output", {}).get("text", "").strip()
        return output if output else "解析失败"
    except Exception as e:
        print(f"Qwen 异常: {e}")
        return "【官方摘要】\n（解析服务异常）\n【专业解析】\n暂无\n【白话解析】\n暂无"

# ────────────────────────────────────────────────
# HTML 构建 —— 高级电子报风格
# ────────────────────────────────────────────────
today = datetime.now().strftime('%Y年%m月%d日')

msg = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日新闻早报 {today}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif; background:#f8f9fa; color:#1a1a1a; line-height:1.65; margin:0; padding:20px 12px; }}
    .container {{ max-width:680px; margin:0 auto; background:white; border-radius:12px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.08); }}
    .header {{ background:linear-gradient(135deg, #1e3a8a, #3b82f6); color:white; padding:32px 24px 20px; text-align:center; }}
    .header h1 {{ margin:0; font-size:28px; font-weight:700; letter-spacing:0.5px; }}
    .header .date {{ margin:8px 0 0; font-size:15px; opacity:0.9; }}
    .content {{ padding:24px; }}
    h2 {{ color:#111827; font-size:22px; font-weight:700; margin:36px 0 16px; padding-left:12px; border-left:5px solid #3b82f6; }}
    .card {{ background:#ffffff; border:1px solid #e5e7eb; border-radius:10px; margin-bottom:24px; overflow:hidden; box-shadow:0 4px 12px rgba(0,0,0,0.04); transition:box-shadow 0.2s; }}
    .card:hover {{ box-shadow:0 8px 20px rgba(0,0,0,0.08); }}
    .card img {{ width:100%; height:180px; object-fit:cover; display:block; }}
    .card-body {{ padding:20px 22px; }}
    .title {{ font-size:19px; font-weight:700; color:#111827; margin:0 0 14px; line-height:1.4; }}
    .section {{ font-size:15px; color:#4b5563; margin:14px 0; }}
    .section strong {{ color:#1e40af; }}
    .link {{ display:block; text-align:right; margin-top:12px; font-size:14px; }}
    .link a {{ color:#2563eb; text-decoration:none; font-weight:500; }}
    .link a:hover {{ text-decoration:underline; }}
    .footer {{ background:#f1f5f9; padding:20px; text-align:center; font-size:13px; color:#6b7280; border-top:1px solid #e5e7eb; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>每日新闻早报</h1>
        <div class="date">{today}　全球主流媒体精选</div>
    </div>
    <div class="content">
"""

current_cat = None
for item in news_list:
    if item['category'] != current_cat:
        msg += f'<h2>{item["category"]}</h2>'
        current_cat = item['category']

    parsed = qwen_process(item)

    # 更健壮的拆分（防止格式错乱）
    parts = parsed.replace('\n\n', '\n').split('【')
    official = professional = vernacular = "（解析异常）"

    for p in parts:
        p = p.strip()
        if p.startswith('官方摘要】'):
            official = p.replace('官方摘要】', '').strip()[:180]
        elif p.startswith('专业解析】'):
            professional = p.replace('专业解析】', '').strip()[:160]
        elif p.startswith('白话解析】'):
            vernacular = p.replace('白话解析】', '').strip()[:140]

    img_tag = f'<img src="{item["img_url"]}" alt="新闻配图">' if item['img_url'] else ''

    msg += f"""
        <div class="card">
            {img_tag}
            <div class="card-body">
                <div class="title">{item['title']}</div>
                <div class="section"><strong>官方摘要</strong><br>{official}</div>
                <div class="section"><strong>专业解析</strong><br>{professional}</div>
                <div class="section"><strong>白话解读</strong><br>{vernacular}</div>
                <div class="link"><a href="{item['link']}" target="_blank">阅读原文 →</a></div>
            </div>
        </div>
    """

msg += """
    </div>
    <div class="footer">
        <p>来源：NewsData.io 聚合（Reuters / BBC / 新华社 / 财新 / 澎湃等）</p>
        <p>每日北京时间早8:30推送　欢迎反馈</p>
    </div>
</div>
</body>
</html>
"""

# ────────────────────────────────────────────────
# 推送到 PushPlus
# ────────────────────────────────────────────────
push_url = "https://www.pushplus.plus/send"
payload = {
    "token": PUSHPLUS_TOKEN,
    "title": f"每日新闻早报 {today}",
    "content": msg,
    "template": "html"
}

success = False
for attempt in range(1, 4):
    try:
        r = requests.post(push_url, json=payload, timeout=20)
        print(f"推送尝试 {attempt} | 状态码: {r.status_code}")
        print("返回:", r.text[:300])
        if r.status_code == 200:
            j = r.json()
            if j.get("code") in (200, 0) or "成功" in r.text:
                print("推送成功")
                success = True
                break
    except Exception as e:
        print(f"推送异常 {attempt}: {e}")
    if attempt < 3:
        time.sleep(10)

if not success:
    print("推送未确认成功（但脚本已完成）")
    # 可选：把 msg 存本地看实际字节数
    with open("last_news.html", "w", encoding="utf-8") as f:
        f.write(msg)

print(f"执行结束　新闻总数：{len(news_list)}")
