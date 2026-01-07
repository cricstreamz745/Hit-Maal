#!/usr/bin/env python3
"""
HITMaal Video Scraper
Pagination + Single JSON storage
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
OUTPUT_FOLDER = "hitmaal_data"
JSON_FILE = os.path.join(OUTPUT_FOLDER, "hitmaal_all.json")

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# ==========================
# FETCH PAGE
# ==========================
def fetch_page(url):
    print(f"📡 Fetching: {url}")
    r = requests.get(url, headers=HEADERS, timeout=30)
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
# EXTRACT EPISODES
# ==========================
def extract_episodes(html):
    soup = BeautifulSoup(html, "html.parser")
    episodes = []

    cards = soup.select("a.video")
    print(f"🔍 Found {len(cards)} video cards")

    for card in cards:
        title = card.find("h2", class_="vtitle")
        duration = card.find("span", class_="time")
        ago = card.find("span", class_="ago")

        link = card.get("href", "")
        link = urljoin(BASE_URL, link)

        # thumbnail from inline style
        thumbnail = ""
        style = card.get("style", "")
        match = re.search(r'url\((["\']?)(.*?)\1\)', style)
        if match:
            thumbnail = match.group(2)

        episodes.append({
            "title": title.get_text(strip=True) if title else "Untitled",
            "duration": duration.get_text(strip=True) if duration else "",
            "upload_time": ago.get_text(strip=True) if ago else "",
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
        episodes = extract_episodes(html)

        if not episodes:
            print("🚫 No more pages found. Stopping.")
            break

        all_episodes.extend(episodes)
        page += 1

    return all_episodes

# ==========================
# SAVE (APPEND) JSON
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

    print(f"✅ Added {added} new episodes")
    print(f"📦 Total stored: {data['total']}")
    print(f"💾 JSON file: {JSON_FILE}")

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
