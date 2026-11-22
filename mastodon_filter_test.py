import os
import re
import html
import time
import requests
from datetime import datetime, timezone, timedelta
import subprocess

# ⚠️ ضع اسم الخادم الجديد هنا (بدون https://)
# مثال: "mastodon.online" أو "mstdn.social"
MASTODON_INSTANCE = "YOUR_MASTODON_INSTANCE" 
API = f"https://{MASTODON_INSTANCE}"
TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")

MAX_REPLIES_PER_DAY = 2
MAX_POSTS_PER_DAY = 3

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "mastodon_used_articles.json"
STATE_FILE = "mastodon_daily_state.json"
BLOG = "https://antiatlasdev-apps.blogspot.com/"

SEARCH_TERMS = ["VPN", "DNS", "Android", "Mock location", "Image resizer"]

def headers():
    return {"Authorization": f"Bearer {TOKEN}"}

def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"https?://\S+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def get_account():
    response = requests.get(
        f"{API}/api/v1/accounts/verify_credentials",
        headers=headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()

def search_posts(query):
    response = requests.get(
        f"{API}/api/v2/search",
        headers=headers(),
        params={"q": query, "type": "statuses", "limit": 5},
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("statuses", [])

def load_json(filename, default):
    if not os.path.exists(filename): return default
    try:
        with open(filename, "r") as f: return json.load(f)
    except: return default

def save_json(filename, data):
    with open(filename, "w") as f: json.dump(data, f, indent=2)

def get_daily_state():
    today = datetime.now(timezone.utc).date().isoformat()
    state = load_json(STATE_FILE, {"date": today, "posts_count": 0, "replies_count": 0, "replied_ids": []})
    if state.get("date") != today:
        state = {"date": today, "posts_count": 0, "replies_count": 0, "replied_ids": []}
    return state

def publish_reply(post, message):
    if len(message) > 500: return None
    response = requests.post(
        f"{API}/api/v1/statuses", headers=headers(),
        data={"status": message, "in_reply_to_id": str(post["id"]), "visibility": "public"},
        timeout=20,
    )
    if response.status_code not in (200, 201): return None
    return response.json()

def publish_post(text):
    response = requests.post(
        f"{API}/api/v1/statuses", headers=headers(),
        data={"status": text, "visibility": "public"}, timeout=20,
    )
    if response.status_code not in (200, 201): return None
    return response.json()

def commit_history():
    try:
        subprocess.run(["git", "config", "user.name", "AntiAtlasDev Bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@antiatlasdev.com"], check=True)
        subprocess.run(["git", "add", HISTORY_FILE, STATE_FILE], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", "Update Mastodon history"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("History saved to GitHub.")
    except Exception as e:
        print(f"Git error: {e}")

def main():
    if not TOKEN: 
        raise RuntimeError("MASTODON_ACCESS_TOKEN is missing.")
    if MASTODON_INSTANCE == "YOUR_MASTODON_INSTANCE":
        raise RuntimeError("Please set MASTODON_INSTANCE to your server name.")

    account = get_account()
    my_id = str(account["id"])
    print(f"Authenticated: @{account['acct']} on {MASTODON_INSTANCE}")

    state = get_daily_state()
    print(f"Today's posts: {state['posts_count']}/{MAX_POSTS_PER_DAY} | Replies: {state['replies_count']}/{MAX_REPLIES_PER_DAY}")

    # 1. الردود (بحد أقصى 2 في اليوم)
    if state["replies_count"] < MAX_REPLIES_PER_DAY:
        for query in SEARCH_TERMS:
            if state["replies_count"] >= MAX_REPLIES_PER_DAY: break
            try:
                posts = search_posts(query)
                for post in posts:
                    post_id = str(post["id"])
                    if post_id in state["replied_ids"]: continue
                    if post["account"]["id"] == my_id: continue
                    
                    reply_text = "If you're looking for Android networking tools, I build open-source apps for VPNs and DNS. Check my blog: " + BLOG
                    print(f"Replying to @{post['account'].get('acct')}...")
                    result = publish_reply(post, reply_text)
                    if result:
                        print(f"✅ Replied successfully: {result.get('url')}")
                        state["replies_count"] += 1
                        state["replied_ids"].append(post_id)
                        break # رد واحد لكل كلمة بحث
                time.sleep(5)
            except Exception as e:
                print(f"Search error: {e}")

    # 2. النشر (بحد أقصى 3 في اليوم)
    if state["posts_count"] < MAX_POSTS_PER_DAY:
        try:
            response = requests.get(RSS_URL, timeout=15)
            root = ET.fromstring(response.content)
            articles = []
            for item in root.findall("./channel/item"):
                title = item.findtext("title", default="").strip()
                link = item.findtext("link", default="").strip()
                if title and link:
                    articles.append({"title": title, "link": link})
            
            history = load_json(HISTORY_FILE, [])
            article = next((a for a in articles if a["link"] not in history), None)
            
            if article:
                post_text = f"Discover {article['title']} from AntiAtlasDev!\n\n{article['link']}"
                print("Publishing new article...")
                result = publish_post(post_text)
                if result:
                    print(f"✅ Published: {result.get('url')}")
                    history.append(article["link"])
                    save_json(HISTORY_FILE, history)
                    state["posts_count"] += 1
            else:
                print("No new articles to publish.")
        except Exception as e:
            print(f"Publishing error: {e}")

    save_json(STATE_FILE, state)
    commit_history()
    print(f"Finished. Posts: {state['posts_count']}, Replies: {state['replies_count']}")

if __name__ == "__main__":
    import xml.etree.ElementTree as ET
    main()
