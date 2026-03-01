import requests
import os
import json
import time
from datetime import datetime

# 从 GitHub Secrets 获取密钥
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

# 新闻板块定义（每个板块目标至少2条）
categories = [
    {'cn': '国际政治', 'q': '中国 OR China OR world politics OR international relations OR geopolitics'},
    {'cn': '财经经济', 'q': '中国经济 OR China economy OR global market OR finance OR stock OR trade'},
    {'cn': '科技前沿', 'q': '中国科技 OR AI China OR tech innovation OR semiconductor OR quantum'},
    {'cn': '体育赛事', 'q': '中国体育 OR world sports OR Olympics OR football OR basketball OR tennis'},
    {'cn': '文化娱乐', 'q': '中国文化 OR global culture OR entertainment OR movie OR music OR festival'},
    {'cn': '社会民生', 'q': '中国社会 OR China society OR livelihood OR education OR housing OR employment'},
    {'cn': '健康医疗', 'q': '中国医疗 OR health China OR medicine OR public health OR vaccine OR aging'},
    {'cn': '环境气候', 'q': '中国环境 OR climate change OR carbon neutral OR ecology OR pollution OR renewable energy'}
]

news_list = []

for cat in categories:
    url = "https://newsdata.io/api/1/latest"
    params = {
        'apikey': NEWSDATA_API_KEY,
        'q': cat['q'],
        'language': 'zh',
        'size': 3,               # 多取一些，筛选保留高质量的
        'removeduplicate': '1'
    }

    try:
        resp = requests.get(url, params=params, timeout=18)
        data = resp.json()

        if data.get('status') == 'success' and data.get('results'):
            valid_articles = []
            for art in data['results'][:3]:  # 每个板块最多3条
                title = art.get('title', '').strip()
                desc = (art.get('description') or art.get('content', '')).strip()[:320]
                link = art.get('link', '')
                img_url = art.get('image_url', '')

                # 过滤低质量
                if len(title) > 8 and len(desc) > 30 and 'http' in link:
                    valid_articles.append({
                        'category': cat['cn'],
                        'title': title,
                        'desc': desc,
                        'link': link,
                        'img_url': img_url if img_url and img_url.startswith('https://') else '',
                        'lang': art.get('language', 'zh')
                    })

            # 确保至少2条
            if len(valid_articles) >= 2:
                news_list.extend(valid_articles[:3])
            else:
                news_list.extend(valid_articles)

    except Exception as e:
        print(f"板块 {cat['cn']} 获取失败: {e}")

# 全局补齐，确保总新闻 ≥15 条
if len(news_list) < 15:
    extra_params = {
        'apikey': NEWSDATA_API_KEY,
        'q': '中国 OR China OR world news OR global hot OR breaking',
        'size': 20,
        'language': 'zh'
    }
    try:
        resp = requests.get("https://newsdata.io/api/1/latest", params=extra_params, timeout=18)
        data = resp.json()
        if data.get('status') == 'success' and data.get('results'):
            for art in data['results']:
                if len(news_list) >= 20:  # 上限
                    break
                title = art.get('title', '').strip()
                desc = (art.get('description') or art.get('content', '')).strip()[:320]
                link = art.get('link', '')
                img_url = art.get('image_url', '')

                if len(title) > 8 and len(desc) > 30 and 'http' in link:
                    if not any(n['link'] == link for n in news_list):
                        news_list.append({
                            'category': '综合要闻',
                            'title': title,
                            'desc': desc,
                            'link': link,
                            'img_url': img_url if img_url and img_url.startswith('https://') else '',
                            'lang': art.get('language', 'zh')
                        })
    except Exception as e:
        print(f"全局补齐失败: {e}")

# 通义千问处理函数（输出官方摘要、专业解析、白话解析）
def qwen_process(item):
    text = f"语言：{item['lang']} 分类：{item['category']} 标题：{item['title']} 摘要：{item['desc']}"
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "qwen-turbo",
        "input": {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一位资深中文报纸编辑。用简体中文处理新闻：\n"
                        "1. 如果原文非中文，先给出简洁的中文翻译作为官方摘要（标题+核心内容）。否则，直接用原文摘要作为官方摘要。\n"
                        "2. 撰写专业解析（专家视角）：客观、中性、深入分析背景、影响，风格如社论，字数120-180字，分2-3段。\n"
                        "3. 撰写白话解析（普通人视角）：通俗易懂、接地气、像聊天解释，字数100-150字，分2-3段。\n"
                        "只输出以下严格格式，无任何前缀、多余符号或说明：\n"
                        "【官方摘要】\n正文\n"
                        "【专业解析】\n正文\n"
                        "【白话解析】\n正文"
                    )
                },
                {"role": "user", "content": f"处理这条新闻：{text}"}
            ]
        },
        "parameters": {"max_tokens": 650, "temperature": 0.7}
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=28)
        result = r.json()
        output = result.get("output", {}).get("text", "解析失败").strip()
        return output
    except Exception as e:
        print(f"Qwen 处理异常: {e}")
        return "【官方摘要】\n解析服务暂不可用\n【专业解析】\n暂无\n【白话解析】\n暂无"

