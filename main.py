import requests
import os
import json
import re
from datetime import datetime

# =============================
# 环境变量（已改为 QWEN_API_KEY）
# =============================
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')          # ← 关键修改
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

if not QWEN_API_KEY:
    print("❌ 错误：未找到 QWEN_API_KEY，请检查 GitHub Secrets")
    exit(1)

# =============================
# 新闻分类（均衡 + 省额度）
# =============================
categories = [
    {'cn': '国际政治', 'q': '中国 OR China OR geopolitics OR Taiwan'},
    {'cn': '财经经济', 'q': '中国经济 OR China economy OR 股市 OR inflation'},
    {'cn': '科技前沿', 'q': 'AI OR 人工智能 OR chip OR Huawei OR 新能源'},
    {'cn': '社会民生', 'q': '中国社会 OR 民生 OR education OR housing'},
    {'cn': '文化娱乐', 'q': '中国文化 OR entertainment OR 奥运 OR celebrity'},
    {'cn': '健康环境', 'q': 'health OR climate OR 碳中和 OR 医疗'},
]

news_list = []
seen_links = set()

# =============================
# 获取新闻
# =============================
print("🚀 开始抓取新闻...")
for cat in categories:
    if len(news_list) >= 18: break
    try:
        resp = requests.get(
            "https://newsdata.io/api/1/latest",
            params={
                'apikey': NEWSDATA_API_KEY,
                'q': cat['q'],
                'language': 'zh',
                'size': 6,
                'removeduplicate': '1'
            },
            timeout=20
        )
        data = resp.json()

        if data.get('status') != 'success':
            print(f"[{cat['cn']}] API状态异常: {data.get('results')}")
            continue

        valid_count = 0
        for art in data.get('results', []):
            if valid_count >= 3 or len(news_list) >= 18: break

            link = art.get('link', '')
            if not link or link in seen_links: continue
            seen_links.add(link)

            title = (art.get('title') or '').strip()
            desc = (art.get('description') or art.get('content') or '').strip()
            img_url = art.get('image_url', '')

            if len(title) < 8 or len(desc) < 35: continue

            news_list.append({
                'category': cat['cn'],
                'title': title[:88] + '…' if len(title) > 88 else title,
                'desc': desc[:300],
                'link': link,
                'img_url': img_url if isinstance(img_url, str) and img_url.startswith('http') else ''
            })
            valid_count += 1

    except Exception as e:
        print(f"[{cat['cn']}] 抓取异常: {e}")

print(f"✅ 收集到 {len(news_list)} 条新闻")

# fallback
if len(news_list) < 6:
    print("🛡️ 启动 fallback...")
    try:
        resp = requests.get("https://newsdata.io/api/1/latest",
                            params={"apikey": NEWSDATA_API_KEY, "size": 12}, timeout=20)
        for art in resp.json().get("results", [])[:6]:
            link = art.get("link") or ""
            if link and link not in seen_links:
                seen_links.add(link)
                news_list.append({
                    'category': '今日要闻',
                    'title': (art.get("title") or "无标题")[:88],
                    'desc': (art.get("description") or "")[:300],
                    'link': link,
                    'img_url': art.get("image_url") or ""
                })
    except: pass

if not news_list:
    print("❌ 无新闻，退出")
    exit()

# =============================
# Qwen 通义千问 批量生成（已适配正确API）
# =============================
def batch_qwen(items):
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"  # Qwen官方兼容接口
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = [{"id": i, "category": item["category"], "title": item["title"], "desc": item["desc"]}
               for i, item in enumerate(items)]

    system_prompt = """你是一位资深中文报纸副总编辑。
为每条新闻生成三个字段（全部简体中文）：
- official：约150字官方摘要
- professional：不少于250字专业深度解析（2-3段）
- vernacular：不少于200字白话解读（2段，通俗生动）

必须返回纯JSON数组，不要任何其他文字。"""

    body = {
        "model": "qwen-turbo",          # 速度快、性价比高（也可换 qwen-plus）
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
        "temperature": 0.65,
        "max_tokens": 8000
    }

    try:
        r = requests.post(url, headers=headers, json=body, timeout=120)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = re.sub(r"```json|```", "", content).strip()
        print("✅ Qwen 调用成功")
        return json.loads(content)
    except Exception as e:
        print(f"❌ Qwen 调用失败: {e}")
        print(f"响应内容: {r.text if 'r' in locals() else '无响应'}")
        return [{
            "official": "暂无摘要（API调用失败）",
            "professional": "暂无专业解析（API调用失败）",
            "vernacular": "暂无白话解读（API调用失败）"
        } for _ in items]


print("🤖 调用 Qwen 生成解读...")
analysis_list = batch_qwen(news_list)

# =============================
# HTML（保留你喜欢的02风格 + 图片）
# =============================
today = datetime.now().strftime('%Y年%m月%d日')
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日新闻早报 {today}</title>
<style>
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9fa;margin:0;padding:10px 8px;line-height:1.75;}}
    .container{{max-width:100%;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.07);}}
    .header{{background:linear-gradient(135deg,#1e40af,#3b82f6);color:white;padding:42px 20px 26px;text-align:center;}}
    .header h1{{margin:0;font-size:27px;}} .date{{font-size:15.5px;opacity:0.95;margin-top:8px;}}
    .content{{padding:20px 18px;}} .news-item{{margin-bottom:38px;}}
    .title{{font-size:20px;font-weight:700;color:#1e3a8a;margin:18px 0 14px;line-height:1.45;}}
    .img-container{{margin:14px -18px 20px -18px;}} .img-container img{{width:100%;height:auto;display:block;border-radius:10px;}}
    .section{{margin:17px 0;font-size:15.4px;}} .section strong{{color:#1e40af;}}
    .link{{text-align:right;margin-top:14px;}} hr{{border:none;border-top:1px solid #e5e7eb;margin:34px 0 28px;}}
    .footer{{background:#f1f5f9;padding:22px;text-align:center;font-size:13.5px;color:#64748b;}}
</style></head>
<body>
<div class="container">
<div class="header"><h1>每日新闻早报</h1><div class="date">{today}</div></div>
<div class="content">
"""

for item, analysis in zip(news_list, analysis_list):
    img_html = f'<div class="img-container"><img src="{item["img_url"]}" alt="配图"></div>' if item.get('img_url') else ''
    html += f"""
    <div class="news-item">
        {img_html}
        <div class="title">{item['title']}</div>
        <div class="section"><strong>官方摘要：</strong><br>{analysis.get('official','暂无')}</div>
        <div class="section"><strong>专业解析：</strong><br>{analysis.get('professional','暂无')}</div>
        <div class="section"><strong>白话解读：</strong><br>{analysis.get('vernacular','暂无')}</div>
        <div class="link"><a href="{item['link']}" target="_blank">阅读原文 →</a></div>
    </div><hr>
"""

html += """</div><div class="footer">来源：NewsData.io · Qwen 通义千问深度解读</div></div></body></html>"""

# =============================
# PushPlus 推送
# =============================
print("📤 推送中...")
r = requests.post(
    "https://www.pushplus.plus/send",
    json={
        "token": PUSHPLUS_TOKEN,
        "title": f"每日新闻早报 {today}",
        "content": html,
        "template": "html"
    },
    timeout=30
)
print(f"推送状态: {r.status_code} | 返回: {r.text[:200]}")
print("🎉 执行完成！")
