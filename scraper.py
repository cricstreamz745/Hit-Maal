#!/usr/bin/env python3
"""
HITMail Video Scraper
Scrapes episode information from HITMail website
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import datetime
from urllib.parse import urljoin

# Configuration
BASE_URL = "https://hitmaal.com/"
OUTPUT_FOLDER = "hitmaal_data"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Headers to mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

def get_page_content(url):
    """Fetch webpage content"""
    try:
        print(f"📡 Fetching: {url}")
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        # Check if we got valid HTML
        if 'text/html' not in response.headers.get('content-type', '').lower():
            print("⚠️  Warning: Response is not HTML")
            
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching page: {e}")
        return None

def extract_episodes_from_html(html):
    """Extract episode information from HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    episodes = []
    
    print("\n🔍 Searching for episodes...")
    
    # Method 1: Look for patterns based on screenshot
    # Pattern: Duration (26:00) + Time ago (1 Hr Ago) + Title
    time_pattern = re.compile(r'(\d{1,2}:\d{2})')
    ago_pattern = re.compile(r'(\d+\s*(Hr|Hour|Min|Minute|Day|Week)\s*Ago)', re.IGNORECASE)
    
    # Find all text nodes that match our patterns
    all_text = soup.find_all(string=True)
    
    for text_node in all_text:
        text = text_node.strip()
        if len(text) < 5:  # Skip very short text
            continue
            
        # Check if this looks like episode information
        has_duration = time_pattern.search(text)
        has_ago = ago_pattern.search(text)
        has_episode = 'Episode' in text
        
        if has_duration or has_ago or has_episode:
            # Find the parent container
            parent = text_node.parent
            for _ in range(3):  # Go up a few levels
                if parent and parent.name in ['div', 'article', 'li', 'section', 'a']:
                    # Extract structured data
                    episode_data = extract_episode_data(parent)
                    if episode_data and episode_data not in episodes:
                        episodes.append(episode_data)
                    break
                if parent:
                    parent = parent.parent
    
    # Method 2: Look for video cards/containers
    if len(episodes) < 3:
        print("Trying alternative method...")
        
        # Common class names for video cards
        card_selectors = [
            '.video-card', '.episode-card', '.card', 
            '.item', '.post', '.content-item'
        ]
        
        for selector in card_selectors:
            cards = soup.select(selector)
            if cards:
                print(f"Found {len(cards)} elements with selector: {selector}")
                for card in cards[:10]:  # Limit to first 10
                    episode_data = extract_episode_data(card)
                    if episode_data and episode_data not in episodes:
                        episodes.append(episode_data)
    
    # Remove duplicates based on title
    unique_episodes = []
    seen_titles = set()
    
    for ep in episodes:
        if ep['title'] and ep['title'] not in seen_titles:
            unique_episodes.append(ep)
            seen_titles.add(ep['title'])
    
    return unique_episodes

def extract_episode_data(element):
    """Extract data from an episode element"""
    try:
        # Get text content
        full_text = element.get_text(separator=' ', strip=True)
        if len(full_text) < 20:  # Too short to be an episode
            return None
        
        # Extract duration (pattern: 26:00)
        duration_match = re.search(r'(\d{1,2}:\d{2})', full_text)
        duration = duration_match.group(1) if duration_match else ""
        
        # Extract upload time (pattern: 1 Hr Ago)
        ago_match = re.search(r'(\d+\s*(Hr|Hour|Min|Minute|Day|Week)\s*Ago)', full_text, re.IGNORECASE)
        upload_time = ago_match.group(1) if ago_match else ""
        
        # Extract title (look for text with "Episode")
        title = ""
        title_elements = element.find_all(['h2', 'h3', 'h4', 'span', 'div', 'a'])
        for elem in title_elements:
            text = elem.get_text(strip=True)
            if text and ('Episode' in text or len(text) > 10):
                title = text
                break
        
        # If no title found, use the longest text chunk
        if not title:
            text_chunks = [chunk.strip() for chunk in full_text.split() if len(chunk) > 5]
            if text_chunks:
                title = ' '.join(text_chunks[:3])  # First few meaningful words
        
        # Get link
        link = ""
        if element.name == 'a' and element.get('href'):
            link = element.get('href')
        else:
            link_elem = element.find('a', href=True)
            if link_elem:
                link = link_elem.get('href')
        
        # Get thumbnail
        thumbnail = ""
        img_elem = element.find('img')
        if img_elem:
            thumbnail = img_elem.get('src') or img_elem.get('data-src') or ""
        
        # Get clean title without duration/time
        clean_title = title
        if duration and duration in clean_title:
            clean_title = clean_title.replace(duration, '').strip()
        if upload_time and upload_time in clean_title:
            clean_title = clean_title.replace(upload_time, '').strip()
        
        return {
            'title': clean_title or "Untitled Episode",
            'duration': duration,
            'upload_time': upload_time,
            'link': link,
            'thumbnail': thumbnail,
            'raw_text': full_text[:200]  # Store first 200 chars for debugging
        }
    except Exception as e:
        print(f"Error extracting episode data: {e}")
        return None

