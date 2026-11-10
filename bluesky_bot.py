import os
import json
import subprocess
import time
import random
from datetime import datetime, timezone

import requests
import xml.etree.ElementTree as ET
from atproto import Client

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "bluesky_used_articles.json"
STATE_FILE = "bluesky_daily_state_v5.json" # اسم جديد لتجنب تداخل الملفات القديمة

MAX_REPLIES_DAILY = 3
MAX_POSTS_DAILY = 5

SEARCH_QUERIES = ["VPN recommendation", "DNS not working", "Android networking"]

def get_articles():
    try:
        # إضافة timeout هنا لمنع التعليق
        response = requests.get(RSS_URL, headers={"User-Agent": "Bot/1.0"}, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        return [{"title": item.findtext("title", "").strip(), "link": item.findtext("link", "").strip()} 
                for item in root.findall("./channel/item") if item.findtext("title") and item.findtext("link")]
    except Exception as e:
        print(f"RSS error: {e}")
        return []

def get_daily_state():
    today = datetime.now(timezone.utc).date().isoformat()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: state = json.load(f)
        except: state = {}
    else: state = {}
    
    if state.get("date") != today:
        state = {"date": today, "posts_count": 0, "replies_count": 0}
    return state

def save_state(state):
    with open(STATE_FILE, "w") as f: json.dump(state, f)

def save_history(history):
    with open(HISTORY_FILE, "w") as f: json.dump(history, f, indent=2)

def load_history():
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r") as f: return json.load(f)
    except: return []

def commit_history():
    try:
        subprocess.run(["git", "config", "user.name", "Bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@example.com"], check=True)
        subprocess.run(["git", "add", HISTORY_FILE, STATE_FILE], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", "Update Bluesky state"], check=True)
            subprocess.run(["git", "push"], check=True)
    except Exception as e:
        print(f"Git commit error: {e}")

def main():
    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not password: 
        raise RuntimeError("Secrets missing.")
    
    client = Client()
    try:
        print("Attempting to log in to Bluesky...")
        client.login(handle, password)
        print("Logged in successfully.")
    except Exception as e:
        print(f"Login failed (Account might be suspended): {e}")
        raise SystemExit(1)

    state = get_daily_state()
    print(f"Replies today: {state['replies_count']}/{MAX_REPLIES_DAILY} | Posts today: {state['posts_count']}/{MAX_POSTS_DAILY}")

    # 1. الردود
    if state["replies_count"] < MAX_REPLIES_DAILY:
        for query in SEARCH_QUERIES:
            try:
                print(f"Searching for: {query}")
                results = client.app.bsky.feed.search_posts({'q': query, 'limit': 3})
                
                if results and results.posts:
                    for post in results.posts:
                        if post.author.did == client.me.did: continue
                        
                        # تجنب الردود على المنشورات القديمة
                        try:
                            created_at = datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00'))
                            if (datetime.now(timezone.utc) - created_at).days >= 1: continue
                        except: pass

                        reply_text = random.choice([
                            "I build Android networking tools. You might find something useful here: https://antiatlasdev-apps.blogspot.com/",
                            "As an Android dev, I create utilities for VPNs and DNS. Check my blog: https://antiatlasdev-apps.blogspot.com/"
                        ])
                        
                        print(f"Replying to @{post.author.handle}...")
                        client.send_post(
                            text=reply_text, 
                            reply_to={
                                "parent": {"uri": post.uri, "cid": post.cid}, 
                                "root": {"uri": post.uri, "cid": post.cid}
                            }
                        )
                        print("✅ Replied successfully!")
                        state["replies_count"] += 1
                        time.sleep(20) # انتظار 20 ثانية بين الردود
                        break # رد واحد لكل استعلام
                if state["replies_count"] >= MAX_REPLIES_DAILY: break
            except Exception as e:
                print(f"Reply error: {e}")

    # 2. النشر
    if state["posts_count"] < MAX_POSTS_DAILY:
        articles = get_articles()
        history = load_history()
        article = next((a for a in articles if a["link"] not in history), None)
        
        if article:
            post_text = f"Discover {article['title']} from AntiAtlasDev! 📱\n\nRead more:\n{article['link']}\n\n#Android #AppDevelopment"
            try:
                print(f"Publishing article: {article['title']}")
                client.send_post(text=post_text)
                print("✅ Published successfully!")
                history.append(article["link"])
                state["posts_count"] += 1
                save_history(history)
            except Exception as e:
                print(f"Publishing error: {e}")

    save_state(state)
    commit_history()
    print("Finished.")

if __name__ == "__main__":
    main()
