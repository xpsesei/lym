import sys
import io

# 强制标准输出和错误输出为 UTF-8，彻底杜绝终端乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import json
import hashlib
import feedparser
import requests
from datetime import datetime, timezone

# 🌍 覆盖全球 AI, Crypto, 海外银行, VPS, 开发者资源及全球“撸羊毛”的高权重 RSS 源
RSS_SOURCES = [
    {"name": "OpenAI News", "url": "https://openai.com/news/rss.xml", "default_cat": "AI订阅优惠"},
    {"name": "Anthropic News", "url": "https://www.anthropic.com/news/rss.xml", "default_cat": "AI订阅优惠"},
    {"name": "Binance Announcement", "url": "https://www.binance.com/en/support/announcement/rss", "default_cat": "Crypto"},
    {"name": "Cloudflare Blog", "url": "https://blog.cloudflare.com/rss/", "default_cat": "VPS及云服务"},
    {"name": "GitHub Blog", "url": "https://github.blog/feed/", "default_cat": "VPS及云服务"},
    {"name": "Product Hunt", "url": "https://www.producthunt.com/feed", "default_cat": "软件与数字服务"},
    {"name": "Hacker News (Free/Deals)", "url": "https://hnrss.org/newest?q=free+OR+credit+OR+airdrop+OR+bonus+OR+giveaway", "default_cat": "其他优惠"},
    {"name": "Reddit Freebies", "url": "https://www.reddit.com/r/freebies/.rss", "default_cat": "软件与数字服务"},
    {"name": "Reddit Deals", "url": "https://www.reddit.com/r/deals/.rss", "default_cat": "其他优惠"}
]

ACTIVE_FILE = "data/active_deals.json"
ARCHIVE_FILE = "data/archived_deals.json"

# 🛡️ 获取环境变量，并强力清洗所有换行符、空格、引号，防止 Header 注入报错
API_KEY = os.environ.get("LLM_API_KEY", "").strip().strip('"').strip("'").replace("\n", "").replace("\r", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "").strip().strip('"').strip("'").replace("\n", "").replace("\r", "").rstrip('/')
MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini").strip().strip('"').strip("'").replace("\n", "").replace("\r", "")

# 智能容错：如果用户未配置 BASE_URL，自动使用官方默认地址
if not BASE_URL or not BASE_URL.startswith("http"):
    BASE_URL = "https://api.openai.com/v1"

if not MODEL:
    MODEL = "gpt-4o-mini"

client_base_url = BASE_URL

# 通知配置（同样进行防错清洗）
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip().strip('"').strip("'").replace("\n", "").replace("\r", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip().strip('"').strip("'").replace("\n", "").replace("\r", "")
FEISHU_URL = os.environ.get("FEISHU_WEBHOOK_URL", "").strip().strip('"').strip("'").replace("\n", "").replace("\r", "")

SYSTEM_PROMPT = """
你是一个精通全球“撸羊毛”、免费资源、限时活动、空投与金融优惠的情报分析专家。
请从原始内容中提取符合以下7大领域的真实活动：
1. AI订阅优惠
2. Crypto (空投、测试网、积分、交易所活动)
3. U卡 (海外虚拟卡、实体卡、返现、开卡奖励)
4. 海外银行 (开户奖励、存款优惠、推荐奖励)
5. VPS及云服务 (免费服务器、云计算额度、域名)
6. 软件与数字服务 (免费试用、终身会员、开发者福利)
7. 其他值得关注的全球优惠活动

【严格质量红线】：
1. 绝对不要编造优惠！如无明确优惠信息返回 {"is_valid_deal": false}。
2. 必须明确标出门槛类型（threshold_tag）：【真正免费】、【免费试用】、【需要充值】、【需要交易量】、【需要邀请】。
3. 评估实际价值（value_score: 1-100整数，用于排行榜排序；value_desc: 具体金额或权益如 "$100 算力额度"）。
4. 无法确认截止日期或官方链接的标注“待核实”。

请严格输出合法的 JSON 格式：
{
  "is_valid_deal": true,
  "title": "活动名称",
  "category": "必须严格匹配上述7大类别之一",
  "offer_detail": "优惠内容详细描述",
  "value_desc": "实际价值描述",
  "value_score": 85,
  "threshold_tag": "真正免费 | 免费试用 | 需要充值 | 需要交易量 | 需要邀请",
  "requirements": "参与条件与隐藏门槛",
  "region": "适用国家或地区",
  "start_date": "YYYY-MM-DD 或 待核实",
  "end_date": "YYYY-MM-DD 或 长期有效 或 待核实",
  "steps": ["步骤1", "步骤2"],
  "official_url": "原始链接",
  "source": "来源名称",
  "risk_warning": "风险提示"
}
"""

def clean_text(text):
    if not text:
        return ""
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='ignore')
    
    safe_chars = []
    for c in text:
        if c.isprintable() or c in ('\n', '\t'):
            safe_chars.append(c)
        else:
            safe_chars.append(' ')
    text = "".join(safe_chars)
    
    for char in ['\u200b', '\u200c', '\u200d', '\ufeff', '\u2060', '\u00ad', '\r', '\u200e', '\u200f']:
        text = text.replace(char, '')
        
    return text.strip()

