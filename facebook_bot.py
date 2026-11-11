import os
import json
import random
import requests
import xml.etree.ElementTree as ET

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "facebook_used_articles.json"

PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")
PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN")
API_VERSION = "v20.0"

def get_articles():
    try:
        response = requests.get(RSS_URL, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        articles = []
        ns = {'media': 'http://search.yahoo.com/mrss/'}
        
        for item in root.findall("./channel/item"):
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            
            image_url = None
            media_thumb = item.find("media:thumbnail", ns)
            if media_thumb is not None:
                image_url = media_thumb.get("url")
                
            if title and link:
                articles.append({"title": title, "link": link, "image": image_url})
        print("Total articles:", len(articles))
        return articles
    except Exception as e:
        print("RSS error:", e)
        return []

def load_history():
    if not os.path.exists(HISTORY_FILE): 
        return []
    try:
        with open(HISTORY_FILE, "r") as f: 
            return json.load(f)
    except: 
        return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f: 
        json.dump(history, f, indent=2)

def publish_to_facebook(article, is_recycled=False):
    if not PAGE_ID or not PAGE_TOKEN:
        raise RuntimeError("Facebook secrets are missing.")

    # إضافة الوسوم ومنشن المتابعين
    hashtags = "#Android #AppDevelopment #Networking #VPN #DNS #AntiAtlasDev"
    followers_tag = "@followers"
    
    message = f"📱 {article['title']}\n\nRead more here:\n{article['link']}\n\n{followers_tag}\n{hashtags}"

    if article.get("image"):
        url = f"https://graph.facebook.com/{API_VERSION}/{PAGE_ID}/photos"
        payload = {
            "url": article["image"],
            "caption": message,
            "access_token": PAGE_TOKEN
        }
    else:
        url = f"https://graph.facebook.com/{API_VERSION}/{PAGE_ID}/feed"
        payload = {
            "message": message,
            "link": article["link"],
            "access_token": PAGE_TOKEN
        }

    try:
        response = requests.post(url, data=payload, timeout=20)
        if response.status_code in (200, 201):
            print(f"✅ Published to Facebook: {article['title']}")
            return True
        else:
            print(f"❌ Facebook Error: {response.text}")
            return False
    except Exception as e:
        print(f"Request error: {e}")
        return False

if __name__ == "__main__":
    print("AntiAtlasDev Facebook Bot")
    
    articles = get_articles()
    if not articles: 
        raise SystemExit("No articles found.")
    
    history = load_history()
    new_article = next((a for a in articles if a["link"] not in history), None)
    
    if new_article:
        print("Found NEW article. Sending...")
        if publish_to_facebook(new_article, is_recycled=False):
            history.append(new_article["link"])
            save_history(history)
    else:
        print("No new articles. Recycling an old one...")
        recycled_article = random.choice(articles)
        publish_to_facebook(recycled_article, is_recycled=True)