def extract_navigation(soup):
    """Extract navigation menu items"""
    nav_items = []
    
    # Look for navigation elements
    nav_selectors = ['nav', '.navbar', '.menu', '.navigation', 'header']
    
    for selector in nav_selectors:
        nav_elem = soup.find(selector)
        if nav_elem:
            links = nav_elem.find_all('a', href=True)
            for link in links:
                text = link.get_text(strip=True)
                if text and len(text) > 1:
                    nav_items.append({
                        'text': text,
                        'url': link.get('href'),
                        'title': link.get('title', '')
                    })
    
    return nav_items[:10]  # Return first 10 items

def save_results(episodes, nav_items, metadata):
    """Save scraping results to files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save as JSON
    json_data = {
        'metadata': metadata,
        'episodes': episodes,
        'navigation': nav_items,
        'scraped_at': datetime.now().isoformat(),
        'total_episodes': len(episodes)
    }
    
    json_file = os.path.join(OUTPUT_FOLDER, f"hitmaal_{timestamp}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON data saved: {json_file}")
    
    # Save as readable text
    txt_file = os.path.join(OUTPUT_FOLDER, f"hitmaal_{timestamp}.txt")
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("HITMAIL EPISODE SCRAPER RESULTS\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"Scraped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total episodes found: {len(episodes)}\n\n")
        
        f.write("NAVIGATION:\n")
        f.write("-" * 40 + "\n")
        for item in nav_items:
            f.write(f"• {item['text']}\n")
        
        f.write("\n\nEPISODES:\n")
        f.write("=" * 60 + "\n")
        
        for i, episode in enumerate(episodes, 1):
            f.write(f"\n{i}. {episode['title']}\n")
            if episode['duration']:
                f.write(f"   Duration: {episode['duration']}\n")
            if episode['upload_time']:
                f.write(f"   Uploaded: {episode['upload_time']}\n")
            if episode['link']:
                f.write(f"   Link: {episode['link']}\n")
            if episode['thumbnail']:
                f.write(f"   Thumbnail: {episode['thumbnail']}\n")
    
    print(f"✅ Text report saved: {txt_file}")
    
    return json_file, txt_file

def main():
    """Main function"""
    print("🎬 HITMail Video Scraper")
    print("=" * 50)
    
    # Get page content
    html = get_page_content(BASE_URL)
    if not html:
        print("❌ Failed to get page content. Exiting...")
        return
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Get page metadata
    page_title = soup.title.string if soup.title else "No title"
    print(f"📄 Page Title: {page_title}")
    
    # Extract episodes
    episodes = extract_episodes_from_html(html)
    
    # Extract navigation
    nav_items = extract_navigation(soup)
    
    # Display results
    print("\n" + "=" * 50)
    print(f"📊 RESULTS SUMMARY")
    print("=" * 50)
    print(f"Total episodes found: {len(episodes)}")
    print(f"Navigation items: {len(nav_items)}")
    
    if episodes:
        print("\n📺 EPISODES FOUND:")
        print("-" * 40)
        for i, episode in enumerate(episodes[:5], 1):  # Show first 5
            print(f"{i}. {episode['title']}")
            if episode['duration']:
                print(f"   ⏱️  {episode['duration']}", end="")
            if episode['upload_time']:
                print(f" | 📅 {episode['upload_time']}")
            print()
        
        if len(episodes) > 5:
            print(f"... and {len(episodes) - 5} more episodes")
    else:
        print("\n⚠️  No episodes found. The site structure might have changed.")
        print("\nDebugging information:")
        print(f"Page size: {len(html)} characters")
        print(f"Contains 'Episode': {'Episode' in html}")
        print(f"Contains 'Hr Ago': {'Hr Ago' in html}")
    
    if nav_items:
        print("\n🗺️  NAVIGATION MENU:")
        print("-" * 40)
        for item in nav_items[:5]:
            print(f"• {item['text']}")
    
    # Save results
    metadata = {
        'url': BASE_URL,
        'title': page_title,
        'scraped_at': datetime.now().isoformat()
    }
    
    json_file, txt_file = save_results(episodes, nav_items, metadata)
    
    print("\n" + "=" * 50)
    print("✅ SCRAPING COMPLETE!")
    print("=" * 50)
    print(f"\nFiles created:")
    print(f"  • {json_file}")
    print(f"  • {txt_file}")
    print(f"\nOutput folder: {OUTPUT_FOLDER}")

if __name__ == "__main__":
    main()