def call_universal_llm(prompt_text):
    url = f"{client_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=40)
        if response.status_code == 200:
            result_json = response.json()
            content = result_json["choices"][0]["message"]["content"]
            return json.loads(content)
        else:
            print(f"LLM API 状态码异常 ({response.status_code}): {response.text[:120]}")
    except Exception as e:
        print(f"LLM 请求异常: {str(e)[:120]}")
    
    return {"is_valid_deal": False}

def load_json(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_id(title, url):
    raw = f"{title.strip().lower()}_{url.strip().lower()}"
    return hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]

def send_push_notification(deal):
    msg = f"🔥 【全球高价值羊毛/优惠情报】\n\n📌 名称: {deal['title']}\n📂 分类: {deal['category']}\n💰 价值: {deal['value_desc']} (评分: {deal['value_score']})\n🏷️ 门槛: {deal['threshold_tag']}\n⏰ 截止: {deal['end_date']}\n🔗 链接: {deal['official_url']}"
    
    if TG_TOKEN and TG_CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={
                "chat_id": TG_CHAT_ID,
                "text": msg,
                "disable_web_page_preview": True
            }, timeout=10)
        except Exception:
            pass

    if FEISHU_URL:
        try:
            requests.post(FEISHU_URL, json={
                "msg_type": "text",
                "content": {"text": msg}
            }, timeout=10)
        except Exception:
            pass

def main():
    if not API_KEY or API_KEY.startswith("***"):
        print("【致命错误】LLM_API_KEY 无效！请检查 GitHub 仓库 Secrets 中是否填入了真实的 API Key（而不是掩码或带空格）。")
        return

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    active_deals = load_json(ACTIVE_FILE)
    archived_deals = load_json(ARCHIVE_FILE)

    # 1. 自动归档过期活动
    still_active = []
    for deal in active_deals:
        end_date = deal.get("end_date", "")
        if len(end_date) == 10 and end_date < today_date:
            deal["status"] = "已结束"
            archived_deals.insert(0, deal)
        else:
            still_active.append(deal)
    active_deals = still_active

    existing_ids = {d["id"] for d in active_deals} | {d["id"] for d in archived_deals}

    # 2. 抓取与 AI 验证
    new_added_count = 0
    for src in RSS_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:8]:
                title = clean_text(entry.get("title", ""))
                link = clean_text(entry.get("link", ""))
                summary = clean_text(entry.get("summary", entry.get("description", "")))
                
                if not title or not link:
                    continue
                    
                deal_id = generate_id(title, link)
                if deal_id in existing_ids:
                    continue

                prompt_content = f"来源: {src['name']}\n标题: {title}\n链接: {link}\n摘要: {summary[:1500]}"
                parsed = call_universal_llm(prompt_content)
                
                if parsed.get("is_valid_deal"):
                    parsed["id"] = deal_id
                    parsed["created_at"] = today_date
                    parsed["last_verified"] = now_str
                    if not parsed.get("official_url"):
                        parsed["official_url"] = link
                    
                    active_deals.insert(0, parsed)
                    existing_ids.add(deal_id)
                    new_added_count += 1

                    if parsed.get("value_score", 0) >= 85:
                        send_push_notification(parsed)
        except Exception as e:
            print(f"解析源 {src['name']} 失败: {str(e)[:100]}")

    active_deals.sort(key=lambda x: (x.get("created_at") == today_date, x.get("value_score", 0)), reverse=True)
    save_json(ACTIVE_FILE, active_deals)
    save_json(ARCHIVE_FILE, archived_deals[:500])
    print(f"采集完成，新增有效优惠/羊毛: {new_added_count} 条")

if __name__ == "__main__":
    main()
