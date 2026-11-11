import os
import json
import time
import random
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "threads_used_articles.json"
STATE_FILE = "threads_daily_state.json"

# المتغيرات من GitHub Secrets
ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
USER_ID = os.environ.get("THREADS_USER_ID")

# الإعدادات
MAX_POSTS_DAILY = 3
MAX_REPLIES_DAILY = 5

# الكلمات المفتاحية الدقيقة المستخرجة من مقالاتك
SEARCH_QUERIES = [
    "VPN recommendation", "VPN not working", "OpenVPN client", "WireGuard VPN",
    "DNS problem", "DNS Changer", "DNS leak", "Proxy client", "Network tools",
    "Subdomain finder", "DNSTT", "Mock location", "Fake GPS", "GPS route simulator",
    "Offline maps", "Image resizer", "Background eraser", "Image converter",
    "Compress image", "Calorie calculator", "File explorer", "WiFi analyzer"
]

def get_articles():
    try:
        response = requests.get(RSS_URL, timeout=15)
        root = ET.fromstring(response.content)
        articles = []
        for item in root.findall("./channel/item"):
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            if title and link:
                articles.append({"title": title, "link": link})
        return articles
    except Exception as e:
        print("RSS error:", e)
        return []

def load_json(filename, default):
    if not os.path.exists(filename): return default
    try:
        with open(filename, "r") as f: return json.load(f)
    except: return default

def save_json(filename, data):
    with open(filename, "w") as f: json.dump(data, f, indent=2)

def get_daily_state():
    today = datetime.now(timezone.utc).date().isoformat()
    state = load_json(STATE_FILE, {"date": today, "posts_count": 0, "replies_count": 0})
    if state.get("date") != today:
        state = {"date": today, "posts_count": 0, "replies_count": 0}
    return state

def search_and_reply():
    print("--- Processing Replies ---")
    replies_made = 0
    
    # خلط الكلمات المفتاحية لاختيار كلمة عشوائية في كل مرة
    random.shuffle(SEARCH_QUERIES)
    
    for query in SEARCH_QUERIES:
        if replies_made >= 1: # رد واحد فقط في كل تشغيل (لتجنب الحظر)
            break
            
        print(f"Searching for: {query}")
        search_url = "https://graph.threads.net/v1.0/keyword_search"
        params = {"q": query, "search_type": "RECENT", "access_token": ACCESS_TOKEN}
        
        try:
            res = requests.get(search_url, params=params, timeout=15)
            if res.status_code != 200:
                continue
                
            data = res.json().get("data", [])
            for post in data:
                if post.get("username") == "antiatlasdev": continue # تجنب الرد على النفس
                
                post_id = post.get("id")
                if not post_id: continue

                # نصوص ردود متنوعة (بدون روابط مباشرة لتجنب الحظر)
                replies = [
                    "If you're looking for Android network tools, I develop independent apps for VPNs, DNS, and diagnostics. Check my profile!",
                    "As an Android dev, I build utilities for networking and security. You might find something useful on my page!",
                    "Thanks for sharing this. I also build Android tools (VPNs, DNS, GPS). Feel free to check my profile for more."
                ]
                reply_text = random.choice(replies)

                # إنشاء حاوية الرد
                create_url = f"https://graph.threads.net/v1.0/{USER_ID}/threads"
                payload = {"media_type": "TEXT", "text": reply_text, "reply_to_id": post_id, "access_token": ACCESS_TOKEN}
                
                create_res = requests.post(create_url, data=payload, timeout=15)
                if create_res.status_code != 200:
                    continue
                    
                creation_id = create_res.json().get("id")
                print("Waiting 30 seconds before publishing reply...")
                time.sleep(30) # الانتظار 30 ثانية قبل النشر
                
                # نشر الرد
                publish_url = f"https://graph.threads.net/v1.0/{USER_ID}/threads_publish"
                pub_payload = {"creation_id": creation_id, "access_token": ACCESS_TOKEN}
                pub_res = requests.post(publish_url, data=pub_payload, timeout=15)
                
                if pub_res.status_code == 200:
                    print(f"✅ Replied to @{post.get('username')}")
                    replies_made += 1
                    break # نكتفي برد واحد لكل كلمة بحث
                    
        except Exception as e:
            print(f"Search error: {e}")

    return replies_made

def publish_post(text):
    print("Publishing post...")
    url_create = f"https://graph.threads.net/v1.0/{USER_ID}/threads"
    payload_create = {"media_type": "TEXT", "text": text, "access_token": ACCESS_TOKEN}
    
    res = requests.post(url_create, data=payload_create, timeout=15)
    if res.status_code != 200:
        print(f"Error creating post: {res.text}")
        return False
        
    creation_id = res.json().get("id")
    time.sleep(30) # الانتظار 30 ثانية
    
    url_publish = f"https://graph.threads.net/v1.0/{USER_ID}/threads_publish"
    pub_payload = {"creation_id": creation_id, "access_token": ACCESS_TOKEN}
    pub_res = requests.post(url_publish, data=pub_payload, timeout=15)
    
    if pub_res.status_code == 200:
        print("✅ Published post successfully.")
        return True
    return False

if __name__ == "__main__":
    print("AntiAtlasDev Threads Bot")
    state = get_daily_state()
    
    # 1. محاولة الردود (إذا لم نصل للحد اليومي)
    if state["replies_count"] < MAX_REPLIES_DAILY:
        new_replies = search_and_reply()
        state["replies_count"] += new_replies
        save_json(STATE_FILE, state)

    # 2. محاولة النشر (إذا لم نصل للحد اليومي)
    if state["posts_count"] < MAX_POSTS_DAILY:
        articles = get_articles()
        history = load_json(HISTORY_FILE, [])
        
        # البحث عن مقال جديد
        article = next((a for a in articles if a["link"] not in history), None)
        
        if article:
            # نشر مقال جديد
            draft = f"Discover {article['title']} from AntiAtlasDev!\n\nRead more:\n{article['link']}"
            if publish_post(draft):
                history.append(article["link"])
                save_json(HISTORY_FILE, history)
                state["posts_count"] += 1
        else:
            # إعادة نشر مقال قديم (Flashback)
            print("No new articles. Recycling...")
            recycled = random.choice(articles)
            draft = f"🔄 Flashback: {recycled['title']}\n\nRead more:\n{recycled['link']}"
            if publish_post(draft):
                state["posts_count"] += 1

    save_json(STATE_FILE, state)
    print(f"Finished. Posts: {state['posts_count']}, Replies: {state['replies_count']}")
