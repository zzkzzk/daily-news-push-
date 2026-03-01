import requests
import os
import json
import time

# Secrets
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

# 类别（中文名 + 英文参数 + 关键词侧重中国/世界）
categories = [
    {'cn': '国际政治', 'en': 'politics', 'q': '中国 OR China OR world politics'},
    {'cn': '财经经济', 'en': 'business', 'q': '中国经济 OR China economy'},
    {'cn': '科技', 'en': 'technology', 'q': '中国科技 OR AI China'},
    {'cn': '体育', 'en': 'sports', 'q': '中国体育 OR world sports'},
    {'cn': '文化娱乐', 'en': 'entertainment', 'q': '中国文化 OR global culture'}
]

news_list = []

for cat in categories:
    url = "https://newsdata.io/api/1/latest"
    params = {
        'apikey': NEWSDATA_API_KEY,
        'language': 'zh',  # 优先中文
        'size': 1,
        'removeduplicate': '1'
    }
    if 'q' in cat:
        params['q'] = cat['q']  # 用关键词侧重中国+世界

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        if data.get('status') == 'success' and data.get('results'):
            art = data['results'][0]
            # 提取图片（如果有）
            img_url = art.get('image_url') or ''
            news_list.append({
                'category': cat['cn'],
                'title': art.get('title', '无标题').strip(),
                'desc': (art.get('description') or art.get('content', '无内容'))[:300].strip(),
                'link': art.get('link', ''),
                'img_url': img_url,
                'lang': art.get('language', 'unknown')
            })
    except Exception as e:
        print(f"{cat['cn']} 抓取失败: {e}")

# fallback：如果少于4条，用全球热门补
if len(news_list) < 4:
    params = {
        'apikey': NEWSDATA_API_KEY,
        'q': 'top world news today China',
        'size': 2  # 多补几条
    }
    try:
        resp = requests.get("https://newsdata.io/api/1/latest", params=params, timeout=15)
        data = resp.json()
        if data.get('status') == 'success' and data.get('results'):
            for art in data['results'][:2]:
                img_url = art.get('image_url') or ''
                news_list.append({
                    'category': '全球热点',
                    'title': art.get('title', '无标题').strip(),
                    'desc': (art.get('description') or art.get('content', '无内容'))[:300].strip(),
                    'link': art.get('link', ''),
                    'img_url': img_url,
                    'lang': art.get('language', 'unknown')
                })
    except:
        pass

# Qwen 处理：翻译（如果非中文） + 大白话解析（报纸风格）
def qwen_process(item):
    text = f"语言：{item['lang']} 分类：{item['category']} 标题：{item['title']} 摘要：{item['desc']}"
    qwen_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "qwen-turbo",
        "input": {
            "messages": [
                {"role": "system", "content": "你是一位专业中文报纸编辑。用简体中文处理新闻：1. 如果原文非中文，先完整翻译成简体中文（标题+摘要）。2. 然后写大白话专业解析，像《人民日报》或《纽约时报中文网》风格：客观、通俗、专业、易读，分自然段。限150-220字。只输出：【翻译摘要】（如果需要） + 【大白话解析】正文。无前缀、无废话。"},
                {"role": "user", "content": f"处理这条新闻：{text}"}
            ]
        },
        "parameters": {"max_tokens": 450}
    }
    try:
        r = requests.post(qwen_url, headers=headers, json=body, timeout=25)
        result = r.json()
        output = result.get("output", {}).get("text", "处理失败").strip()
        return output
    except Exception as e:
        print(f"Qwen 异常: {e}")
        return "解析失败"

# 构建 Markdown 报纸风格消息
msg = "# 每日全球新闻早报\n\n**今日焦点**：世界热点 + 中国视角 | **日期**：{time.strftime('%Y年%m月%d日')}\n\n---\n\n".format(time=time)

for item in news_list:
    parsed = qwen_process(item)
    msg += f"## {item['category']} · {item['title']}\n\n"
    if item['img_url']:
        msg += f"![新闻配图]({item['img_url']})\n\n"  # 插入图片
    msg += f"**官方摘要**：{item['desc']}\n\n"
    msg += f"**专业解析**：\n{parsed}\n\n"
    if item['link']:
        msg += f"[阅读原文 →]({item['link']})\n\n"
    msg += "---\n\n"

if not news_list:
    msg += "**今日暂无精选**，网络或额度问题，明天继续更新！\n"

msg += "\n**来源**：NewsData.io 聚合（Reuters/BBC/CNN/SCMP/CGTN 等） | **推送**：每日早8点\n小提示：点链接/图看详情。欢迎反馈！"

# PushPlus POST + markdown
push_url = "https://www.pushplus.plus/send"
payload = {
    "token": PUSHPLUS_TOKEN,
    "title": "每日新闻早报 - 全球+中国热点",
    "content": msg,
    "template": "markdown"
}

# 重试推送（不变）
success = False
for attempt in range(1, 4):
    try:
        response = requests.post(push_url, json=payload, timeout=20)
        print(f"尝试 {attempt}: {response.status_code} | 返回: {response.text[:200]}...")
        if response.status_code == 200 and '200' in response.text:
            success = True
            break
    except Exception as e:
        print(f"异常: {e}")
    if attempt < 3:
        time.sleep(10)

print("执行完毕，新闻数：", len(news_list))
