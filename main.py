import requests
import os
import json
import re
from datetime import datetime
import time

# =============================
# 环境变量诊断（智谱版）
# =============================
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

print("🔍 环境变量诊断:")
print(f"   NEWSDATA_API_KEY: {'✅ 有' if NEWSDATA_API_KEY else '❌ 无'}")
print(f"   ZHIPU_API_KEY: {'✅ 有' if ZHIPU_API_KEY else '❌ 无'} (长度:{len(ZHIPU_API_KEY or '')})")
print(f"   PUSHPLUS_TOKEN: {'✅ 有' if PUSHPLUS_TOKEN else '❌ 无'}")

if not NEWSDATA_API_KEY or not ZHIPU_API_KEY or not PUSHPLUS_TOKEN:
    print("❌ 缺少关键环境变量，退出")
    exit(1)

# =============================
# 新闻分类 + 抓取
# =============================
categories = [
    {'cn': '国际政治', 'q': '中国 OR China OR Taiwan OR geopolitics'},
    {'cn': '财经经济', 'q': '中国经济 OR China economy OR 股市 OR inflation OR 贸易'},
    {'cn': '科技前沿', 'q': 'AI OR 人工智能 OR chip OR Huawei OR 新能源 OR 量子'},
    {'cn': '社会民生', 'q': '中国社会 OR 民生 OR 教育 OR 房价 OR 就业'},
    {'cn': '文化娱乐', 'q': '中国文化 OR 娱乐 OR 奥运 OR 电影 OR 明星'},
    {'cn': '健康环境', 'q': '医疗 OR 健康 OR 气候 OR 碳中和 OR pollution'}
]

news_list = []
seen_links = set()

print("\n🚀 开始抓取新闻...")

for cat in categories:
    print(f"📡 [{cat['cn']}] 正在请求...")
    try:
        resp = requests.get(
            "https://newsdata.io/api/1/latest",
            params={
                'apikey': NEWSDATA_API_KEY,
                'q': cat['q'],
                'size': 10,
                'removeduplicate': '1'
            },
            timeout=25
        )
        data = resp.json()

        print(f"   状态: {data.get('status')} | 返回结果数: {len(data.get('results', []))}")

        if data.get('status') != 'success':
            print(f"   ❌ API异常: {data}")
            continue

        valid_count = 0
        for art in data.get('results', []):
            if valid_count >= 3 or len(news_list) >= 18:
                break

            link = art.get('link', '')
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            title = (art.get('title') or '').strip()
            desc = (art.get('description') or art.get('content') or '').strip()
            img_url = art.get('image_url', '')

            if len(title) < 8 or len(desc) < 30:
                continue

            news_list.append({
                'category': cat['cn'],
                'title': title[:88] + '…' if len(title) > 88 else title,
                'desc': desc[:300],
                'link': link,
                'img_url': img_url if isinstance(img_url, str) and img_url.startswith('http') else ''
            })
            valid_count += 1

        print(f"   ✅ 本分类有效收集: {valid_count} 条")

    except Exception as e:
        print(f"   ❌ [{cat['cn']}] 异常: {e}")

print(f"\n✅ 第一阶段收集到 {len(news_list)} 条新闻")

# =============================
# 超强 Fallback
# =============================
if len(news_list) < 6:
    print("🛡️ 启动强力 fallback...")
    fallback_queries = ["", "中国", "world", "news", "China", "AI"]
    for fq in fallback_queries:
        if len(news_list) >= 18: break
        try:
            resp = requests.get(
                "https://newsdata.io/api/1/latest",
                params={'apikey': NEWSDATA_API_KEY, 'q': fq, 'size': 10},
                timeout=20
            )
            data = resp.json()
            for art in data.get('results', [])[:4]:
                link = art.get('link') or ""
                if link and link not in seen_links:
                    seen_links.add(link)
                    title = (art.get('title') or "无标题").strip()
                    desc = (art.get('description') or "").strip()
                    news_list.append({
                        'category': '今日要闻',
                        'title': title[:88] + '…' if len(title) > 88 else title,
                        'desc': desc[:300],
                        'link': link,
                        'img_url': art.get('image_url') or ""
                    })
        except Exception as e:
            print(f"   fallback异常: {e}")

print(f"最终收集到 {len(news_list)} 条新闻")

