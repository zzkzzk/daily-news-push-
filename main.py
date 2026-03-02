import requests
import os
import json
import re
from datetime import datetime

# =============================
# 环境变量诊断
# =============================
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

print("🔍 环境变量诊断:")
print(f"   NEWSDATA_API_KEY: {'✅ 有' if NEWSDATA_API_KEY else '❌ 无'}")
print(f"   QWEN_API_KEY: {'✅ 有' if QWEN_API_KEY else '❌ 无'} (长度:{len(QWEN_API_KEY or '')})")
print(f"   PUSHPLUS_TOKEN: {'✅ 有' if PUSHPLUS_TOKEN else '❌ 无'}")

if not NEWSDATA_API_KEY or not QWEN_API_KEY or not PUSHPLUS_TOKEN:
    print("❌ 缺少环境变量，退出")
    exit(1)

# =============================
# 新闻抓取（极致诊断版）
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
# 超强 Fallback（如果还是很少）
# =============================
if len(news_list) < 6:
    print("🛡️ 启动强力 fallback...")
    fallback_queries = ["", "中国", "world", "news", "China", "AI"]
    for fq in fallback_queries:
        if len(news_list) >= 12:
            break
        try:
            resp = requests.get(
                "https://newsdata.io/api/1/latest",
                params={
                    'apikey': NEWSDATA_API_KEY,
                    'q': fq,
                    'size': 10
                },
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
    <p>今日暂无新新闻（可能 NewsData.io 免费额度已用完或暂无更新）。</p>
    <p>额度每日北京时间早上8点自动重置，请明天再试。</p>
    <p>来源：NewsData.io</p></body></html>"""
    requests.post("https://www.pushplus.plus/send", json={
        "token": PUSHPLUS_TOKEN,
        "title": f"每日新闻 {today}（暂无更新）",
        "content": html,
        "template": "html"
    })
    exit()

# =============================
# Qwen 生成解读（保持上版稳定配置）
# =============================
def call_qwen_batch(batch):
    url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    payload = [{"id": i, "category": item["category"], "title": item["title"], "desc": item["desc"]} for i, item in enumerate(batch)]
    system_prompt = """你是一位资深中文报纸副总编辑。
为每条新闻生成三个字段（全部简体中文）：
- official：约150字官方摘要
- professional：不少于250字专业深度解析（2-3段）
- vernacular：不少于200字白话解读（2段）
只返回纯JSON数组，不要任何其他文字。"""
    body = {
        "model": "qwen-plus",
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        "temperature": 0.7,
        "max_tokens": 6000
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=90)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = re.sub(r"```json|```", "", content).strip()
        return json.loads(content)
    except Exception as e:
        print(f"❌ Qwen 本批失败: {e}")
        return [{"official": "API调用失败", "professional": "请检查额度/开通服务", "vernacular": "阿里云百炼充值10元即可恢复"} for _ in batch]

print("🤖 开始分批调用 Qwen...")
analysis_list = []
for i in range(0, len(news_list), 6):
    batch = news_list[i:i+6]
    analysis_list.extend(call_qwen_batch(batch))

# =============================
# HTML + 推送（02风格）
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

html += """</div><div class="footer">来源：NewsData.io · 通义千问 Qwen-plus · 自动推送</div></div></body></html>"""

print("📤 正在推送...")
r = requests.post("https://www.pushplus.plus/send", json={
    "token": PUSHPLUS_TOKEN,
    "title": f"每日新闻早报 {today}",
    "content": html,
    "template": "html"
}, timeout=30)
print(f"推送状态: {r.status_code}")
print("🎉 执行完成！")
