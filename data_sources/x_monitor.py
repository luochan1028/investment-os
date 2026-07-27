"""X/Twitter 账号监控模块 — 轮询 + 分类 + 去重 + 推送

自包含模块，不依赖 x-monitor-push 项目。

数据源策略（零 token）：
1. Truth Social RSS (trumpstruth.org) — 川普专用
2. Twitter Syndication API — 其他账号
3. Nitter 镜像 — 备选

分级策略：关键词三级体系（high/medium/low）
"""
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("investment-os.x_monitor")


# ==================== 数据结构 ====================

@dataclass
class TweetItem:
    username: str
    title: str
    link: str
    published: str
    summary: str
    original_id: str = ""


@dataclass
class AnalysisResult:
    impact_level: str   # high / medium / low
    direction: str       # positive / negative / neutral
    category: str = ""
    sectors: list = field(default_factory=list)
    analysis: str = ""


# ==================== 轮询：Truth Social RSS ====================

TRUTH_RSS_URL = "https://www.trumpstruth.org/feed"
TRUTH_USERS = {"realdonaldtrump", "trump", "donaldtrump"}


def _clean_html(text: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p[^>]*>', '', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def _parse_rss_feed(feed_xml: str, max_items: int = 10) -> list[dict]:
    """用标准库解析 RSS feed，返回 entry 列表"""
    try:
        root = ET.fromstring(feed_xml)
    except ET.ParseError:
        logger.warning("RSS XML 解析失败")
        return []

    # RSS 2.0: channel/item
    items = root.findall(".//item")
    entries = []
    for item in items[:max_items]:
        entry = {}
        for child in item:
            tag = child.tag.split("}")[-1]  # 去掉命名空间前缀
            entry[tag] = child.text or ""
            # 处理属性（如 truth:originalid）
            for attr_key, attr_val in child.attrib.items():
                if "originalid" in attr_key.lower():
                    entry["original_id"] = attr_val
        entries.append(entry)
    return entries


def fetch_truth_posts(username: str, max_items: int = 10) -> list[TweetItem]:
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(TRUTH_RSS_URL)
            resp.raise_for_status()
            feed_content = resp.text
    except Exception as e:
        logger.warning(f"Truth Social RSS 拉取失败: {e}")
        return []

    entries = _parse_rss_feed(feed_content, max_items)
    if not entries:
        return []

    posts = []
    for entry in entries:
        title = entry.get("title", "")
        link = entry.get("link", "")
        published = entry.get("pubDate", entry.get("published", ""))
        summary = _clean_html(entry.get("description", ""))
        original_id = entry.get("original_id", "")
        if title.startswith("[No Title]"):
            title = summary[:200] if summary else title
        posts.append(TweetItem(
            username=username, title=title, link=link,
            published=published, summary=summary, original_id=original_id,
        ))
        if len(posts) >= max_items:
            break
    logger.info(f"Truth Social 拉取到 {len(posts)} 条 @{username}")
    return posts


# ==================== 轮询：Twitter Syndication API ====================

SYNDICATION_BASE_URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name"
_last_syndication_time = 0.0
_SYNDICATION_MIN_INTERVAL = 5.0
_syndication_rate_limited_until = 0.0


def _extract_tweets_from_syndication(data: dict, username: str, max_items: int = 10) -> list[TweetItem]:
    tweets = []

    def _find(obj, depth=0, max_depth=15):
        if depth > max_depth or len(tweets) >= max_items:
            return
        if isinstance(obj, dict):
            if "full_text" in obj and "id_str" in obj:
                full_text = obj.get("full_text", "")
                id_str = obj.get("id_str", "")
                if full_text.startswith("RT @"):
                    return
                screen_name = obj.get("user", {}).get("screen_name", username) if isinstance(obj.get("user"), dict) else username
                tweets.append(TweetItem(
                    username=screen_name, title=full_text[:200],
                    link=f"https://x.com/{screen_name}/status/{id_str}",
                    published=obj.get("created_at", ""), summary=full_text, original_id=id_str,
                ))
                return
            for v in obj.values():
                _find(v, depth + 1, max_depth)
        elif isinstance(obj, list):
            for item in obj:
                _find(item, depth + 1, max_depth)

    _find(data)
    return tweets


def fetch_twitter_syndication(username: str, max_items: int = 10) -> list[TweetItem]:
    global _last_syndication_time, _syndication_rate_limited_until

    now = time.time()
    if now < _syndication_rate_limited_until:
        return []

    elapsed = now - _last_syndication_time
    if elapsed < _SYNDICATION_MIN_INTERVAL:
        time.sleep(_SYNDICATION_MIN_INTERVAL - elapsed)

    url = f"{SYNDICATION_BASE_URL}/{username}"
    try:
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            resp = client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            })
            _last_syndication_time = time.time()
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPStatusError as e:
        _last_syndication_time = time.time()
        if e.response.status_code == 429:
            _syndication_rate_limited_until = time.time() + 180
            logger.warning(f"Syndication 429 限流 @{username}")
        return []
    except Exception as e:
        _last_syndication_time = time.time()
        logger.warning(f"Syndication 连接失败 @{username}: {e}")
        return []

    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not m:
        logger.warning(f"Syndication 未找到推文数据 @{username}")
        return []

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    tweets = _extract_tweets_from_syndication(data, username, max_items)
    logger.info(f"Syndication 拉取到 {len(tweets)} 条 @{username}")
    return tweets


