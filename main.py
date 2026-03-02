import requests
import os
import time
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

# =============================
# 智谱处理函数（带限速+指数退避）
# =============================
def zhipu_process(item):

    prompt_text = (
        f"语言：{item['lang']} "
        f"分类：{item['category']} "
        f"标题：{item['title']} "
        f"摘要：{item['desc'][:200]}"
    )

    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": "glm-4-flash",
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一位资深中文报纸副总编辑。必须使用简体中文输出。\n\n"
                    "严格格式：\n"
                    "【官方摘要】\n≤160字\n\n"
                    "【专业解析】\n110-130字，两段\n\n"
                    "【白话解析】\n90-110字，两段\n"
                )
            },
            {
                "role": "user",
                "content": f"处理这条新闻：{prompt_text}"
            }
        ],
        "temperature": 0.6,
        "max_tokens": 600
    }

    delay = 2
    for attempt in range(5):
        try:
            response = requests.post(url, headers=headers, json=body, timeout=40)

            if response.status_code == 429:
                print(f"触发速率限制，等待 {delay} 秒...")
                time.sleep(delay)
                delay *= 2
                continue

            response.raise_for_status()
            result = response.json()
            output = result["choices"][0]["message"]["content"].strip()

            time.sleep(2)  # 控制频率
            return output

        except Exception as e:
            print(f"智谱异常: {e}")
            time.sleep(delay)
            delay *= 2

    return "【官方摘要】\n解析失败\n【专业解析】\n暂无\n【白话解析】\n暂无"

# =============================
# 构建 HTML（含图片）
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
    background:#f9fafb;
    margin:0;
    padding:12px 8px;
}}
.container {{
    max-width:920px;
    margin:0 auto;
    background:#fff;
    border-radius:16px;
    overflow:hidden;
    box-shadow:0 10px 38px rgba(0,0,0,0.08);
}}
.header {{
    background:linear-gradient(135deg,#1d4ed8,#60a5fa);
    color:white;
    padding:44px 24px 24px;
    text-align:center;
}}
.content {{
    padding:24px 20px;
}}
h2 {{
    font-size:22px;
    margin:32px 0 16px;
    border-left:5px solid #3b82f6;
    padding-left:10px;
}}
.card {{
    border:1px solid #e5e7eb;
    border-radius:12px;
    margin-bottom:28px;
    overflow:hidden;
}}
.card img {{
    width:100%;
    max-height:220px;
    object-fit:cover;
    display:block;
}}
.card-body {{
    padding:22px;
}}
.title {{
    font-size:20px;
    font-weight:700;
    margin-bottom:14px;
}}
.section {{
    font-size:15px;
    margin:14px 0;
}}
.link {{
    text-align:right;
    margin-top:12px;
}}
.footer {{
    background:#f1f5f9;
    padding:20px;
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

for item in news_list:

    if item['category'] != current_cat:
        msg += f"<h2>{item['category']}</h2>"
        current_cat = item['category']

    parsed = zhipu_process(item)

    official = professional = vernacular = "解析异常"

    parts = parsed.replace('\n\n', '\n').split('【')
    for p in parts:
        p = p.strip()
        if p.startswith('官方摘要】'):
            official = p.replace('官方摘要】', '').strip()
        elif p.startswith('专业解析】'):
            professional = p.replace('专业解析】', '').strip()
        elif p.startswith('白话解析】'):
            vernacular = p.replace('白话解析】', '').strip()

    img_tag = ""
    if item['img_url']:
        img_tag = f'<img src="{item["img_url"]}" alt="配图" onerror="this.style.display=\'none\';">'

    msg += f"""
    <div class="card">
        {img_tag}
        <div class="card-body">
            <div class="title">{item['title']}</div>
            <div class="section"><strong>官方摘要：</strong><br>{official}</div>
            <div class="section"><strong>专业解析：</strong><br>{professional}</div>
            <div class="section"><strong>白话解读：</strong><br>{vernacular}</div>
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

success = False
for attempt in range(3):
    try:
        r = requests.post(push_url, json=payload, timeout=20)
        print(f"推送尝试 {attempt+1} | 状态: {r.status_code}")
        print("返回:", r.text[:200])
        if r.status_code == 200 and '"code":200' in r.text:
            success = True
            break
    except Exception as e:
        print("推送异常:", e)
    time.sleep(8)

if not success:
    print("推送未确认成功")

print(f"执行结束　新闻总数：{len(news_list)}")
