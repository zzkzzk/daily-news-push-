import requests
import os
import json

# 这些密钥从 GitHub Secrets 自动读取，不要写死在这里
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

# 要抓的新闻类别（NewsData.io 支持的）
categories = ['politics', 'business', 'technology', 'sports', 'entertainment']

news_list = []

for cat in categories:
    url = "https://newsdata.io/api/1/latest"
    params = {
        'apikey': NEWSDATA_API_KEY,
        'category': cat,
        'language': 'zh',          # 优先中文
        'size': 1,                 # 每类只取1条，省额度
        'removeduplicate': '1'
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        if data.get('status') == 'success' and data.get('results'):
            art = data['results'][0]
            news_list.append({
                'title': art.get('title', '无标题'),
                'desc': art.get('description') or art.get('content', '无内容')[:300],
                'link': art.get('link', '无链接')
            })
    except:
        pass  # 出错了就跳过这个类别

# 如果中文没抓到，简单 fallback（不限语言 + 关键词中国）
if len(news_list) < 3:
    for cat in categories:
        params.pop('language', None)
        params['q'] = '中国 ' + cat
        params['size'] = 1
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get('status') == 'success' and data.get('results'):
                art = data['results'][0]
                news_list.append({
                    'title': art.get('title', '无标题'),
                    'desc': art.get('description') or art.get('content', '无内容')[:300],
                    'link': art.get('link', '无链接')
                })
        except:
            pass

# 通义千问 大白话解析
def qwen_parse(text):
    qwen_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "qwen-turbo",
        "input": {
            "messages": [
                {"role": "system", "content": "你是新闻大白话翻译机。用最接地气、简单易懂的口语化中文解释新闻。只输出解释内容，不要加任何前缀、标题、废话。限150字。"},
                {"role": "user", "content": f"用大白话解释：{text}"}
            ]
        },
        "parameters": {"max_tokens": 280}
    }
    try:
        r = requests.post(qwen_url, headers=headers, json=body, timeout=20)
        result = r.json()
        return result.get("output", {}).get("text", "解析失败").strip()
    except:
        return "解析出错了"

# 拼消息
msg = "今日新闻简报（政治/财经/科技/体育/文化）\n\n"
for i, item in enumerate(news_list, 1):
    official = f"{i}. {item['title']}\n摘要：{item['desc']}\n链接：{item['link']}\n"
    parse_text = qwen_parse(item['title'] + " " + item['desc'])
    msg += official + f"大白话：{parse_text}\n\n{'-'*30}\n"

if not news_list:
    msg += "今天没抓到新闻（可能API额度用完或网络问题），明天再来看～"

# PushPlus 推送
push_url = f"http://www.pushplus.plus/send?token={PUSHPLUS_TOKEN}&title=每日新闻&content={msg}&template=html"
requests.get(push_url)

print("执行完毕，新闻数：", len(news_list))