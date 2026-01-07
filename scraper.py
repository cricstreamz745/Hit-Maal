#!/usr/bin/env python3
"""
HITMaal Scraper (FINAL – REAL FIX)
- Pagination: /page/{n}/
- Thumbnail fetched from episode page (og:image)
- Single JSON file: hitmall.json
- Deduplication
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime
from urllib.parse import urljoin

BASE_URL = "https://hitmaal.com/"
JSON_FILE = "hitmall.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}

# --------------------------
# Fetch page safely
# --------------------------
def fetch_page(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text

# --------------------------
# Load existing JSON
# --------------------------
def load_existing():
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

# --------------------------
# Fetch thumbnail from episode page
# --------------------------
def fetch_thumbnail_from_post(url):
    try:
        html = fetch_page(url)
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        og = soup.find("meta", property="og:image")
        return og["content"].strip() if og else ""
    except Exception:
        return ""

# --------------------------
# Extract listing page videos
# --------------------------
def extract_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("a.video")
    episodes = []

    for card in cards:
        title = card.get("title", "").strip()
        link = urljoin(BASE_URL, card.get("href", "").strip())

        duration = card.find("span", class_="time")
        ago = card.find("span", class_="ago")

        episodes.append({
            "title": title,
            "duration": duration.get_text(strip=True) if duration else "",
            "upload_time": ago.get_text(strip=True) if ago else "",
            "link": link,
            "thumbnail": ""  # filled later
        })

    return episodes

# --------------------------
# Pagination scraper
# --------------------------
def scrape_all_pages():
    page = 1
    all_items = []

    while True:
        url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
        print(f"📡 Fetching {url}")

        html = fetch_page(url)
        if not html:
            break

        items = extract_listing(html)
        if not items:
            break

        all_items.extend(items)
        print(f"✅ Page {page} → {len(items)} videos")

        page += 1

    return all_items

# --------------------------
# Save merged JSON
# --------------------------
def save_data(new_items):
    data = load_existing()
    existing_links = {e["link"] for e in data["episodes"]}

    added = 0
    for ep in new_items:
        if ep["link"] not in existing_links:
            print(f"🖼 Fetching thumbnail → {ep['title']}")
            ep["thumbnail"] = fetch_thumbnail_from_post(ep["link"])
            data["episodes"].append(ep)
            added += 1

    data["total"] = len(data["episodes"])
    data["last_updated"] = datetime.now().isoformat()

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"💾 Added {added} new videos")

# --------------------------
# MAIN
# --------------------------
def main():
    print("🎬 HITMaal Scraper Started")
    items = scrape_all_pages()
    print(f"📊 Found {len(items)} total items")
    save_data(items)
    print("✅ DONE")

if __name__ == "__main__":
    main()
