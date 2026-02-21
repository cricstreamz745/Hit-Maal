#!/usr/bin/env python3
"""
HITMaal Video Scraper
- Correct thumbnail scraping from inline background-image
- Pagination: /page/{n}/
- Safe stop on 404
- Single JSON output: hitmall.json
- Deduplication by video link
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime
from urllib.parse import urljoin

# ==========================
# CONFIG
# ==========================
BASE_URL = "https://hitmaal.com/"
JSON_FILE = "hitmall.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ==========================
# FETCH PAGE (SAFE)
# ==========================
def fetch_page(url):
    print(f"📡 Fetching: {url}")
    r = requests.get(url, headers=HEADERS, timeout=30)

    if r.status_code == 404:
        return None

    r.raise_for_status()
    return r.text

# ==========================
# LOAD EXISTING JSON
# ==========================
def load_existing_data():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    return {
        "source": BASE_URL,
        "created_at": datetime.now().isoformat(),
        "last_updated": None,
        "total": 0,
        "episodes": []
    }

# ==========================
# EXTRACT EPISODES (FIXED)
# ==========================
def extract_episodes(html):
    soup = BeautifulSoup(html, "html.parser")
    episodes = []

    # HITMaal cards
    cards = soup.select("a.video")
    print(f"🔍 Found {len(cards)} videos")

    for card in cards:
        title = card.get("title", "").strip()

        duration_elem = card.find("span", class_="time")
        ago_elem = card.find("span", class_="ago")

        link = urljoin(BASE_URL, card.get("href", "").strip())

        # ✅ CORRECT THUMBNAIL EXTRACTION
        thumbnail = ""
        style = card.get("style", "")
        if "background-image" in style:
            match = re.search(
                r'background-image:\s*url\(["\']?(.*?)["\']?\)',
                style
            )
            if match:
                thumbnail = match.group(1)

        episodes.append({
            "title": title,
            "duration": duration_elem.get_text(strip=True) if duration_elem else "",
            "upload_time": ago_elem.get_text(strip=True) if ago_elem else "",
            "link": link,
            "thumbnail": thumbnail
        })

    return episodes

# ==========================
# PAGINATION SCRAPER
# ==========================
def scrape_all_pages():
    page = 1
    all_episodes = []

    while True:
        url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"

        html = fetch_page(url)
        if html is None:
            print(f"🛑 Page {page} not found. Stopping.")
            break

        episodes = extract_episodes(html)
        if not episodes:
            print(f"🛑 No videos on page {page}. Stopping.")
            break

        all_episodes.extend(episodes)
        print(f"✅ Page {page} scraped")

        page += 1

    return all_episodes

# ==========================
# SAVE MERGED JSON
# ==========================
def save_merged_data(new_episodes):
    data = load_existing_data()
    existing_links = {ep["link"] for ep in data["episodes"]}

    added = 0
    for ep in new_episodes:
        if ep["link"] not in existing_links:
            data["episodes"].append(ep)
            added += 1

    data["total"] = len(data["episodes"])
    data["last_updated"] = datetime.now().isoformat()

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"💾 Added {added} new videos")
    print(f"📦 Total stored: {data['total']}")

# ==========================
# MAIN
# ==========================
def main():
    print("🎬 HITMaal Scraper Started")
    print("=" * 50)

    episodes = scrape_all_pages()
    print(f"\n📊 Total scraped this run: {len(episodes)}")

    save_merged_data(episodes)

    print("\n✅ DONE")

# ==========================
if __name__ == "__main__":
    main()