# 构建内容（高级报纸排版：HTML + 内联CSS，标题醒目、正文清晰）
today = datetime.now().strftime('%Y年%m月%d日')

msg = f"""
<div style="font-family: 'SimSun', serif; max-width: 100%; margin: 0 auto; padding: 15px; border: 1px solid #ddd; background-color: #f9f9f9; border-radius: 8px;">
    <h1 style="text-align: center; color: #333; margin-bottom: 5px; font-size: 24px; border-bottom: 2px solid #ccc; padding-bottom: 10px;">每日新闻早报</h1>
    <p style="text-align: center; color: #666; font-size: 14px; margin: 0;">日期：{today}　来源：全球主流媒体聚合</p>
    <hr style="border: 0; border-top: 1px dashed #ccc; margin: 15px 0;">
"""

current_category = ''
for item in news_list:
    parsed = qwen_process(item)

    if item['category'] != current_category:
        msg += f"""
        <h2 style="color: #444; font-size: 20px; margin-top: 25px; border-left: 5px solid #007bff; padding-left: 10px;">{item['category']}</h2>
        """
        current_category = item['category']

    msg += f"""
    <div style="margin-bottom: 20px; padding: 10px; background-color: #fff; border: 1px solid #eee; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <h3 style="color: #222; font-size: 18px; margin: 0 0 10px 0;">{item['title']}</h3>
        {('<img src="' + item['img_url'] + '" alt="配图" style="max-width:100%; height:auto; display:block; margin:0 auto 10px; border-radius:4px;">' if item['img_url'] else '')}
        <p style="font-size: 14px; line-height: 1.6; color: #555; margin: 5px 0;"><strong>官方摘要：</strong> {parsed.split('【专业解析】')[0].replace('【官方摘要】\n', '').strip()}</p>
        <p style="font-size: 14px; line-height: 1.6; color: #555; margin: 5px 0;"><strong>专业解析：</strong> {parsed.split('【专业解析】\n')[1].split('【白话解析】')[0].strip()}</p>
        <p style="font-size: 14px; line-height: 1.6; color: #555; margin: 5px 0;"><strong>白话解析：</strong> {parsed.split('【白话解析】\n')[1].strip()}</p>
        <p style="text-align: right; margin-top: 10px;"><a href="{item['link']}" style="color: #007bff; text-decoration: none; font-size: 13px;">阅读原文 →</a></p>
    </div>
    """

msg += """
    <hr style="border: 0; border-top: 1px dashed #ccc; margin: 15px 0;">
    <p style="text-align: center; font-size: 12px; color: #888; margin: 0;">来源：NewsData.io（Reuters、BBC、CNN、澎湃、财新、新华社等）</p>
    <p style="text-align: center; font-size: 12px; color: #888; margin: 0;">推送时间：每日北京时间早8:30　欢迎反馈意见</p>
</div>
"""

# PushPlus 发送
push_url = "https://www.pushplus.plus/send"
payload = {
    "token": PUSHPLUS_TOKEN,
    "title": f"每日新闻早报 {today}",
    "content": msg,
    "template": "html"
}

success = False
for attempt in range(1, 4):
    try:
        response = requests.post(push_url, json=payload, timeout=22)
        print(f"推送尝试 {attempt} | 状态码: {response.status_code}")
        print(f"返回: {response.text[:280]}...")

        if response.status_code == 200:
            try:
                resp_json = response.json()
                if resp_json.get("code") == 200:
                    print("推送成功")
                    success = True
                    break
            except:
                if "请求成功" in response.text or "200" in response.text:
                    print("推送可能成功（非标准响应）")
                    success = True
                    break
    except Exception as e:
        print(f"推送异常 {attempt}: {str(e)}")

    if attempt < 3:
        time.sleep(12)

if not success:
    print("推送未确认成功，但脚本已完成")

print(f"执行结束　新闻总数：{len(news_list)}")