# ==================== 轮询：Nitter 备选 ====================

NITTER_INSTANCES = ["https://nitter.cz", "https://nitter.poast.org", "https://nitter.net"]


def fetch_from_nitter(username: str, max_items: int = 10) -> list[TweetItem]:
    for base_url in NITTER_INSTANCES:
        url = f"{base_url}/{username}"
        try:
            with httpx.Client(timeout=8, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                html = resp.text
        except Exception:
            continue

        if not html or len(html) < 500:
            continue

        items = re.findall(
            r'<div class="timeline-item[^"]*">(.*?)(?=<div class="timeline-item|<div class="timeline-footer|$)',
            html, re.DOTALL,
        )
        tweets = []
        for item in items[:max_items]:
            text = ""
            for pattern in [r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>', r'<p class="tweet-content[^"]*"[^>]*>(.*?)</p>']:
                m = re.search(pattern, item, re.DOTALL)
                if m:
                    text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                    break
            link_match = re.search(r'href="(/[^/]+/status/(\d+))"', item)
            if text and link_match:
                tweets.append(TweetItem(
                    username=username, title=text[:200],
                    link=f"https://x.com/{username}/status/{link_match.group(2)}",
                    published="", summary=text, original_id=link_match.group(2),
                ))
        if tweets:
            logger.info(f"Nitter 拉取到 {len(tweets)} 条 @{username} ({base_url})")
            return tweets

    return []


# ==================== 统一拉取入口 ====================

def fetch_user_tweets(username: str, max_items: int = 10) -> list[TweetItem]:
    """拉取单个用户推文（四级降级）"""
    if username.lower() in TRUTH_USERS:
        return fetch_truth_posts(username, max_items)

    posts = fetch_twitter_syndication(username, max_items)
    if not posts:
        posts = fetch_from_nitter(username, max_items)
    return posts


# ==================== 关键词分级 ====================

HIGH_KEYWORDS = {
    "关税": ["tariff", "trade war", "duties", "import tax", "trade barrier", "trade deal"],
    "战争": ["war", "military", "invasion", "attack", "troops", "nuclear", "missile", "strike"],
    "选举": ["election", "vote", "ballot", "campaign", "senate", "congress", "presidential"],
    "重大政策": ["sanction", "embargo", "executive order", "national emergency", "crackdown", "ban"],
}
MEDIUM_KEYWORDS = {
    "股市": ["stock", "market", "s&p", "nasdaq", "dow", "rally", "crash", "selloff"],
    "币圈": ["crypto", "bitcoin", "btc", "ethereum", "eth", "blockchain", "token", "defi"],
    "中美关系": ["china", "chinese", "beijing", "taiwan", "semiconductor", "chip", "huawei", "tiktok"],
    "经济": ["fed", "interest rate", "dollar", "inflation", "recession", "gdp", "cpi", "fomc"],
    "科技": ["spacex", "starlink", "ai", "artificial intelligence", "tesla", "neuralink", "ipo"],
}
POSITIVE_KW = ["deal", "agreement", "growth", "boost", "cut", "reduce", "recovery", "success", "win", "approval"]
NEGATIVE_KW = ["war", "ban", "restrict", "sanction", "threat", "crisis", "crash", "collapse", "attack", "warning"]


def classify_tweet(tweet: TweetItem) -> AnalysisResult:
    """关键词三级分类"""
    text = f"{tweet.title} {tweet.summary}".lower()

    high_matches = {}
    for cat, keywords in HIGH_KEYWORDS.items():
        found = [k for k in keywords if k in text]
        if found:
            high_matches[cat] = found

    medium_matches = {}
    for cat, keywords in MEDIUM_KEYWORDS.items():
        found = [k for k in keywords if k in text]
        if found:
            medium_matches[cat] = found

    found_pos = [k for k in POSITIVE_KW if k in text]
    found_neg = [k for k in NEGATIVE_KW if k in text]
    if found_pos and not found_neg:
        direction = "positive"
    elif found_neg and not found_pos:
        direction = "negative"
    else:
        direction = "neutral"

    if high_matches:
        impact_level = "high"
        category = "、".join(high_matches.keys())
    elif medium_matches:
        impact_level = "medium"
        category = "、".join(medium_matches.keys())
    else:
        impact_level = "low"
        category = ""

    analysis_parts = []
    level_text = {"high": "🔴 重大影响", "medium": "🟡 有影响", "low": "⚪ 无直接影响"}
    analysis_parts.append(level_text.get(impact_level, "⚪ 未知"))
    if category:
        analysis_parts.append(f"分类: {category}")
    dir_text = {"positive": "📈 偏利好", "negative": "📉 偏利空", "neutral": "↔️ 中性"}
    analysis_parts.append(f"方向: {dir_text.get(direction, '↔️ 中性')}")

    return AnalysisResult(
        impact_level=impact_level, direction=direction,
        category=category, analysis="\n".join(analysis_parts),
    )


# ==================== 用户名映射 ====================

USERNAME_MAP = {
    "realdonaldtrump": "唐纳德·特朗普",
    "elonmusk": "埃隆·马斯克",
    "cathiedwood": "Cathie Wood",
    "saylor": "Michael Saylor",
    "vitalikbuterin": "Vitalik Buterin",
    "cz_binance": "赵长鹏 CZ",
    "peternavarro45": "Peter Navarro",
    "howardlutnick": "Howard Lutnick",
    "brian_armstrong": "Brian Armstrong",
    "cryptohayes": "Arthur Hayes",
    "balajis": "Balaji Srinivasan",
    "100trillionusd": "PlanB",
    "apompliano": "Anthony Pompliano",
}


def get_display_name(username: str) -> str:
    return USERNAME_MAP.get(username.lower(), username)


# ==================== 一轮完整轮询 ====================

def run_poll_once(accounts: list[str], max_items: int = 5) -> dict:
    """对指定账号列表执行一轮拉取 → 分类 → 存储 → 推送

    Returns:
        {total_fetched, new_saved, pushed, errors}
    """
    from store import save_tweet, mark_tweet_pushed, get_recent_tweets
    from shared.pusher import push_alert, PushLevel

    total_fetched = 0
    new_saved = 0
    pushed = 0
    errors = []

    for username in accounts:
        username = username.strip().lstrip("@")
        if not username:
            continue
        try:
            tweets = fetch_user_tweets(username, max_items)
            total_fetched += len(tweets)

            for tw in tweets:
                result = classify_tweet(tw)
                display = get_display_name(username)

                is_new = save_tweet(
                    username=username,
                    title=tw.title,
                    link=tw.link,
                    published=tw.published,
                    impact_level=result.impact_level,
                    category=result.category,
                    pushed=0,
                    summary=tw.summary[:500] if tw.summary else "",
                    tweet_id=tw.original_id,
                )
                if is_new:
                    new_saved += 1

                    # 高级别新推文自动推送微信
                    if result.impact_level == "high":
                        content = f"👤 @{username} ({display})\n\n{tw.title}\n\n{result.analysis}\n\n🔗 {tw.link}"
                        ok = push_alert(
                            level=PushLevel.HIGH,
                            title=f"🔴 {display} 发布重要消息",
                            content=content,
                            symbol=username,
                            alert_type="sentiment_high",
                        )
                        if ok:
                            pushed += 1
                            # 标记已推送
                            recent = get_recent_tweets(1)
                            if recent and recent[0]["link"] == tw.link:
                                mark_tweet_pushed(recent[0]["id"])

        except Exception as e:
            logger.error(f"轮询 @{username} 失败: {e}")
            errors.append(f"@{username}: {e}")

    logger.info(f"轮询完成: 拉取 {total_fetched} 条, 新增 {new_saved} 条, 推送 {pushed} 条")
    return {
        "total_fetched": total_fetched,
        "new_saved": new_saved,
        "pushed": pushed,
        "errors": errors,
    }
