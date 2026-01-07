#!/usr/bin/env python3
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
def fetch_page(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text

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
def extract_thumbnail(card):
    style = card.get("style", "")
    if not style:
        return ""

    style = " ".join(style.split())
    m = re.search(r'url\((["\']?)(.*?)\1\)', style, re.IGNORECASE)
    return m.group(2).strip() if m else ""

# --------------------------
def extract_episodes(html):
    soup = BeautifulSoup(html, "html.parser")
    episodes = []

    cards = soup.select("a.video")
    print(f"🔍 Found {len(cards)} videos")

    for card in cards:
        episodes.append({
            "title": card.get("title", "").strip(),
            "duration": card.find("span", class_="time").get_text(strip=True)
                        if card.find("span", class_="time") else "",
            "upload_time": card.find("span", class_="ago").get_text(strip=True)
                        if card.find("span", class_="ago") else "",
            "link": urljoin(BASE_URL, card.get("href", "")),
            "thumbnail": extract_thumbnail(card)
        })

    return episodes

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

        items = extract_episodes(html)
        if not items:
            break

        all_items.extend(items)
        page += 1

    return all_items

# --------------------------
def save_data(items):
    data = load_existing()
    seen = {e["link"] for e in data["episodes"]}

    added = 0
    for ep in items:
        if ep["link"] not in seen:
            data["episodes"].append(ep)
            added += 1

    data["total"] = len(data["episodes"])
    data["last_updated"] = datetime.now().isoformat()

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"💾 Added {added} new items")

# --------------------------
def main():
    print("🎬 HITMaal Scraper Started")
    items = scrape_all_pages()
    save_data(items)
    print("✅ DONE")

if __name__ == "__main__":
    main()
