import requests
import os
import json
import time

# 从 GitHub Secrets 获取
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

# 优化类别：对应中文常见分类
categories = {
    '政治': 'politics',
    '财经': 'business',
    '科技': 'technology',
    '体育': 'sports',
    '文化': 'entertainment'  # 娱乐+文化
}

news_list = []

for cn_name, en_name in categories.items():
    url = "https://newsdata.io/api/1/latest"
    params = {
        'apikey': NEWSDATA_API_KEY,
        'category': en_name,
        'language': 'zh',
        'size': 1,  # 每类1条，控制长度
        'removeduplicate': '1'
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        if data.get('status') == 'success' and data.get('results'):
            art = data['results'][0]
            news_list.append({
                'category': cn_name,
                'title': art.get('title', '无标题').strip(),
                'desc': (art.get('description') or art.get('content', '无内容'))[:250].strip(),
                'link': art.get('link', '')
            })
        else:
            print(f"{cn_name} 抓取失败")
    except Exception as e:
        print(f"{cn_name} 异常: {e}")

# fallback：如果某类空，用关键词补
if len(news_list) < 4:
    for cn_name, en_name in categories.items():
        if any(item['category'] == cn_name for item in news_list):
            continue
        params = {
            'apikey': NEWSDATA_API_KEY,
            'q': f'中国 {cn_name}',
            'language': 'zh',
            'size': 1
        }
        try:
            resp = requests.get("https://newsdata.io/api/1/latest", params=params, timeout=15)
            data = resp.json()
            if data.get('status') == 'success' and data.get('results'):
                art = data['results'][0]
                news_list.append({
                    'category': cn_name,
                    'title': art.get('title', '无标题').strip(),
                    'desc': (art.get('description') or art.get('content', '无内容'))[:250].strip(),
                    'link': art.get('link', '')
                })
        except:
            pass

# 通义千问解析：升级提示，更像报纸编辑
def qwen_parse(category, title, desc):
    text = f"分类：{category} 标题：{title} 摘要：{desc}"
    qwen_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "qwen-turbo",
        "input": {
            "messages": [
                {"role": "system", "content": "你是一位专业报纸编辑，用简体中文撰写大白话解析。风格：客观、中性、通俗易懂、专业感强，像《人民日报》或《南方周末》风格。只输出解析正文，不要标题、前缀、废话。限120-180字。用自然段落分段，便于阅读。"},
                {"role": "user", "content": f"用大白话专业解析这条新闻：{text}"}
            ]
        },
        "parameters": {"max_tokens": 350}
    }
    try:
        r = requests.post(qwen_url, headers=headers, json=body, timeout=20)
        result = r.json()
        parsed = result.get("output", {}).get("text", "解析失败").strip()
        return parsed
    except Exception as e:
        print(f"Qwen 异常: {e}")
        return "解析出错了"

# 构建 Markdown 格式消息（像报纸）
msg = "# 每日新闻早报\n\n**日期**：今日精选 | **来源**：全球主流媒体聚合\n\n---\n\n"

for item in news_list:
    parse_text = qwen_parse(item['category'], item['title'], item['desc'])
    msg += f"## {item['category']} | {item['title']}\n\n"
    msg += f"**官方摘要**：{item['desc']}\n\n"
    msg += f"**大白话解析**：\n{parse_text}\n\n"
    if item['link']:
        msg += f"[阅读原文]({item['link']})\n\n"
    msg += "---\n\n"

if not news_list:
    msg += "**今日暂无精选新闻**，可能是网络或额度问题，明天见！\n"

msg += "\n\n**小提示**：点链接查看详情。欢迎反馈意见～"

# PushPlus POST 推送（用 markdown 模板）
push_url = "https://www.pushplus.plus/send"

payload = {
    "token": PUSHPLUS_TOKEN,
    "title": "每日新闻早报",
    "content": msg,
    "template": "markdown"  # 关键：markdown 模板，微信渲染超美观
}

success = False
for attempt in range(1, 4):
    try:
        response = requests.post(push_url, json=payload, timeout=20)
        print(f"POST 尝试 {attempt}: 状态 {response.status_code}")
        print(f"返回: {response.text[:300]}...")
        
        if response.status_code == 200:
            resp_json = response.json()
            if resp_json.get("code") == 200:
                print("推送成功！")
                success = True
                break
            else:
                print(f"错误: {resp_json.get('msg')}")
    except Exception as e:
        print(f"异常 {attempt}: {e}")
    
    if attempt < 3:
        time.sleep(8 * attempt)

if not success:
    print("推送失败，但脚本继续")

print("执行完，新闻数：", len(news_list))