if not news_list:
    print("⚠️ 最终仍无新闻 → 推送友好提示")
    today = datetime.now().strftime('%Y年%m月%d日')
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>每日新闻 {today}</title></head><body>
    <h1>每日新闻早报 {today}</h1>
    <p>今日暂无新新闻（NewsData.io 免费额度可能已用完或暂无更新）。</p>
    <p>额度每日北京时间早上8点自动重置，明天再试即可。</p></body></html>"""
    requests.post("https://www.pushplus.plus/send", json={
        "token": PUSHPLUS_TOKEN,
        "title": f"每日新闻 {today}（暂无更新）",
        "content": html,
        "template": "html"
    })
    exit()

# =============================
# 智谱 GLM 批量生成（安全 + 可剔除无效新闻）
# =============================
def batch_zhipu(items):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {"Authorization": f"Bearer {ZHIPU_API_KEY}", "Content-Type": "application/json"}

    payload = [{"id": i, "category": item["category"], "title": item["title"], "desc": item["desc"]}
               for i, item in enumerate(items)]

    system_prompt = """你是一位资深中文报纸副总编辑。
为每条新闻生成三个字段（全部简体中文）：
- official：约120字官方摘要
- professional：不少于200字专业解析（分段）
- vernacular：不少于160字白话解读（分段）
必须返回纯JSON数组。禁止markdown，禁止解释，只输出JSON。"""

    body = {"model": "glm-4-flash",
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            "temperature": 0.6,
            "max_tokens": 5000}

    try:
        r = requests.post(url, headers=headers, json=body, timeout=120)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = re.sub(r"```json|```", "", content).strip()
        match = re.search(r"\[.*\]", content, re.S)
        if match:
            content = match.group(0)
        result = json.loads(content)
        if not isinstance(result, list):
            raise ValueError("返回不是数组")
        return result
    except Exception as e:
        print(f"❌ 批量失败，尝试单条重试: {e}")
        results = []
        for single in items:
            try:
                single_payload = [{"id": 0, "category": single["category"],
                                   "title": single["title"], "desc": single["desc"]}]
                single_body = body.copy()
                single_body["messages"][1]["content"] = json.dumps(single_payload, ensure_ascii=False)
                r = requests.post(url, headers=headers, json=single_body, timeout=90)
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                content = re.sub(r"```json|```", "", content).strip()
                match = re.search(r"\[.*\]", content, re.S)
                if match:
                    content = match.group(0)
                parsed = json.loads(content)
                results.append(parsed[0])
            except Exception as ee:
                results.append({
                    "official": "",
                    "professional": "",
                    "vernacular": ""
                })
        return results

# =============================
# 分批调用智谱
# =============================
print("🤖 开始分批调用智谱...")
analysis_list = []
batch_size = 3
for i in range(0, len(news_list), batch_size):
    batch = news_list[i:i+batch_size]
    analysis_list.extend(batch_zhipu(batch))
    time.sleep(1)

# =============================
# 剔除无效新闻，保证推送数量≥12
# =============================
valid_news = []
valid_analysis = []

for item, analysis in zip(news_list, analysis_list):
    if analysis.get('official') and analysis.get('professional') and analysis.get('vernacular'):
        valid_news.append(item)
        valid_analysis.append(analysis)

# 如果有效新闻少于12条，则从 news_list 里补充还没使用的新闻（不含无效内容）
idx = 0
while len(valid_news) < 12 and idx < len(news_list):
    candidate = news_list[idx]
    if candidate not in valid_news:
        valid_news.append(candidate)
        # 填充空分析，用户不会看到无内容新闻
        valid_analysis.append({
            "official": "暂无摘要",
            "professional": "暂无专业解析",
            "vernacular": "暂无白话解读"
        })
    idx += 1

# =============================
# HTML 构建
# =============================
today = datetime.now().strftime('%Y年%m月%d日')
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
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
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>每日新闻早报</h1><div class="date">{today}</div></div>
<div class="content">
"""

for item, analysis in zip(valid_news, valid_analysis):
    img_html = f'<div class="img-container"><img src="{item.get("img_url","")}" alt="配图"></div>' if item.get('img_url') else ''
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

html += """</div><div class="footer">来源：NewsData.io · 智谱GLM-4-Flash深度解读 · 自动推送</div></div></body></html>"""

# =============================
# PushPlus推送
# =============================
print("📤 正在推送...")
r = requests.post("https://www.pushplus.plus/send", json={
    "token": PUSHPLUS_TOKEN,
    "title": f"每日新闻早报 {today}",
    "content": html,
    "template": "html"
}, timeout=30)
print(f"推送状态: {r.status_code}")
print("🎉 执行完成！")
