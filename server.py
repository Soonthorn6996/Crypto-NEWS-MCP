"""
Crypto News & Market MCP Server
================================
ใช้แหล่งข้อมูล "ฟรี" ทั้งหมด:
  - CoinGecko        : ราคา / market data / trending   (ไม่ต้องใช้ key)
  - Alternative.me   : Fear & Greed Index               (ไม่ต้องใช้ key)
  - RSS News Feeds   : CoinDesk / Cointelegraph / Decrypt / Bitcoin Magazine (ไม่ต้องใช้ key)
  - CryptoPanic      : news aggregator                  (optional - ใส่ token เพื่อใช้)

Transport: Streamable HTTP  -> deploy online ได้ (เช่น Railway)
Endpoint  : http://<host>:<port>/mcp
"""

import os
import time

import httpx
import feedparser
from mcp.server.fastmcp import FastMCP

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
FEAR_GREED_URL = "https://api.alternative.me/fng/"
CRYPTOPANIC_BASE = "https://cryptopanic.com/api/v1/posts/"

CRYPTOPANIC_TOKEN = os.environ.get("CRYPTOPANIC_TOKEN", "").strip()
COINGECKO_DEMO_KEY = os.environ.get("COINGECKO_DEMO_KEY", "").strip()

RSS_FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "decrypt": "https://decrypt.co/feed",
    "bitcoinmagazine": "https://bitcoinmagazine.com/.rss/full/",
}

USER_AGENT = "crypto-news-mcp/1.0 (+https://github.com)"
HTTP_TIMEOUT = 25.0

mcp = FastMCP(
    "crypto-news",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _get(url, params=None, headers=None, as_json=True):
    h = {"User-Agent": USER_AGENT}
    if as_json:
        h["Accept"] = "application/json"
    if headers:
        h.update(headers)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        r = await client.get(url, params=params, headers=h)
        r.raise_for_status()
        return r.json() if as_json else r.text


def _cg_headers():
    return {"x-cg-demo-api-key": COINGECKO_DEMO_KEY} if COINGECKO_DEMO_KEY else {}


def _fmt(n, decimals=2):
    """ตัวเลขทั่วไป + คอมมาคั่นหลักพัน"""
    if n is None:
        return "N/A"
    try:
        if abs(n) < 1 and n != 0:
            s = f"{n:,.8f}".rstrip("0").rstrip(".")
            return s
        return f"{n:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(n)


def _fmt_pct(n):
    if n is None:
        return "N/A"
    try:
        return f"{n:+.2f}%"
    except (TypeError, ValueError):
        return str(n)


def _fmt_big(n, currency="usd"):
    """market cap / volume แบบย่อ T/B/M พร้อม label สกุลเงินที่ถูกต้อง"""
    if n is None:
        return "N/A"
    try:
        a = abs(n)
        if a >= 1e12:
            v, suf = n / 1e12, "T"
        elif a >= 1e9:
            v, suf = n / 1e9, "B"
        elif a >= 1e6:
            v, suf = n / 1e6, "M"
        else:
            v, suf = n, ""
        cur = currency.upper()
        if cur == "USD":
            return f"${v:,.2f}{suf}"
        return f"{v:,.2f}{suf} {cur}"
    except (TypeError, ValueError):
        return str(n)


DISCLAIMER = (
    "\n\n_ข้อมูลนี้รวบรวมจากแหล่งสาธารณะเพื่อการศึกษาเท่านั้น "
    "ไม่ใช่คำชี้ชวนในการลงทุน ผู้ลงทุนควรศึกษาข้อมูลเพิ่มเติมก่อนตัดสินใจ_"
)


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@mcp.tool()
async def get_crypto_price(coin_ids: str, vs_currency: str = "usd") -> str:
    """ดึงราคาล่าสุดของเหรียญ crypto จาก CoinGecko (ฟรี ไม่ต้องใช้ key)

    Args:
        coin_ids: CoinGecko id คั่นด้วย comma เช่น "bitcoin,ethereum,solana"
                  (ถ้าไม่แน่ใจ id ให้ใช้ tool search_coin ก่อน)
        vs_currency: สกุลเงินอ้างอิง เช่น "usd", "thb", "btc"
    """
    try:
        params = {
            "ids": coin_ids,
            "vs_currencies": vs_currency,
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_24hr_change": "true",
            "include_last_updated_at": "true",
        }
        data = await _get(f"{COINGECKO_BASE}/simple/price", params=params, headers=_cg_headers())
        if not data:
            return f"ไม่พบข้อมูลสำหรับ '{coin_ids}' — ลองตรวจสอบ id ด้วย search_coin"

        cur = vs_currency.lower()
        lines = [f"💰 ราคา Crypto (อ้างอิง {vs_currency.upper()})\n"]
        for coin, v in data.items():
            price = v.get(cur)
            mcap = v.get(f"{cur}_market_cap")
            vol = v.get(f"{cur}_24h_vol")
            chg = v.get(f"{cur}_24h_change")
            arrow = "🟢" if (chg or 0) >= 0 else "🔴"
            lines.append(
                f"{arrow} {coin.upper()}\n"
                f"   ราคา      : {_fmt(price)} {vs_currency.upper()}\n"
                f"   24h       : {_fmt_pct(chg)}\n"
                f"   Market Cap: {_fmt_big(mcap, vs_currency)}\n"
                f"   Vol 24h   : {_fmt_big(vol, vs_currency)}\n"
            )
        return "\n".join(lines) + DISCLAIMER
    except httpx.HTTPStatusError as e:
        return f"⚠️ CoinGecko error {e.response.status_code} (อาจติด rate limit ลองใหม่อีกครั้ง)"
    except Exception as e:
        return f"⚠️ เกิดข้อผิดพลาด: {e}"


@mcp.tool()
async def get_market_overview(top: int = 10, vs_currency: str = "usd") -> str:
    """ภาพรวมตลาด crypto: Market cap รวม, BTC dominance และเหรียญ top N ตาม market cap

    Args:
        top: จำนวนเหรียญอันดับต้นที่ต้องการ (default 10, สูงสุด 50)
        vs_currency: สกุลเงินอ้างอิง เช่น "usd", "thb"
    """
    try:
        top = max(1, min(int(top), 50))
        glob = await _get(f"{COINGECKO_BASE}/global", headers=_cg_headers())
        g = glob.get("data", {})
        total_mcap = g.get("total_market_cap", {}).get("usd")
        total_vol = g.get("total_volume", {}).get("usd")
        btc_dom = g.get("market_cap_percentage", {}).get("btc")
        eth_dom = g.get("market_cap_percentage", {}).get("eth")
        mcap_chg = g.get("market_cap_change_percentage_24h_usd")

        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": top,
            "page": 1,
            "price_change_percentage": "24h",
        }
        coins = await _get(f"{COINGECKO_BASE}/coins/markets", params=params, headers=_cg_headers())

        out = [
            "📊 ภาพรวมตลาด Crypto",
            f"   Market Cap รวม : {_fmt_big(total_mcap, 'usd')} ({_fmt_pct(mcap_chg)} 24h)",
            f"   Volume 24h     : {_fmt_big(total_vol, 'usd')}",
            f"   BTC Dominance  : {_fmt(btc_dom)}%",
            f"   ETH Dominance  : {_fmt(eth_dom)}%",
            f"\n🏆 Top {top} เหรียญ (อ้างอิง {vs_currency.upper()}):",
        ]
        for c in coins:
            chg = c.get("price_change_percentage_24h")
            arrow = "🟢" if (chg or 0) >= 0 else "🔴"
            out.append(
                f"{arrow} #{c.get('market_cap_rank')} {c.get('symbol', '').upper()} "
                f"({c.get('name')}) — {_fmt(c.get('current_price'))} {vs_currency.upper()} "
                f"| {_fmt_pct(chg)} | MCap {_fmt_big(c.get('market_cap'), vs_currency)}"
            )
        return "\n".join(out) + DISCLAIMER
    except httpx.HTTPStatusError as e:
        return f"⚠️ CoinGecko error {e.response.status_code} (อาจติด rate limit ลองใหม่อีกครั้ง)"
    except Exception as e:
        return f"⚠️ เกิดข้อผิดพลาด: {e}"


