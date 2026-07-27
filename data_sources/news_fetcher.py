"""新闻数据源 - 地缘政治/宏观新闻抓取

从多个 RSS 源抓取新闻，分类后保存到 news_events 表。
"""
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import httpx

from store import save_news_event, get_news_events

logger = logging.getLogger(__name__)

# 缓存：5分钟内不重复抓取 RSS
_news_cache: dict = {"last_fetch": 0, "items": []}
NEWS_CACHE_TTL = 300  # 5分钟

# 新闻源配置
NEWS_SOURCES = [
    {
        "name": "路透社世界新闻",
        "url": "https://feeds.reuters.com/Reuters/worldNews",
        "category": "地缘政治",
        "regions": ["全球"],
        "affected_assets": ["原油", "黄金", "股市"],
    },
    {
        "name": "路透社财经新闻",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "category": "经济政策",
        "regions": ["全球"],
        "affected_assets": ["股市", "债券", "汇率"],
    },
    {
        "name": "CNBC 世界新闻",
        "url": "https://www.cnbc.com/id/100727362/device/rss/rss.html",
        "category": "地缘政治",
        "regions": ["全球"],
        "affected_assets": ["原油", "股市"],
    },
    {
        "name": "BBC 世界新闻",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "category": "地缘政治",
        "regions": ["全球"],
        "affected_assets": ["原油", "黄金"],
    },
]

# 地缘关键词，用于分类和判断重要性
GEOPOLITICAL_KEYWORDS = [
    "war", "conflict", "military", "attack", "strike", "missile",
    "sanction", "tariff", "trade war", "embargo",
    "election", "coup", "protest", "unrest", "crisis",
    "oil", "opec", "energy", "gas", "pipeline",
    "china", "us", "russia", "iran", "israel", "ukraine",
    "nato", "united nations", "summit", "deal", "agreement",
]

ECONOMIC_KEYWORDS = [
    "fed", "interest rate", "inflation", "cpi", "gdp", "unemployment",
    "central bank", "monetary policy", "fiscal policy",
    "recession", "economic growth", "stimulus",
    "earnings", "profit", "revenue",
]


def _parse_rss(xml_content: str, source_name: str) -> list[dict]:
    """解析 RSS XML，返回新闻列表"""
    items = []
    try:
        root = ET.fromstring(xml_content)
        for item in root.iter("item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_date_elem = item.find("pubDate")

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            description = ""
            if desc_elem is not None and desc_elem.text:
                description = re.sub(r"<[^>]+>", "", desc_elem.text).strip()

            pub_date = datetime.now(timezone.utc)
            if pub_date_elem is not None and pub_date_elem.text:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date = parsedate_to_datetime(pub_date_elem.text)
                except Exception:
                    pass

            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "pub_date": pub_date,
                    "source": source_name,
                })
    except Exception as e:
        logger.warning(f"解析 RSS 失败 ({source_name}): {e}")
    return items


def _classify_news(title: str, description: str) -> dict:
    """根据标题和描述分类新闻，判断重要性"""
    text = (title + " " + description).lower()

    category = "其他"
    importance = "low"
    regions = []
    affected_assets = []

    geo_hits = sum(1 for kw in GEOPOLITICAL_KEYWORDS if kw in text)
    eco_hits = sum(1 for kw in ECONOMIC_KEYWORDS if kw in text)

    if geo_hits >= 2:
        category = "地缘冲突"
        importance = "high" if geo_hits >= 4 else "medium"
        affected_assets = ["原油", "黄金", "军工"]
    elif eco_hits >= 2:
        category = "经济政策"
        importance = "high" if eco_hits >= 4 else "medium"
        affected_assets = ["股市", "债券", "汇率"]
    elif geo_hits >= 1:
        category = "地缘政治"
        importance = "medium"
        affected_assets = ["原油", "黄金"]
    elif eco_hits >= 1:
        category = "经济政策"
        importance = "low"
        affected_assets = ["股市"]

    if "china" in text or "中国" in text:
        regions.append("中国")
    if "us" in text or "america" in text or "美国" in text:
        regions.append("美国")
    if "russia" in text or "俄罗斯" in text:
        regions.append("俄罗斯")
    if "europe" in text or "eu" in text or "欧洲" in text:
        regions.append("欧洲")
    if "middle east" in text or "israel" in text or "iran" in text or "中东" in text:
        regions.append("中东")
    if "asia" in text or "亚洲" in text:
        regions.append("亚洲")

    if not regions:
        regions.append("全球")

    return {
        "category": category,
        "importance": importance,
        "regions": regions,
        "affected_assets": affected_assets,
    }


def fetch_geopolitical_news(limit: int = 20) -> list[dict]:
    """抓取地缘政治新闻（并发抓取多个RSS源）

    Returns:
        按时间倒序排列的新闻列表
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    all_news = []
    seen_titles = set()

    def _fetch_one(src):
        items = []
        try:
            with httpx.Client(timeout=5, follow_redirects=True) as client:
                resp = client.get(src["url"])
                if resp.status_code != 200:
                    logger.warning(f"获取新闻源失败 {src['name']}: HTTP {resp.status_code}")
                    return items
                items = _parse_rss(resp.text, src["name"])
        except Exception as e:
            logger.warning(f"抓取新闻源失败 {src['name']}: {e}")
        return items

    # 并发抓取所有RSS源
    with ThreadPoolExecutor(max_workers=min(4, len(NEWS_SOURCES))) as executor:
        future_map = {executor.submit(_fetch_one, src): src for src in NEWS_SOURCES}
        for future in as_completed(future_map):
            items = future.result()
            for item in items:
                if item["title"] in seen_titles:
                    continue
                seen_titles.add(item["title"])
                info = _classify_news(item["title"], item["description"])
                all_news.append({
                    **item,
                    "category": info["category"],
                    "importance": info["importance"],
                    "regions": info["regions"],
                    "affected_assets": info["affected_assets"],
                })

    all_news.sort(key=lambda x: x["pub_date"], reverse=True)
    return all_news[:limit]


def sync_news_to_db(limit: int = 50) -> int:
    """同步新闻到数据库，返回新增数量

    5分钟缓存：避免频繁抓取 RSS 导致超时
    """
    now = time.time()
    if now - _news_cache["last_fetch"] < NEWS_CACHE_TTL and _news_cache["items"]:
        logger.debug("新闻缓存命中，跳过 RSS 抓取")
        return 0

    try:
        news_items = fetch_geopolitical_news(limit)
        _news_cache["items"] = news_items
        _news_cache["last_fetch"] = now
    except Exception as e:
        logger.warning(f"RSS 抓取失败，使用缓存: {e}")
        return 0

    existing = get_news_events(limit=200)
    existing_titles = {n["title"] for n in existing}

    added = 0
    for item in news_items:
        if item["title"] in existing_titles:
            continue
        try:
            pub_str = item["pub_date"].strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pub_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        save_news_event(
            category=item["category"],
            title=item["title"],
            source=item["source"],
            url=item["link"],
            regions=",".join(item["regions"]),
            affected_assets=",".join(item["affected_assets"]),
            published_at=pub_str,
        )
        added += 1

    logger.info(f"新闻同步完成，新增 {added} 条")
    return added


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    news = fetch_geopolitical_news(10)
    for n in news:
        print(f"[{n['category']}] {n['title']} - {n['source']}")
