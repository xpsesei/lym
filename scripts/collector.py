import os
import json
import hashlib
import feedparser
import requests
from datetime import datetime, timezone
from openai import OpenAI

# 覆盖全球 AI、Crypto、海外银行、VPS 及开发者资源的官方与高权重 RSS 源
RSS_SOURCES = [
    {"name": "OpenAI News", "url": "https://openai.com/news/rss.xml", "default_cat": "AI订阅优惠"},
    {"name": "Anthropic News", "url": "https://www.anthropic.com/news/rss.xml", "default_cat": "AI订阅优惠"},
    {"name": "Binance Announcement", "url": "https://www.binance.com/en/support/announcement/rss", "default_cat": "Crypto"},
    {"name": "Cloudflare Blog", "url": "https://blog.cloudflare.com/rss/", "default_cat": "VPS及云服务"},
    {"name": "GitHub Blog", "url": "https://github.blog/feed/", "default_cat": "VPS及云服务"},
    {"name": "Product Hunt", "url": "https://www.producthunt.com/feed", "default_cat": "软件与数字服务"},
    {"name": "Hacker News Deals/Free", "url": "https://hnrss.org/newest?q=free+OR+credit+OR+airdrop+OR+bonus", "default_cat": "其他优惠"}
]

ACTIVE_FILE = "data/active_deals.json"
ARCHIVE_FILE = "data/archived_deals.json"

client = OpenAI(
    api_key=os.environ.get("LLM_API_KEY"),
    base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
)
MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

# 通知配置
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
FEISHU_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")

SYSTEM_PROMPT = """
你是一个严谨的全球金融与科技优惠情报分析师。从原始内容中提取符合以下7大领域的真实优惠：
1. AI订阅优惠
2. Crypto
3. U卡
4. 海外银行
5. VPS及云服务
6. 软件与数字服务
7. 其他值得关注的全球优惠活动

【严格红线】：
1. 绝对不要编造优惠！如无真实优惠返回 {"is_valid_deal": false}。
2. 明确门槛标签（threshold_tag）：【真正免费】、【免费试用】、【需要充值】、【需要交易量】、【需要邀请】。
3. 评估实际价值（value_score: 1-100整数，用于排行榜排序；value_desc: 描述如 "$200 额度"）。
4. 无法确认截止日期或官方链接的标注“待核实”。

请严格输出 JSON：
{
  "is_valid_deal": true,
  "title": "活动名称",
  "category": "必须严格匹配7大领域之一",
  "offer_detail": "优惠内容",
  "value_desc": "实际价值描述",
  "value_score": 85,
  "threshold_tag": "真正免费 | 免费试用 | 需要充值 | 需要交易量 | 需要邀请",
  "requirements": "参与条件与隐藏门槛",
  "region": "适用地区",
  "start_date": "YYYY-MM-DD 或 待核实",
  "end_date": "YYYY-MM-DD 或 长期有效 或 待核实",
  "steps": ["步骤1", "步骤2"],
  "official_url": "原始链接",
  "source": "来源名称",
  "risk_warning": "风险提示"
}
"""

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
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]

def send_push_notification(deal):
    msg = f"🔥 【高价值优惠情报雷达】\n\n📌 名称: {deal['title']}\n📂 分类: {deal['category']}\n💰 价值: {deal['value_desc']} (评分: {deal['value_score']})\n🏷️ 门槛: {deal['threshold_tag']}\n⏰ 截止: {deal['end_date']}\n🔗 链接: {deal['official_url']}"
    
    # Telegram 推送
    if TG_TOKEN and TG_CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={
                "chat_id": TG_CHAT_ID,
                "text": msg,
                "disable_web_page_preview": True
            }, timeout=10)
        except Exception as e:
            print(f"Telegram 推送失败: {e}")

    # 飞书 Webhook 推送
    if FEISHU_URL:
        try:
            requests.post(FEISHU_URL, json={
                "msg_type": "text",
                "content": {"text": msg}
            }, timeout=10)
        except Exception as e:
            print(f"飞书推送失败: {e}")

def analyze_with_ai(entry, source_name):
    content = f"标题: {entry.get('title', '')}\n链接: {entry.get('link', '')}\n摘要: {entry.get('summary', '')[:1500]}"
    try:
        response = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"来源: {source_name}\n\n{content}"}
            ],
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"AI 分析失败: {e}")
        return {"is_valid_deal": False}

def main():
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
        feed = feedparser.parse(src["url"])
        for entry in feed.entries[:8]:
            deal_id = generate_id(entry.get("title", ""), entry.get("link", ""))
            if deal_id in existing_ids:
                continue

            parsed = analyze_with_ai(entry, src["name"])
            if parsed.get("is_valid_deal"):
                parsed["id"] = deal_id
                parsed["created_at"] = today_date
                parsed["last_verified"] = now_str
                if not parsed.get("official_url"):
                    parsed["official_url"] = entry.get("link", "")
                
                active_deals.insert(0, parsed)
                existing_ids.add(deal_id)
                new_added_count += 1

                # 高价值（>=85分）触发即时推送
                if parsed.get("value_score", 0) >= 85:
                    send_push_notification(parsed)

    active_deals.sort(key=lambda x: (x.get("created_at") == today_date, x.get("value_score", 0)), reverse=True)
    save_json(ACTIVE_FILE, active_deals)
    save_json(ARCHIVE_FILE, archived_deals[:500])
    print(f"采集完成，新增有效优惠: {new_added_count} 条")

if __name__ == "__main__":
    main()
