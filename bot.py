import os
import json
import subprocess
import requests
import xml.etree.ElementTree as ET
import time
import random

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "used_articles.json"

ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
USER_ID = os.environ.get("THREADS_USER_ID")

# إعدادات البحث
SEARCH_QUERIES = ["VPN recommendation", "DNS not working", "Android network tools"]
MAX_REPLIES_PER_RUN = 1 # الرد على منشور واحد فقط في كل تشغيل (حماية)

def get_articles():
    try:
        response = requests.get(RSS_URL, headers={"User-Agent": "AntiAtlasDevBot/1.0"}, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        articles = []
        for item in root.findall("./channel/item"):
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            if title and link:
                articles.append({"title": title, "link": link})
        print("Total articles:", len(articles))
        return articles
    except Exception as error:
        print("RSS error:", error)
        return []

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)

def select_article(articles, history):
    unused = [article for article in articles if article["link"] not in history]
    if not unused:
        print("All articles have been used. Starting a new cycle.")
        history.clear()
        unused = articles
    if not unused:
        return None
    article = unused[0]
    history.append(article["link"])
    return article

def search_and_reply():
    print("--- Processing Replies ---")
    if not USER_ID:
        print("THREADS_USER_ID is missing. Cannot search.")
        return 0

    replies_made = 0
    for query in SEARCH_QUERIES:
        if replies_made >= MAX_REPLIES_PER_RUN:
            break
            
        print(f"Searching for: {query}")
        search_url = "https://graph.threads.net/v1.0/keyword_search"
        params = {
            "q": query,
            "search_type": "RECENT",
            "access_token": ACCESS_TOKEN
        }
        
        try:
            response = requests.get(search_url, params=params, timeout=15)
            if response.status_code != 200:
                print(f"Search error ({response.status_code}): {response.text}")
                continue
                
            data = response.json().get("data", [])
            if not data:
                print("No results found.")
                continue

            for post in data:
                # تجنب الرد على منشوراتنا
                if post.get("username") == "antiatlasdev": 
                    continue
                
                post_id = post.get("id")
                if not post_id:
                    continue

                replies = [
                    "If you're looking for Android network tools, I develop independent apps for VPNs, DNS, and diagnostics. Check them out here: https://antiatlasdev-apps.blogspot.com/",
                    "As an Android dev, I build utilities for networking and security. You might find something useful here: https://antiatlasdev-apps.blogspot.com/"
                ]
                reply_text = random.choice(replies)

                create_url = f"https://graph.threads.net/v1.0/{USER_ID}/threads"
                payload = {
                    "media_type": "TEXT",
                    "text": reply_text,
                    "reply_to_id": post_id,
                    "access_token": ACCESS_TOKEN
                }
                
                res = requests.post(create_url, data=payload, timeout=15)
                if res.status_code != 200:
                    print(f"Error creating reply container: {res.text}")
                    continue
                    
                creation_id = res.json().get("id")
                print(f"Reply container created: {creation_id}")
                
                # الانتظار 30 ثانية قبل النشر
                time.sleep(30)
                
                publish_url = f"https://graph.threads.net/v1.0/{USER_ID}/threads_publish"
                pub_payload = {
                    "creation_id": creation_id,
                    "access_token": ACCESS_TOKEN
                }
                
                pub_res = requests.post(publish_url, data=pub_payload, timeout=15)
                if pub_res.status_code == 200:
                    print(f"✅ Replied to @{post.get('username')} successfully!")
                    replies_made += 1
                    break # نكتفي برد واحد لكل استعلام
                else:
                    print(f"Error publishing reply: {pub_res.text}")
                    
        except Exception as e:
            print(f"Exception during search/reply: {e}")

    return replies_made

def publish_post(text):
    print("--- Publishing New Article ---")
    url_create = f"https://graph.threads.net/v1.0/{USER_ID}/threads"
    payload_create = {
        "media_type": "TEXT",
        "text": text,
        "access_token": ACCESS_TOKEN
    }
    try:
        response = requests.post(url_create, data=payload_create, timeout=15)
        if response.status_code != 200:
            print(f"Error creating container: {response.text}")
            return False
        creation_id = response.json().get("id")
        print(f"Container created: {creation_id}")
        print("Waiting 30 seconds...")
        time.sleep(30)
        
        url_publish = f"https://graph.threads.net/v1.0/{USER_ID}/threads_publish"
        payload_publish = {"creation_id": creation_id, "access_token": ACCESS_TOKEN}
        response = requests.post(url_publish, data=payload_publish, timeout=15)
        if response.status_code == 200:
            print("✅ Published successfully!")
            return True
        else:
            print(f"Error publishing: {response.text}")
            return False
    except Exception as e:
        print(f"Exception during publish: {e}")
        return False

def commit_history():
    try:
        subprocess.run(["git", "config", "user.name", "AntiAtlasDev Bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@antiatlasdev.com"], check=True)
        subprocess.run(["git", "add", HISTORY_FILE], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", "Update history"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("History saved.")
    except Exception as error:
        print("Git history save error:", error)

if __name__ == "__main__":
    print("AntiAtlasDev Threads Bot - Search, Reply & Publish")
    
    # 1. محاولة الردود أولاً
    replies = search_and_reply()
    
    # 2. نشر مقال جديد
    articles = get_articles()
    if articles:
        history = load_history()
        article = select_article(articles, history)
        if article:
            draft = f"Discover {article['title']} from AntiAtlasDev!\n\nRead more:\n{article['link']}"
            success = publish_post(draft)
            if success:
                save_history(history)
                commit_history()
    
    print("\nBot finished.")
