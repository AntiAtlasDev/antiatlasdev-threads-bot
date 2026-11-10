import os
import json
import random
import requests
import xml.etree.ElementTree as ET
import re
from html import unescape

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "telegram_used_articles.json"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def get_articles():
    try:
        response = requests.get(RSS_URL, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        articles = []
        
        # مساحة الأسماء (Namespace) الخاصة بصور المدونة
        ns = {'media': 'http://search.yahoo.com/mrss/'}
        
        for item in root.findall("./channel/item"):
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            
            # جلب الصورة المصغرة من الـ RSS
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
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r") as f: return json.load(f)
    except: return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f: json.dump(history, f, indent=2)

def send_to_telegram(article, is_recycled=False):
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Telegram secrets are missing.")

    # صياغة الرسالة
    if is_recycled:
        text = f"🔄 <b>Flashback:</b> {article['title']}\n\nRead more here:\n{article['link']}"
    else:
        text = f"📱 <b>New App:</b> {article['title']}\n\nRead more here:\n{article['link']}"

    if article.get("image"):
        # إرسال صورة مع النص
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHAT_ID,
            "photo": article["image"],
            "caption": text,
            "parse_mode": "HTML"
        }
    else:
        # إرسال نص فقط إذا لم توجد صورة
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }

    try:
        response = requests.post(url, data=payload, timeout=15)
        if response.status_code == 200:
            print(f"✅ Published: {article['title']}")
            return True
        else:
            print(f"❌ Telegram Error: {response.text}")
            return False
    except Exception as e:
        print(f"Request error: {e}")
        return False

if __name__ == "__main__":
    print("AntiAtlasDev Telegram Bot")
    
    articles = get_articles()
    if not articles: 
        raise SystemExit("No articles found in RSS.")
    
    history = load_history()
    
    # 1. البحث عن مقال جديد لم ينشر من قبل
    new_article = next((a for a in articles if a["link"] not in history), None)
    
    if new_article:
        print("Found NEW article. Sending...")
        if send_to_telegram(new_article, is_recycled=False):
            history.append(new_article["link"])
            save_history(history)
    else:
        # 2. إذا لم يوجد جديد، نختار مقالاً قديماً عشوائياً
        print("No new articles. Recycling an old one...")
        recycled_article = random.choice(articles)
        send_to_telegram(recycled_article, is_recycled=True)
        # لا نضيفه للسجل لأنه موجود مسبقاً
