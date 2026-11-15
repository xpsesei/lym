import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import json
import hashlib
import time
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# 🌐 全网超级海量 RSS 源（覆盖 VPS、云服务、Crypto、U卡、银行、免费资源、开发者限免）
RSS_SOURCES = [
    # --- AI 与开发者技术 ---
    {"name": "OpenAI News", "url": "https://openai.com/news/rss.xml", "default_cat": "AI订阅优惠"},
    {"name": "Anthropic News", "url": "https://www.anthropic.com/news/rss.xml", "default_cat": "AI订阅优惠"},
    {"name": "GitHub Blog", "url": "https://github.blog/feed/", "default_cat": "VPS及云服务"},
    {"name": "Cloudflare Blog", "url": "https://blog.cloudflare.com/rss/", "default_cat": "VPS及云服务"},
    {"name": "Product Hunt", "url": "https://www.producthunt.com/feed", "default_cat": "软件与数字服务"},
    
    # --- VPS 与服务器特惠源 (海量增加) ---
    {"name": "LowEndBox (VPS Deals)", "url": "https://lowendbox.com/feed/", "default_cat": "VPS及云服务"},
    {"name": "WHT (Web Hosting Talk Deals)", "url": "https://www.webhostingtalk.com/syndication.php?limit=25&forma=rss", "default_cat": "VPS及云服务"},
    {"name": "Vpsmm (VPS优惠)", "url": "https://www.vpsmm.com/feed", "default_cat": "VPS及云服务"},
    {"name": "NodeSeek Latest", "url": "https://www.nodeseek.com/rss", "default_cat": "VPS及云服务"},

    # --- Crypto 与空投资讯源 ---
    {"name": "Binance Announcement", "url": "https://www.binance.com/en/support/announcement/rss", "default_cat": "Crypto"},
    {"name": "CoinDesk News", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "default_cat": "Crypto"},
    {"name": "Decrypt Co", "url": "https://decrypt.co/feed", "default_cat": "Crypto"},
    {"name": "CoinTelegraph RSS", "url": "https://cointelegraph.com/rss", "default_cat": "Crypto"},
    {"name": "Blockworks RSS", "url": "https://blockworks.co/feed", "default_cat": "Crypto"},

    # --- 软件、限免、绝对免费资源与综合折扣源 ---
    {"name": "Reddit Freebies", "url": "https://www.reddit.com/r/freebies/.rss", "default_cat": "软件与数字服务"},
    {"name": "Reddit Deals", "url": "https://www.reddit.com/r/deals/.rss", "default_cat": "其他优惠"},
    {"name": "Reddit AppHookUp", "url": "https://www.reddit.com/r/AppHookUp/.rss", "default_cat": "软件与数字服务"},
    {"name": "Reddit FreeGameFindings", "url": "https://www.reddit.com/r/freeGameFindings/.rss", "default_cat": "软件与数字服务"},
    {"name": "BetaList (Startups)", "url": "https://betalist.com/feed", "default_cat": "软件与数字服务"},
    {"name": "OzBargain (Global Tech Deals)", "url": "https://www.ozbargain.com.au/feed", "default_cat": "其他优惠"},
    {"name": "Hacker News (Free/Deals)", "url": "https://hnrss.org/newest?q=free+OR+credit+OR+airdrop+OR+bonus+OR+giveaway", "default_cat": "其他优惠"}
]

# 📱 超级海量公开 Telegram 频道源（全网覆盖 U卡、海外银行、VPS特惠、空投、免费资源、科技数码羊毛）
TG_CHANNELS = [
    "ahmivaults",          # 核心指定频道
    "vps_deals",           # 全球 VPS 优惠
    "freevps",             # 免费与特价云服务器
    "airdropinspect",      # 热门空投监测
    "CryptoAirdrops",      # 空投线报
    "Ucard_news",          # U卡与虚拟卡资讯
    "DealHunt",            # 全球数码与软件折扣
    "bank_accounts_deals", # 海外银行与开户奖励
    "freebies_tg",         # 全球免费资源线报
    "crypto_airdrops_free",# 零撸空投
    "vps_chat",            # VPS 交流与特价通知
    "free_vps",            # 免费云服务器
    "airdrop_alert",       # 空投提醒
    "virtual_cards",       # 虚拟卡与U卡福利
    "tech_deals",          # 科技数码折扣
    "giveaways_hub"        # 全球福利抽奖与羊毛
]

