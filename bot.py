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

ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
USER_ID = os.environ.get("THREADS_USER_ID")

MAX_POSTS_DAILY = 3
MAX_REPLIES_DAILY = 5

SEARCH_QUERIES = ["VPN recommendation", "DNS problem", "Mock location", "Image resizer"]

def get_articles():
    try:
        response = requests.get(RSS_URL, timeout=15)
        root = ET.fromstring(response.content)
        return [{"title": item.findtext("title", "").strip(), "link": item.findtext("link", "").strip()} 
                for item in root.findall("./channel/item") if item.findtext("title") and item.findtext("link")]
    except: return []

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
    if state.get("date") != today: state = {"date": today, "posts_count": 0, "replies_count": 0}
    return state

def search_and_reply():
    print("--- Processing Replies ---")
    random.shuffle(SEARCH_QUERIES)
    for query in SEARCH_QUERIES:
        print(f"Searching for: {query}")
        try:
            res = requests.get("https://graph.threads.net/v1.0/keyword_search", 
                               params={"q": query, "search_type": "RECENT", "access_token": ACCESS_TOKEN}, timeout=10)
            if res.status_code != 200: continue
            for post in res.json().get("data", []):
                username, post_id = post.get("username"), post.get("id")
                if not username or not post_id or username == "antiatlasdev": continue
                
                reply_text = "If you're looking for Android tools, I build apps for VPNs and DNS. Check my profile!"
                create_url = f"https://graph.threads.net/v1.0/{USER_ID}/threads"
                payload = {"media_type": "TEXT", "text": reply_text, "reply_to_id": post_id, "access_token": ACCESS_TOKEN}
                
                create_res = requests.post(create_url, data=payload, timeout=10)
                if create_res.status_code != 200: continue
                
                creation_id = create_res.json().get("id")
                time.sleep(5) # انتظار 5 ثوانٍ فقط
                
                pub_res = requests.post(f"https://graph.threads.net/v1.0/{USER_ID}/threads_publish", 
                                        data={"creation_id": creation_id, "access_token": ACCESS_TOKEN}, timeout=10)
                if pub_res.status_code == 200:
                    print(f"✅ Replied to @{username}")
                    return 1
        except: pass
    return 0

def publish_post(text):
    print("Publishing post...")
    url_create = f"https://graph.threads.net/v1.0/{USER_ID}/threads"
    res = requests.post(url_create, data={"media_type": "TEXT", "text": text, "access_token": ACCESS_TOKEN}, timeout=10)
    if res.status_code != 200: return False
    
    creation_id = res.json().get("id")
    time.sleep(5) # انتظار 5 ثوانٍ فقط
    
    pub_res = requests.post(f"https://graph.threads.net/v1.0/{USER_ID}/threads_publish", 
                            data={"creation_id": creation_id, "access_token": ACCESS_TOKEN}, timeout=10)
    return pub_res.status_code == 200

if __name__ == "__main__":
    state = get_daily_state()
    if state["replies_count"] < MAX_REPLIES_DAILY:
        state["replies_count"] += search_and_reply()
        save_json(STATE_FILE, state)

    if state["posts_count"] < MAX_POSTS_DAILY:
        articles = get_articles()
        history = load_json(HISTORY_FILE, [])
        article = next((a for a in articles if a["link"] not in history), None)
        
        if article:
            if publish_post(f"Discover {article['title']}!\n{article['link']}"):
                history.append(article["link"])
                save_json(HISTORY_FILE, history)
                state["posts_count"] += 1
        else:
            recycled = random.choice(articles)
            if publish_post(f"🔄 Flashback: {recycled['title']}\n{recycled['link']}"):
                state["posts_count"] += 1

    save_json(STATE_FILE, state)
    print(f"Finished. Posts: {state['posts_count']}, Replies: {state['replies_count']}")
