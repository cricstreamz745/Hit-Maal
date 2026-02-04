#!/usr/bin/env python3
import re
import json
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ================== CONFIG ==================
BASE_URL = "https://hitmaal.com/"
MAX_ITEMS = 50              # keep reasonable
OUTPUT_JSON = "hitmaal_with_playback.json"
PAGE_TIMEOUT = 60000

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}

M3U8_REGEX = re.compile(r"https?://[^\s\"'<>]+\.m3u8[^\s\"'<>]*", re.I)
MPD_REGEX  = re.compile(r"https?://[^\s\"'<>]+\.mpd[^\s\"'<>]*", re.I)

# ================== HELPERS ==================
def fetch_page(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text

def extract_thumb(style):
    if not style:
        return ""
    m = re.search(r'url\((?:&quot;|"|\')?(.*?)(?:&quot;|"|\')?\)', style)
    return m.group(1) if m else ""

def extract_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("a.video.lazy-bg")
    out = []
    for c in cards:
        title = c.find("h2", class_="vtitle")
        out.append({
            "title": title.get_text(strip=True) if title else "",
            "page_url": c.get("href", "").strip(),
            "thumbnail": extract_thumb(c.get("style", "")),
        })
    return out

def scrape_listings():
    page = 1
    items = []
    while len(items) < MAX_ITEMS:
        url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
        html = fetch_page(url)
        batch = extract_listing(html)
        if not batch:
            break
        for it in batch:
            if len(items) >= MAX_ITEMS:
                break
            items.append(it)
        page += 1
    return items

# ================== PLAYBACK EXTRACT ==================
def extract_playback(url, browser):
    found_m3u8, found_mpd = set(), set()

    context = browser.new_context(
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"),
        viewport={"width": 1920, "height": 1080},
        locale="en-IN",
    )
    page = context.new_page()

    def on_request(req):
        u = req.url
        if ".m3u8" in u:
            found_m3u8.add(u.split("?")[0])
        if ".mpd" in u or "dash" in u or "manifest" in u:
            found_mpd.add(u.split("?")[0])

    def on_response(res):
        u = res.url
        if ".m3u8" in u:
            found_m3u8.add(u.split("?")[0])
        if ".mpd" in u or "dash" in u or "manifest" in u:
            found_mpd.add(u.split("?")[0])

    page.on("request", on_request)
    page.on("response", on_response)

    try:
        page.goto(url, wait_until="networkidle", timeout=PAGE_TIMEOUT)
    except Exception:
        pass

    page.wait_for_timeout(4000)

    # try clicking play
    for sel in ["video", "button[aria-label*='play' i]", ".play-button"]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1500):
                loc.click()
                page.wait_for_timeout(8000)
                break
        except Exception:
            pass

    # scan DOM
    html = page.content()
    for m in M3U8_REGEX.findall(html):
        found_m3u8.add(m.split("?")[0])
    for m in MPD_REGEX.findall(html):
        found_mpd.add(m.split("?")[0])

    # scan media elements
    media = page.evaluate("""() => {
        const s=new Set();
        document.querySelectorAll('video,source').forEach(e=>{
          if(e.src) s.add(e.src);
          if(e.currentSrc) s.add(e.currentSrc);
        });
        return Array.from(s);
    }""")
    for u in media:
        if ".m3u8" in u:
            found_m3u8.add(u.split("?")[0])
        if ".mpd" in u or "/dash/" in u:
            found_mpd.add(u.split("?")[0])

    context.close()

    playback = {}
    if found_m3u8:
        playback["hls"] = sorted(found_m3u8)
    if found_mpd:
        playback["dash"] = sorted(found_mpd)
    return playback if playback else None

# ================== MAIN ==================
def main():
    listings = scrape_listings()

    results = {
        "source": BASE_URL,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total": len(listings),
        "videos": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        for i, v in enumerate(listings, 1):
            print(f"[{i}/{len(listings)}] {v['title']}")
            playback = extract_playback(v["page_url"], browser)
            results["videos"].append({
                "title": v["title"],
                "page_url": v["page_url"],
                "thumbnail": v["thumbnail"],
                "playback": playback
            })

        browser.close()

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