ACTIVE_FILE = "data/active_deals.json"
ARCHIVE_FILE = "data/archived_deals.json"

# 🛡️ 智能清洗环境变量
raw_api_key = os.environ.get("LLM_API_KEY", "").strip()
for sep in [' ', '\n', '\r', '\t', 'LLM_']:
    if sep in raw_api_key:
        raw_api_key = raw_api_key.split(sep)[0]
API_KEY = "".join(c for c in raw_api_key if c.isprintable() and c not in (' ', '\t', '\n', '\r')).strip('"').strip("'")

raw_base_url = os.environ.get("LLM_BASE_URL", "").strip()
if "https://" in raw_base_url:
    start_idx = raw_base_url.find("https://")
    raw_base_url = raw_base_url[start_idx:]
    for sep in [' ', '\n', '\r', '\t', 'LLM_']:
        if sep in raw_base_url:
            raw_base_url = raw_base_url.split(sep)[0]
BASE_URL = "".join(c for c in raw_base_url if c.isprintable() and c not in (' ', '\t', '\n', '\r')).strip('"').strip("'").rstrip('/')

raw_model = os.environ.get("LLM_MODEL", "").strip()
for sep in [' ', '\n', '\r', '\t', 'LLM_']:
    if sep in raw_model:
        raw_model = raw_model.split(sep)[0]
MODEL = "".join(c for c in raw_model if c.isprintable() and c not in (' ', '\t', '\n', '\r')).strip('"').strip("'")

if not BASE_URL or not BASE_URL.startswith("http"):
    BASE_URL = "https://api.deepseek.com/v1"
if not MODEL:
    MODEL = "deepseek-chat"

client_base_url = BASE_URL

# 💡 宽松高效的 AI 判定提示词
SYSTEM_PROMPT = """
你是一个精通全球“撸羊毛”、免费资源、限时活动、VPS促销、软件折扣与空投的情报分析专家。
请从给定的文章标题、摘要或社交媒体正文中提取任何有价值的优惠、促销、空投或免费资源信息。

只要内容包含以下任何一种元素，即判定为有效活动 (is_valid_deal: true)：
1. VPS / 服务器降价、促销、特价套餐、黑五优惠。
2. AI 订阅折扣、额度赠送、限免。
3. Crypto 积分、空投、白名单、交易所活动。
4. U卡 / 海外银行开户奖励、返现。
5. 软件、App、游戏限免或终身会员折扣。
6. 其他任何免费资源、福利、礼品卡、羊毛线报。

【判定规则】：
- 只要有促销意图或价值，即使部分字段缺失，也请尽量提取并归类，不要轻易返回 false！
- 只有纯技术新闻、纯资讯报道、与优惠完全无关的公告才返回 {"is_valid_deal": false}。

请严格输出合法的 JSON 格式：
{
  "is_valid_deal": true,
  "title": "活动简明名称",
  "category": "必须严格匹配以下7大类别之一: 【AI订阅优惠】、【Crypto】、【U卡】、【海外银行】、【VPS及云服务】、【软件与数字服务】、【其他优惠】",
  "offer_detail": "优惠内容的具体描述（如配置、价格、折扣力度）",
  "value_desc": "实际价值或优惠力度（例如：$3.5/月、送50积分、限时免费）",
  "value_score": 75,
  "threshold_tag": "真正免费 | 免费试用 | 需要充值 | 需要交易量 | 需要邀请 | 限时促销",
  "requirements": "参与条件或说明",
  "region": "全球或适用地区",
  "start_date": "待核实",
  "end_date": "长期有效",
  "steps": ["查看活动链接", "按页面指引参与"],
  "official_url": "原始链接",
  "source": "来源名称",
  "risk_warning": "请自行评估风险"
}
"""

