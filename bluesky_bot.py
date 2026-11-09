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
# تم تغيير اسم ملف الحالة لتجاوز الملف القديم الذي يسبب الخطأ
STATE_FILE = "bluesky_daily_state_v2.json"

# الحدود اليومية
DAILY_LIMIT_POSTS = 5
DAILY_LIMIT_REPLIES = 3

# كلمات البحث للردود
SEARCH_QUERIES = [
    "VPN recommendation",
    "Android networking tools",
    "DNS not working",
    "WireGuard help",
    "looking for a VPN"
]

def get_articles():
    try:
        response = requests.get(
            RSS_URL,
            headers={"User-Agent": "AntiAtlasDevBlueskyBot/1.0"},
            timeout=30
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        articles = []

        for item in root.findall("./channel/item"):
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()

            if title and link:
                articles.append({
                    "title": title,
                    "link": link
                })

        print("Total articles:", len(articles))
        return articles

    except Exception as error:
        print("RSS error:", error)
        return []

def load_json(filename, default):
    if not os.path.exists(filename):
        return default

    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        print("Could not read:", filename)
        return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

def get_daily_state():
    today = datetime.now(timezone.utc).date().isoformat()

    # تم استخدام .get() لتجنب أي أخطاء إذا كان الملف فارغاً
    state = load_json(STATE_FILE, {
        "date": today,
        "posts_count": 0,
        "replies_count": 0
    })

    if state.get("date") != today:
        state = {
            "date": today,
            "posts_count": 0,
            "replies_count": 0
        }
    elif "posts_count" not in state or "replies_count" not in state:
        state["posts_count"] = state.get("posts_count", 0)
        state["replies_count"] = state.get("replies_count", 0)

    return state

def select_article(articles, history):
    for article in articles:
        if article["link"] not in history:
            return article

    print("All articles have already been used.")
    return None

def login_bluesky():
    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")

    if not handle or not password:
        raise RuntimeError("Bluesky secrets are missing.")

    client = Client()
    client.login(handle, password)
    return client

def process_replies(client, max_replies):
    print("--- Processing Replies ---")
    replies_made = 0
    
    for query in SEARCH_QUERIES:
        if replies_made >= max_replies:
            break
            
        try:
            # البحث عن المنشورات
            search_results = client.app.bsky.feed.search_posts({'q': query, 'limit': 5})
            
            if not search_results or not search_results.posts:
                continue
                
            for post in search_results.posts:
                # تجنب الرد على النفس
                if post.author.did == client.me.did:
                    continue
                    
                # تجنب الرد إذا كان منشوراً قديماً (أكثر من 24 ساعة)
                try:
                    created_at = datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00'))
                    if (datetime.now(timezone.utc) - created_at).days >= 1:
                        continue
                except:
                    pass

                # نصوص الردود العشوائية
                replies = [
                    "If you're looking for Android network tools, I develop independent apps for VPNs, DNS, and network diagnostics. Check them out here: https://antiatlasdev-apps.blogspot.com/",
                    "As an Android dev, I build utilities for networking and security. You might find something useful here: https://antiatlasdev-apps.blogspot.com/"
                ]
                
                reply_text = random.choice(replies)
                
                # إنشاء الرد
                client.send_post(
                    text=reply_text,
                    reply_to={'uri': post.uri, 'cid': post.cid}
                )
                
                print(f"Replied to @{post.author.handle}")
                replies_made += 1
                time.sleep(15) # انتظار بين الردود
                
                if replies_made >= max_replies:
                    break
                    
        except Exception as e:
            print(f"Search error for '{query}': {e}")

    return replies_made

def publish_to_bluesky(client, text):
    response = client.send_post(text=text)
    if not response:
        raise RuntimeError("Bluesky publication failed.")
    print("Published successfully.")
    return response

def commit_history():
    try:
        subprocess.run(["git", "config", "user.name", "AntiAtlasDev Bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@antiatlasdev.com"], check=True)
        subprocess.run(["git", "add", HISTORY_FILE, STATE_FILE], check=True)

        result = subprocess.run(["git", "diff", "--cached", "--quiet"])

        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", "Update Bluesky history"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("Bluesky history saved.")
        elif result.returncode == 0:
            print("No history changes.")
        else:
            raise RuntimeError("Git diff failed.")
    except Exception as error:
        print("History save error:", error)
        raise

if __name__ == "__main__":
    print("AntiAtlasDev Bluesky Bot - Posts & Replies")
    
    state = get_daily_state()
    print(f"Today's posts: {state.get('posts_count', 0)}/{DAILY_LIMIT_POSTS}")
    print(f"Today's replies: {state.get('replies_count', 0)}/{DAILY_LIMIT_REPLIES}")

    client = login_bluesky()

    # 1. معالجة الردود أولاً
    current_replies = state.get("replies_count", 0)
    if current_replies < DAILY_LIMIT_REPLIES:
        remaining_replies = DAILY_LIMIT_REPLIES - current_replies
        new_replies = process_replies(client, remaining_replies)
        state["replies_count"] = current_replies + new_replies

    # 2. نشر مقال جديد
    current_posts = state.get("posts_count", 0)
    if current_posts < DAILY_LIMIT_POSTS:
        articles = get_articles()
        history = load_json(HISTORY_FILE, [])
        article = select_article(articles, history)

        if article:
            post_text = (
                f"Discover {article['title']} from AntiAtlasDev! 📱\n\n"
                f"Read more:\n{article['link']}\n\n"
                f"#Android #AppDevelopment"
            )
            publish_to_bluesky(client, post_text)
            history.append(article["link"])
            state["posts_count"] = current_posts + 1
            save_json(HISTORY_FILE, history)

    # حفظ الحالة النهائية
    save_json(STATE_FILE, state)
    commit_history()

    print(f"Finished. Posts: {state.get('posts_count', 0)}, Replies: {state.get('replies_count', 0)}")
