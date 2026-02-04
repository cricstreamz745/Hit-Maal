#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from urllib.parse import urljoin

BASE_URL = "https://hitmaal.com/"
JSON_FILE = "hitmall.json"
MAX_ITEMS = 500

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}

# -------------------------------------------------
def fetch_page(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text

# -------------------------------------------------
def extract_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("a.video")
    episodes = []

    for card in cards:
        episodes.append({
            "title": card.get("title", "").strip(),
            "duration": card.find("span", class_="time").get_text(strip=True)
                        if card.find("span", class_="time") else "",
            "upload_time": card.find("span", class_="ago").get_text(strip=True)
                        if card.find("span", class_="ago") else "",
            "link": urljoin(BASE_URL, card.get("href", "")),
        })

    return episodes

# -------------------------------------------------
def scrape_all_pages():
    page = 1
    items = []

    while len(items) < MAX_ITEMS:
        url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
        print(f"📡 Fetching {url}")

        html = fetch_page(url)
        if not html:
            break

        batch = extract_listing(html)
        if not batch:
            break

        for ep in batch:
            if len(items) >= MAX_ITEMS:
                break
            items.append(ep)

        page += 1

    print(f"🛑 Collected {len(items)} items")
    return items

# -------------------------------------------------
def save_data(items):
    data = {
        "source": BASE_URL,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "total": len(items),
        "episodes": items
    }

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("💾 JSON fully replaced (NO thumbnails)")

# -------------------------------------------------
def main():
    print("🎬 HITMaal Scraper Started")
    items = scrape_all_pages()
    save_data(items)
    print("✅ DONE in seconds")

if __name__ == "__main__":
    main()
