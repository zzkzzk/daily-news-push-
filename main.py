import requests
import os
import json
import time

# 从 GitHub Secrets 获取
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

# 要抓的新闻类别
categories = ['politics', 'business', 'technology', 'sports', 'entertainment']

news_list = []

for cat in categories:
    url = "https://newsdata.io/api/1/latest"
    params = {
        'apikey': NEWSDATA_API_KEY,
        'category': cat,
        'language': 'zh',
        'size': 1,
        'removeduplicate': '1'
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        if data.get('status') == 'success' and data.get('results'):
            art = data['results'][0]
            news_list.append({
                'title': art.get('title', '无标题'),
                'desc': (art.get('description') or art.get('content', '无内容'))[:300],
                'link': art.get('link', '无链接')
            })
    except Exception as e:
        print(f"抓取 {cat} 新闻失败: {e}")

# fallback 如果中文少
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
                    'desc': (art.get('description') or art.get('content', '无内容'))[:300],
                    'link': art.get('link', '无链接')
                })
        except Exception as e:
            print(f"fallback {cat} 失败: {e}")

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
    except Exception as e:
        print(f"Qwen 解析失败: {e}")
        return "解析出错了"

# 拼消息
msg = "今日新闻简报（政治/财经/科技/体育/文化）\n\n"
for i, item in enumerate(news_list, 1):
    official = f"{i}. {item['title']}\n摘要：{item['desc']}\n链接：{item['link']}\n"
    parse_text = qwen_parse(item['title'] + " " + item['desc'])
    msg += official + f"大白话：{parse_text}\n\n{'-'*40}\n"

if not news_list:
    msg += "今天没抓到新闻（可能API额度或网络问题），明天再来看～"

# PushPlus 推送 - 加强版：https + 重试 + 超时 + 日志
push_url = f"https://www.pushplus.plus/send?token={PUSHPLUS_TOKEN}&title=每日新闻&content={msg}&template=html"

success = False
for attempt in range(1, 4):
    try:
        response = requests.get(push_url, timeout=20)
        print(f"PushPlus 尝试 {attempt}: 状态码 {response.status_code}")
        print(f"PushPlus 返回: {response.text[:200]}...")  # 打印前200字符看结果
        if response.status_code == 200:
            success = True
            break
    except Exception as e:
        print(f"推送尝试 {attempt} 失败: {str(e)}")
    
    if attempt < 3:
        time.sleep(10 * attempt)  # 指数退避：10s, 20s

if not success:
    print("推送最终失败，但脚本继续（不影响 workflow 成功）")
    # 可以加 print(msg) 来日志看内容对不对

print("执行完毕，新闻数：", len(news_list))