@mcp.tool()
async def get_trending_coins() -> str:
    """เหรียญที่กำลังเป็นกระแส (ถูกค้นหามากสุดใน 24 ชม.) จาก CoinGecko"""
    try:
        data = await _get(f"{COINGECKO_BASE}/search/trending", headers=_cg_headers())
        coins = data.get("coins", [])
        if not coins:
            return "ไม่พบข้อมูล trending ในขณะนี้"
        out = ["🔥 Trending Coins (24h):\n"]
        for i, item in enumerate(coins, 1):
            c = item.get("item", {})
            out.append(
                f"{i}. {c.get('symbol', '').upper()} ({c.get('name')}) "
                f"— rank #{c.get('market_cap_rank', 'N/A')} "
                f"| id: {c.get('id')}"
            )
        return "\n".join(out) + DISCLAIMER
    except Exception as e:
        return f"⚠️ เกิดข้อผิดพลาด: {e}"


@mcp.tool()
async def get_fear_greed_index(days: int = 1) -> str:
    """Crypto Fear & Greed Index จาก Alternative.me (ฟรี ไม่ต้องใช้ key)

    Args:
        days: จำนวนวันย้อนหลัง (1 = วันนี้, สูงสุด 30)
    """
    try:
        days = max(1, min(int(days), 30))
        data = await _get(FEAR_GREED_URL, params={"limit": days})
        rows = data.get("data", [])
        if not rows:
            return "ไม่พบข้อมูล Fear & Greed Index"
        out = ["😨😐🤑 Crypto Fear & Greed Index:\n"]
        for row in rows:
            val = row.get("value")
            cls = row.get("value_classification")
            ts = row.get("timestamp")
            try:
                date = time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
            except (TypeError, ValueError):
                date = "N/A"
            out.append(f"   {date} : {val}/100 — {cls}")
        return "\n".join(out) + DISCLAIMER
    except Exception as e:
        return f"⚠️ เกิดข้อผิดพลาด: {e}"