def clean_text(text):
    if not text:
        return ""
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='ignore')
    safe_chars = [c for c in text if c.isprintable() or c in ('\n', '\t')]
    text = "".join(safe_chars)
    for char in ['\u200b', '\u200c', '\u200d', '\ufeff', '\u2060', '\u00ad', '\r', '\u200e', '\u200f']:
        text = text.replace(char, '')
    return text.strip()

def call_universal_llm(prompt_text):
    url = f"{client_base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
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
            return json.loads(response.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"LLM 请求异常: {str(e)[:120]}", file=sys.stderr)
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

def fetch_telegram_channel_entries(channel_username):
    entries = []
    url = f"https://t.me/s/{channel_username}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            messages = soup.find_all('div', class_='tgme_widget_message')
            # 💡 深度扩大到最近 25 条消息
            for msg in messages[-25:]:
                text_div = msg.find('div', class_='tgme_widget_message_text')
                if not text_div:
                    continue
                content = clean_text(text_div.get_text(separator="\n", strip=True))
                if not content:
                    continue
                link_a = msg.find('a', class_='tgme_widget_message_date')
                post_link = link_a['href'] if link_a and link_a.has_attr('href') else f"https://t.me/{channel_username}"
                first_line = content.split('\n')[0]
                title = first_line[:50] if len(first_line) > 3 else f"Telegram 推送 (@{channel_username})"
                entries.append({"title": title, "link": post_link, "summary": content})
    except Exception as e:
        print(f"抓取 Telegram 频道 @{channel_username} 异常: {str(e)[:100]}")
    return entries

def main():
    if not API_KEY or len(API_KEY) < 10:
        print("❌ API Key 无效或为空！")
        return

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    active_deals = load_json(ACTIVE_FILE)
    archived_deals = load_json(ARCHIVE_FILE)

    existing_ids = {d["id"] for d in active_deals} | {d["id"] for d in archived_deals}
    new_added_count = 0

    # 1. 采集 RSS 源 (💡 深度扩大到每源前 20 条)
    for src in RSS_SOURCES:
        try:
            print(f"正在检查 RSS 源: {src['name']} ...")
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:20]:
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
                    print(f"  -> 🎉 成功捕获新羊毛: {parsed.get('title')}")
                time.sleep(0.3)
        except Exception as e:
            print(f"解析源 {src['name']} 失败: {str(e)[:100]}")

    # 2. 采集 Telegram 公开频道
    for ch in TG_CHANNELS:
        try:
            print(f"正在检查 Telegram 频道: @{ch} ...")
            tg_entries = fetch_telegram_channel_entries(ch)
            for entry in tg_entries:
                title = entry["title"]
                link = entry["link"]
                summary = entry["summary"]
                
                deal_id = generate_id(title, link)
                if deal_id in existing_ids:
                    continue

                prompt_content = f"Telegram Channel @{ch}\n标题: {title}\n链接: {link}\n正文: {summary[:1500]}"
                parsed = call_universal_llm(prompt_content)
                
                if parsed.get("is_valid_deal"):
                    parsed["id"] = deal_id
                    parsed["created_at"] = today_date
                    parsed["last_verified"] = now_str
                    if not parsed.get("official_url"):
                        parsed["official_url"] = link
                    if not parsed.get("source"):
                        parsed["source"] = f"TG: @{ch}"
                        
                    active_deals.insert(0, parsed)
                    existing_ids.add(deal_id)
                    new_added_count += 1
                    print(f"  -> 🎉 成功从 Telegram 捕获羊毛: {parsed.get('title')}")
                time.sleep(0.3)
        except Exception as e:
            print(f"抓取 Telegram 频道 @{ch} 失败: {str(e)[:100]}")

    active_deals.sort(key=lambda x: (x.get("created_at") == today_date, x.get("value_score", 0)), reverse=True)
    save_json(ACTIVE_FILE, active_deals)
    save_json(ARCHIVE_FILE, archived_deals[:500])
    print(f"采集完成！本次新增: {new_added_count} 条，总计有效: {len(active_deals)} 条")

if __name__ == "__main__":
    main()
