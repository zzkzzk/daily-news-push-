import requests
import os
import json
import time

# 从 GitHub Secrets 获取密钥
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

# 新闻类别
categories = ['politics', 'business', 'technology', 'sports', 'entertainment']

news_list = []

for cat in categories:
    url = "https://newsdata.io/api/1/latest"
    params = {
        'apikey': NEWSDATA_API_KEY,
        'category': cat,
        'language': 'zh',          # 优先中文
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
        else:
            print(f"抓取 {cat} 失败: {data.get('message', '未知错误')}")
    except Exception as e:
        print(f"抓取 {cat} 异常: {e}")

# 如果中文新闻少，fallback 加关键词
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
            print(f"fallback {cat} 异常: {e}")

# 通义千问 大白话解析函数
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
        parsed = result.get("output", {}).get("text", "解析失败").strip()
        return parsed
    except Exception as e:
        print(f"Qwen 解析异常: {e}")
        return "解析出错了"

# 构建消息内容
msg = "今日新闻简报（政治/财经/科技/体育/文化）\n\n"
for i, item in enumerate(news_list, 1):
    official = f"{i}. {item['title']}\n摘要：{item['desc']}\n链接：{item['link']}\n"
    parse_text = qwen_parse(item['title'] + " " + item['desc'])
    msg += official + f"大白话：{parse_text}\n\n{'-'*50}\n\n"

if not news_list:
    msg += "今天没抓到新闻（可能API额度用完或网络问题），明天再来看～"

# PushPlus 推送 - 使用 POST 方法，避免 414 URI Too Large
push_url = "https://www.pushplus.plus/send"

payload = {
    "token": PUSHPLUS_TOKEN,
    "title": "每日新闻推送",
    "content": msg,
    "template": "html"  # 或改成 "txt" 如果不想 html 格式
}

success = False
for attempt in range(1, 4):
    try:
        response = requests.post(push_url, json=payload, timeout=20)
        print(f"PushPlus POST 尝试 {attempt}: 状态码 {response.status_code}")
        print(f"PushPlus 返回内容: {response.text[:400]}...")  # 打印前400字符
        
        if response.status_code == 200:
            try:
                resp_json = response.json()
                if resp_json.get("code") == 200:
                    print("推送成功！code=200")
                    success = True
                    break
                else:
                    print(f"业务错误: {resp_json.get('msg', '未知')}")
            except:
                print("响应不是 JSON，但状态码200，可能已接收")
                success = True
                break
    except Exception as e:
        print(f"POST 尝试 {attempt} 异常: {str(e)}")
    
    if attempt < 3:
        time.sleep(10 * attempt)  # 10s, 20s 退避

if not success:
    print("推送最终失败，但脚本继续执行（不影响 workflow）")

print("脚本执行完毕，抓取新闻数量：", len(news_list))