@mcp.tool()
async def get_crypto_news(limit: int = 10, source: str = "all") -> str:
    """ดึงข่าว crypto ล่าสุดจาก RSS feeds ของสำนักข่าวชั้นนำ (ฟรี ไม่ต้องใช้ key)

    Args:
        limit: จำนวนข่าวสูงสุด (default 10, สูงสุด 30)
        source: "all" หรือเลือกแหล่ง: coindesk / cointelegraph / decrypt / bitcoinmagazine
    """
    try:
        limit = max(1, min(int(limit), 30))
        if source != "all" and source not in RSS_FEEDS:
            return f"source ไม่ถูกต้อง — เลือกได้: all, {', '.join(RSS_FEEDS)}"
        feeds = RSS_FEEDS if source == "all" else {source: RSS_FEEDS[source]}

        entries = []
        for name, url in feeds.items():
            try:
                xml = await _get(url, as_json=False)
                parsed = feedparser.parse(xml)
                for e in parsed.entries:
                    pub = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
                    sort_key = time.mktime(pub) if pub else 0
                    entries.append(
                        {
                            "source": name,
                            "title": getattr(e, "title", "(no title)"),
                            "link": getattr(e, "link", ""),
                            "published": getattr(e, "published", getattr(e, "updated", "N/A")),
                            "sort_key": sort_key,
                        }
                    )
            except Exception:
                continue  # ข้ามแหล่งที่ดึงไม่ได้

        if not entries:
            return "ไม่สามารถดึงข่าวได้ในขณะนี้ ลองใหม่อีกครั้ง"

        entries.sort(key=lambda x: x["sort_key"], reverse=True)
        out = ["📰 ข่าว Crypto ล่าสุด:\n"]
        for i, e in enumerate(entries[:limit], 1):
            out.append(
                f"{i}. [{e['source']}] {e['title']}\n"
                f"   🕒 {e['published']}\n"
                f"   🔗 {e['link']}\n"
            )
        return "\n".join(out)
    except Exception as e:
        return f"⚠️ เกิดข้อผิดพลาด: {e}"


@mcp.tool()
async def search_coin(query: str) -> str:
    """ค้นหา CoinGecko id จากชื่อหรือ symbol (ใช้ก่อน get_crypto_price ถ้าไม่รู้ id)

    Args:
        query: คำค้น เช่น "bitcoin", "pepe", "arb"
    """
    try:
        data = await _get(f"{COINGECKO_BASE}/search", params={"query": query}, headers=_cg_headers())
        coins = data.get("coins", [])[:15]
        if not coins:
            return f"ไม่พบเหรียญที่ตรงกับ '{query}'"
        out = [f"🔍 ผลค้นหา '{query}':\n"]
        for c in coins:
            out.append(
                f"   id: {c.get('id'):<20} | {c.get('symbol', '').upper():<8} "
                f"| {c.get('name')} (rank #{c.get('market_cap_rank', 'N/A')})"
            )
        return "\n".join(out)
    except Exception as e:
        return f"⚠️ เกิดข้อผิดพลาด: {e}"


@mcp.tool()
async def get_cryptopanic_news(currencies: str = "", filter: str = "hot", limit: int = 10) -> str:
    """ข่าว + sentiment จาก CryptoPanic (ต้องตั้งค่า env CRYPTOPANIC_TOKEN ก่อนใช้งาน)

    Args:
        currencies: filter ตามเหรียญ เช่น "BTC,ETH" (เว้นว่าง = ทั้งหมด)
        filter: "hot" | "rising" | "bullish" | "bearish" | "important" | "latest"
        limit: จำนวนข่าวสูงสุด (default 10)
    """
    if not CRYPTOPANIC_TOKEN:
        return (
            "⚠️ ยังไม่ได้ตั้งค่า CRYPTOPANIC_TOKEN\n"
            "สมัครฟรีที่ https://cryptopanic.com/developers/api/ "
            "แล้วตั้งค่า env CRYPTOPANIC_TOKEN\n"
            "ระหว่างนี้ใช้ get_crypto_news (RSS) แทนได้เลย"
        )
    try:
        params = {"auth_token": CRYPTOPANIC_TOKEN, "public": "true", "filter": filter}
        if currencies.strip():
            params["currencies"] = currencies.strip().upper()
        data = await _get(CRYPTOPANIC_BASE, params=params)
        posts = data.get("results", [])[: max(1, min(int(limit), 30))]
        if not posts:
            return "ไม่พบข่าวตามเงื่อนไขที่ระบุ"
        out = [f"📰 CryptoPanic ({filter}):\n"]
        for i, p in enumerate(posts, 1):
            votes = p.get("votes", {})
            out.append(
                f"{i}. {p.get('title')}\n"
                f"   👍 {votes.get('positive', 0)} / 👎 {votes.get('negative', 0)} "
                f"| 🕒 {p.get('published_at', 'N/A')}\n"
                f"   🔗 {p.get('url', '')}\n"
            )
        return "\n".join(out)
    except Exception as e:
        return f"⚠️ เกิดข้อผิดพลาด: {e}"


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
