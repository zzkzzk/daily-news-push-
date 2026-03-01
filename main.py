import requests
import os
import json
import time
from datetime import datetime

# 从 GitHub Secrets 获取密钥
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

# 扩展类别：增加更多大板块（如社会民生、健康医疗、环境气候），每个板块取2条新闻
categories = [
    {'cn': '国际政治', 'en': 'politics', 'q': '中国 OR China OR world politics OR international relations'},
    {'cn': '财经经济', 'en': 'business', 'q': '中国经济 OR China economy OR global market OR finance'},
    {'cn': '科技', 'en': 'technology', 'q': '中国科技 OR AI China OR tech innovation OR science'},
    {'cn': '体育', 'en': 'sports', 'q': '中国体育 OR world sports OR Olympics OR football'},
    {'cn': '文化娱乐', 'en': 'entertainment', 'q': '中国文化 OR global culture OR entertainment OR movie OR music'},
    {'cn': '社会民生', 'en': 'general', 'q': '中国社会 OR China society OR public welfare OR daily life'},  # 新增板块
    {'cn': '健康医疗', 'en': 'health', 'q': '中国医疗 OR health China OR medicine OR pandemic'},  # 新增板块
    {'cn': '环境气候', 'en': 'environment', 'q': '中国环境 OR climate change OR global warming OR ecology'}  # 新增板块
]

news_list = []

for cat in categories:
    url = "https://newsdata.io/api/1/latest"
    params = {
        'apikey': NEWSDATA_API_KEY,
        'language': 'zh',
        'size': 2,  # 每个板块取2条新闻
        'removeduplicate': '1'
    }
    if 'q' in cat:
        params['q'] = cat['q']

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if data.get('status') == 'success' and data.get('results'):
            for art in data['results']:
                img_url = art.get('image_url') or ''
                # 打印 img_url 到日志，便于调试图片问题
                print(f"图片URL for {art.get('title')}: {img_url}")
                news_list.append({
                    'category': cat['cn'],
                    'title': art.get('title', '无标题').strip(),
                    'desc': (art.get('description') or art.get('content', '无内容'))[:300].strip(),
                    'link': art.get('link', ''),
                    'img_url': img_url if img_url.startswith('https://') else '',  # 只用 https 避免加载问题
                    'lang': art.get('language', 'unknown')
                })
    except Exception as e:
        print(f"{cat['cn']} 抓取失败: {e}")

# 如果新闻少于10条，用全球热门 + 中国相关补齐
if len(news_list) < 10:
    params = {
        'apikey': NEWSDATA_API_KEY,
        'q': 'top world news today China OR global hot news',
        'size': 5  # 多补一些
    }
    try:
        resp = requests.get("https://newsdata.io/api/1/latest", params=params, timeout=15)
        data = resp.json()
        if data.get('status') == 'success' and data.get('results'):
            for art in data['results'][:5 - len(news_list)]:
                img_url = art.get('image_url') or ''
                print(f"补齐图片URL: {img_url}")
                news_list.append({
                    'category': '全球热点',
                    'title': art.get('title', '无标题').strip(),
                    'desc': (art.get('description') or art.get('content', '无内容'))[:300].strip(),
                    'link': art.get('link', ''),
                    'img_url': img_url if img_url.startswith('https://') else '',
                    'lang': art.get('language', 'unknown')
                })
    except Exception as e:
        print(f"全球热点 fallback 失败: {e}")

# 通义千问处理：翻译（非中文） + 大白话专业解析
def qwen_process(item):
    text = f"语言：{item['lang']} 分类：{item['category']} 标题：{item['title']} 摘要：{item['desc']}"
    qwen_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "qwen-turbo",
        "input": {
            "messages": [
                {"role": "system", "content": "你是一位专业中文报纸编辑。用简体中文处理新闻：1. 如果原文非中文，先完整翻译成简体中文（标题+摘要）。2. 然后写大白话专业解析，风格像《人民日报》或《纽约时报中文网》：客观、中性、通俗、专业、易读，分自然段。限150-220字。只输出：【翻译摘要】（如果需要） + 【大白话解析】正文。无前缀、无废话、无额外说明。"},
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
        print(f"Qwen 处理异常: {e}")
        return "解析失败"

# 构建 Markdown 格式消息（报纸风格）
today = datetime.now().strftime('%Y年%m月%d日')

msg = f"# 每日全球新闻早报\n\n**今日焦点**：世界热点 + 中国视角 | **日期**：{today}\n\n---\n\n"

for item in news_list:
    parsed = qwen_process(item)
    msg += f"## {item['category']} · {item['title']}\n\n"
    if item['img_url']:
        # 改用 HTML img 标签嵌入（markdown 可能有问题，微信更兼容 HTML）
        msg += f'<img src="{item['img_url']}" alt="新闻配图" width="100%" />\n\n'
    msg += f"**官方摘要**：{item['desc']}\n\n"
    msg += f"**专业解析**：\n{parsed}\n\n"
    if item['link']:
        msg += f"[阅读原文 →]({item['link']})\n\n"
    msg += "---\n\n"

if not news_list:
    msg += "**今日暂无精选新闻**，可能是网络、额度或API问题，明天继续更新！\n"

msg += "\n**来源**：NewsData.io 聚合（Reuters / BBC / CNN / SCMP / CGTN / Xinhua 等）\n"
msg += "**推送时间**：每日北京时间早8点\n"
msg += "小提示：点击图片或链接查看完整内容。欢迎反馈意见～"

# PushPlus 发送（POST + html 模板，避免 markdown 图片问题）
push_url = "https://www.pushplus.plus/send"
payload = {
    "token": PUSHPLUS_TOKEN,
    "title": "每日新闻早报 - 全球与中国热点",
    "content": msg,
    "template": "html"  # 改用 html 模板，确保图片显示
}

success = False
for attempt in range(1, 4):
    try:
        response = requests.post(push_url, json=payload, timeout=20)
        print(f"推送尝试 {attempt}: 状态码 {response.status_code}")
        print(f"返回: {response.text[:300]}...")
        
        if response.status_code == 200:
            try:
                resp_json = response.json()
                if resp_json.get("code") == 200:
                    print("推送成功！")
                    success = True
                    break
                else:
                    print(f"业务错误: {resp_json.get('msg', '未知')}")
            except:
                print("状态200，但非JSON响应，可能已成功")
                success = True
                break
    except Exception as e:
        print(f"推送尝试 {attempt} 异常: {str(e)}")
    
    if attempt < 3:
        time.sleep(10 * attempt)

if not success:
    print("推送最终失败，但脚本继续执行")

print("脚本执行完毕，新闻数量：", len(news_list))
