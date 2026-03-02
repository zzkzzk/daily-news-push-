import requests
import os
import json
import re
from datetime import datetime

# =============================
# 环境变量 + 诊断
# =============================
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

print("🔍 诊断信息:")
print(f"   QWEN_API_KEY 是否存在: {'✅ 有' if QWEN_API_KEY else '❌ 无'}")
print(f"   QWEN_API_KEY 长度: {len(QWEN_API_KEY or '')}")
if QWEN_API_KEY and not QWEN_API_KEY.startswith('sk-'):
    print("⚠️ 警告: Key 格式可能错误，应以 sk- 开头")

if not QWEN_API_KEY:
    print("❌ 未找到 QWEN_API_KEY，退出")
    exit(1)

# =============================
# 新闻抓取（保持不变）
# =============================
categories = [ ... ]  # 保持你之前用的分类（我省略了，和上一个版本完全一样）

news_list = []
seen_links = set()

# ...（抓取代码完全复制上一个版本的，省略以节省篇幅）

print(f"✅ 收集到 {len(news_list)} 条新闻")

if not news_list:
    exit()

# =============================
# Qwen 分批调用 + 国际节点 + 详细日志
# =============================
def call_qwen_batch(batch_items):
    url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"  # ← 改用国际节点（GitHub 更稳定）
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = [{"id": i, "category": item["category"], "title": item["title"], "desc": item["desc"]}
               for i, item in enumerate(batch_items)]

    system_prompt = """你是一位资深中文报纸副总编辑。
为每条新闻生成三个字段（全部简体中文）：
- official：约150字官方摘要
- professional：不少于250字专业深度解析（分2-3段）
- vernacular：不少于200字白话解读（分2段）

只返回纯JSON数组，不要任何其他文字。"""

    body = {
        "model": "qwen-plus",      # ← 改用更稳定的 qwen-plus
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
        "temperature": 0.7,
        "max_tokens": 6000
    }

    try:
        print(f"🚀 调用 Qwen batch ({len(batch_items)}条)...")
        r = requests.post(url, headers=headers, json=body, timeout=90)
        print(f"   状态码: {r.status_code}")
        print(f"   响应前200字符: {r.text[:200]}")

        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = re.sub(r"```json|```", "", content).strip()
        print("✅ Qwen 本批成功")
        return json.loads(content)
    except Exception as e:
        print(f"❌ Qwen 本批失败: {type(e).__name__} - {e}")
        if 'r' in locals():
            print(f"   完整响应: {r.text}")
        return [{
            "official": f"API调用失败（状态码:{r.status_code if 'r' in locals() else 'N/A'}）",
            "professional": "请检查 GitHub Secrets 中的 QWEN_API_KEY 是否正确、是否有额度、是否已开通服务",
            "vernacular": "阿里云百炼控制台 → 立即充值 10 元即可恢复使用"
        } for _ in batch_items]


# 分批调用（每批最多6条，避免超限）
print("🤖 开始分批调用 Qwen...")
analysis_list = []
batch_size = 6
for i in range(0, len(news_list), batch_size):
    batch = news_list[i:i+batch_size]
    analysis_list.extend(call_qwen_batch(batch))

# =============================
# HTML 构建 + 错误友好显示
# =============================
today = datetime.now().strftime('%Y年%m月%d日')
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日新闻 {today}</title>
<style> /* 保持你喜欢的02风格，完全一样 */ 
body{{font-family:-apple-system,...}} /* 省略，和之前一样 */
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

html += """</div><div class="footer">来源：NewsData.io · 通义千问 Qwen-plus</div></div></body></html>"""

# =============================
# 推送
# =============================
print("📤 推送中...")
r = requests.post("https://www.pushplus.plus/send", json={
    "token": PUSHPLUS_TOKEN,
    "title": f"每日新闻 {today} {'（AI生成失败）' if any('API调用失败' in str(a.get('official','')) for a in analysis_list) else ''}",
    "content": html,
    "template": "html"
}, timeout=30)

print(f"推送状态: {r.status_code}")
print("🎉 执行完成！")
