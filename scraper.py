#!/usr/bin/env python3
"""
HITMaal Video Scraper
Auto-scrapes episodes, thumbnails, duration, upload time
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

# ==========================
# CONFIG
# ==========================
BASE_URL = "https://hitmaal.com/"
OUTPUT_FOLDER = "hitmaal_data"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
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
# EXTRACT EPISODES
# ==========================
def extract_episodes(html):
    soup = BeautifulSoup(html, "html.parser")
    episodes = []

    # HITMaal episode cards
    cards = soup.select("a.video")

    print(f"🔍 Found {len(cards)} video cards")

    for card in cards:
        # Title
        title_elem = card.find("h2", class_="vtitle")
        title = title_elem.get_text(strip=True) if title_elem else "Untitled Episode"

        # Duration
        duration_elem = card.find("span", class_="time")
        duration = duration_elem.get_text(strip=True) if duration_elem else ""

        # Upload time
        ago_elem = card.find("span", class_="ago")
        upload_time = ago_elem.get_text(strip=True) if ago_elem else ""

        # Link
        link = card.get("href", "")

        # Thumbnail from background-image
        thumbnail = ""
        style = card.get("style", "")
        if "background-image" in style:
            match = re.search(r'url\((["\']?)(.*?)\1\)', style)
            if match:
                thumbnail = match.group(2)

        episodes.append({
            "title": title,
            "duration": duration,
            "upload_time": upload_time,
            "link": link,
            "thumbnail": thumbnail
        })

    return episodes

# ==========================
# SAVE FILES
# ==========================
def save_output(episodes):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    data = {
        "source": BASE_URL,
        "scraped_at": datetime.now().isoformat(),
        "total": len(episodes),
        "episodes": episodes
    }

    json_path = f"{OUTPUT_FOLDER}/hitmaal_{ts}.json"
    txt_path = f"{OUTPUT_FOLDER}/hitmaal_{ts}.txt"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("HITMAAL SCRAPE REPORT\n")
        f.write("=" * 50 + "\n\n")
        for i, ep in enumerate(episodes, 1):
            f.write(f"{i}. {ep['title']}\n")
            f.write(f"   Duration : {ep['duration']}\n")
            f.write(f"   Uploaded : {ep['upload_time']}\n")
            f.write(f"   Link     : {ep['link']}\n")
            f.write(f"   Thumb    : {ep['thumbnail']}\n\n")

    print(f"✅ JSON saved: {json_path}")
    print(f"✅ TXT saved : {txt_path}")

# ==========================
# MAIN
# ==========================
def main():
    print("🎬 HITMaal Scraper Started")
    print("=" * 50)

    html = fetch_page(BASE_URL)
    episodes = extract_episodes(html)

    print(f"📊 Total episodes scraped: {len(episodes)}")

    if episodes:
        for ep in episodes[:5]:
            print(f"• {ep['title']} ({ep['duration']})")

    save_output(episodes)

    print("\n✅ DONE")

# ==========================
if __name__ == "__main__":
    main()
