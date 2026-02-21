#!/usr/bin/env python3
import re
import json
import time
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ================== CONFIG ==================
BASE_URL = "https://hitmaal.com/"
MAX_ITEMS = 30
OUTPUT_JSON = "hitmaal_with_playback.json"
PAGE_TIMEOUT = 30000
REQUEST_TIMEOUT = 15
MAX_RETRIES = 2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

M3U8_REGEX = re.compile(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', re.I)
MPD_REGEX = re.compile(r'https?://[^\s"\'<>]+\.mpd[^\s"\'<>]*', re.I)

# ================== HELPERS ==================
def fetch_page(url, retry=0):
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        if retry < MAX_RETRIES:
            time.sleep(2)
            return fetch_page(url, retry + 1)
        print(f"Failed to fetch {url}: {e}")
        return ""

def extract_listing(html):
    if not html:
        return []
    
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("a.video.lazy-bg, article.video, .video-item")
    out = []
    
    for c in cards:
        title_elem = c.find("h2", class_="vtitle") or c.find("h3") or c.find("h2")
        title = title_elem.get_text(strip=True) if title_elem else ""
        
        if not title:
            continue
            
        href = c.get("href", "").strip()
        if not href:
            continue
            
        if not href.startswith('http'):
            href = urljoin(BASE_URL, href)
        
        out.append({
            "title": title,
            "page_url": href
        })
    
    return out

def scrape_listings():
    page = 1
    items = []
    
    while len(items) < MAX_ITEMS:
        url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
        print(f"Scraping page {page}: {url}")
        
        html = fetch_page(url)
        if not html:
            break
            
        batch = extract_listing(html)
        if not batch:
            print(f"No more items found on page {page}")
            break
            
        for it in batch:
            if len(items) >= MAX_ITEMS:
                break
            if not any(existing['page_url'] == it['page_url'] for existing in items):
                items.append(it)
                
        print(f"Found {len(batch)} items on page {page}")
        page += 1
        time.sleep(1)
    
    return items

# ================== PLAYBACK EXTRACT ==================
def extract_playback(url, browser):
    found_m3u8, found_mpd = set(), set()
    context = None
    page = None
    
    try:
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 720},
            locale="en-US",
        )
        page = context.new_page()

        def on_request(req):
            u = req.url.lower()
            if ".m3u8" in u:
                found_m3u8.add(req.url.split("?")[0])
            if ".mpd" in u or "/dash/" in u or "manifest" in u:
                found_mpd.add(req.url.split("?")[0])

        def on_response(res):
            u = res.url.lower()
            if ".m3u8" in u:
                found_m3u8.add(res.url.split("?")[0])
            if ".mpd" in u or "/dash/" in u or "manifest" in u:
                found_mpd.add(res.url.split("?")[0])

        page.on("request", on_request)
        page.on("response", on_response)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            print(f"  Timeout loading {url}, continuing...")
        
        play_selectors = [
            "video",
            "button[aria-label*='play' i]",
            "button[class*='play']",
            ".play-button",
            ".vjs-big-play-button",
            "button[title*='Play' i]"
        ]
        
        for selector in play_selectors:
            try:
                play_btn = page.locator(selector).first
                if play_btn.is_visible(timeout=2000):
                    play_btn.click()
                    page.wait_for_timeout(3000)
                    break
            except Exception:
                continue

        page.wait_for_timeout(5000)

        html = page.content()
        for m in M3U8_REGEX.findall(html):
            found_m3u8.add(m.split("?")[0])
        for m in MPD_REGEX.findall(html):
            found_mpd.add(m.split("?")[0])

        media = page.evaluate("""() => {
            const urls = new Set();
            document.querySelectorAll('video, source, iframe').forEach(el => {
                if (el.src) urls.add(el.src);
                if (el.currentSrc) urls.add(el.currentSrc);
                if (el.dataset && el.dataset.src) urls.add(el.dataset.src);
            });
            return Array.from(urls);
        }""")
        
        for u in media:
            u_lower = u.lower()
            if ".m3u8" in u_lower:
                found_m3u8.add(u.split("?")[0])
            if ".mpd" in u_lower or "/dash/" in u_lower:
                found_mpd.add(u.split("?")[0])

    except Exception as e:
        print(f"  Error extracting playback: {str(e)[:100]}")
    finally:
        if page:
            page.close()
        if context:
            context.close()

    playback = {}
    if found_m3u8:
        playback["hls"] = sorted(found_m3u8)[:3]
    if found_mpd:
        playback["dash"] = sorted(found_mpd)[:3]
    
    return playback if playback else None

# ================== MAIN ==================
def main():
    print(f"Starting scraper for {BASE_URL}")
    start_time = time.time()
    
    listings = scrape_listings()
    print(f"Found {len(listings)} videos")
    
    if not listings:
        print("No listings found, exiting")
        return
    
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
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        successful = 0
        for i, v in enumerate(listings, 1):
            print(f"\n[{i}/{len(listings)}] Processing: {v['title'][:50]}...")
            
            try:
                playback = extract_playback(v["page_url"], browser)
                results["videos"].append({
                    "title": v["title"],
                    "page_url": v["page_url"],
                    "playback": playback
                })
                if playback:
                    successful += 1
                    print(f"  ✓ Found playback: {list(playback.keys())}")
                else:
                    print(f"  ✗ No playback found")
            except Exception as e:
                print(f"  ✗ Error: {str(e)[:100]}")
                results["videos"].append({
                    "title": v["title"],
                    "page_url": v["page_url"],
                    "playback": None,
                    "error": str(e)[:200]
                })
            
            elapsed = time.time() - start_time
            avg_time = elapsed / i
            remaining = avg_time * (len(listings) - i)
            print(f"  Progress: {i}/{len(listings)} | Found: {successful} | "
                  f"Elapsed: {elapsed:.0f}s | Remaining: {remaining:.0f}s")

        browser.close()

    results["stats"] = {
        "successful": successful,
        "failed": len(listings) - successful,
        "execution_time_seconds": round(time.time() - start_time, 2)
    }
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Done! Saved to {OUTPUT_JSON}")
    print(f"   Successful: {successful}/{len(listings)}")
    print(f"   Time taken: {results['stats']['execution_time_seconds']}s")

if __name__ == "__main__":
    main()
