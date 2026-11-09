import os
import json
import subprocess
import requests
import xml.etree.ElementTree as ET
import time

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "used_articles.json"

# سيتم جلب التوكن من إعدادات GitHub
ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")

def get_articles():
    try:
        response = requests.get(
            RSS_URL,
            headers={"User-Agent": "AntiAtlasDevThreadsBot/1.0"},
            timeout=30
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        items = root.findall("./channel/item")

        articles = []

        for item in items:
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

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        print("History file could not be read.")
        return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)

def select_article(articles, history):
    unused = [
        article for article in articles
        if article["link"] not in history
    ]

    if not unused:
        print("All articles have been used. Starting a new cycle.")
        history.clear()
        unused = articles

    if not unused:
        return None

    article = unused[0]
    history.append(article["link"])
    return article

def prepare_post(article):
    return (
        f"Discover {article['title']} from AntiAtlasDev!\n\n"
        f"Read more:\n{article['link']}"
    )

def publish_to_threads(text):
    if not ACCESS_TOKEN:
        raise RuntimeError("THREADS_ACCESS_TOKEN is missing.")

    # 1. إنشاء الحاوية (Container)
    print("Creating Threads container...")
    url_create = "https://graph.threads.net/v1.0/me/threads"
    payload_create = {
        "media_type": "TEXT",
        "text": text,
        "access_token": ACCESS_TOKEN
    }
    
    response = requests.post(url_create, data=payload_create)
    if response.status_code != 200:
        print(f"Error creating container: {response.text}")
        return False
    
    creation_id = response.json().get("id")
    print(f"Container created: {creation_id}")

    # Threads يتطلب الانتظار 30 ثانية قبل النشر
    print("Waiting 30 seconds for container to process...")
    time.sleep(30)

    # 2. النشر (Publish)
    print("Publishing to Threads...")
    url_publish = "https://graph.threads.net/v1.0/me/threads_publish"
    payload_publish = {
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN
    }
    
    response = requests.post(url_publish, data=payload_publish)
    if response.status_code == 200:
        print("✅ Published successfully on Threads!")
        print("Post ID:", response.json().get("id"))
        return True
    else:
        print(f"Error publishing: {response.text}")
        return False

def commit_history():
    try:
        subprocess.run(["git", "config", "user.name", "AntiAtlasDev Bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@antiatlasdev.com"], check=True)
        subprocess.run(["git", "add", HISTORY_FILE], check=True)

        result = subprocess.run(["git", "diff", "--cached", "--quiet"])

        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", "Update used articles history"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("Article history saved to GitHub.")
        elif result.returncode == 0:
            print("No history changes to save.")
        else:
            raise RuntimeError("Git diff failed.")
    except Exception as error:
        print("Git history save error:", error)
        raise

if __name__ == "__main__":
    print("AntiAtlasDev Threads Bot")
    print("Mode: LIVE PUBLISHING")

    articles = get_articles()

    if not articles:
        print("No articles available. Stopping.")
        raise SystemExit(1)

    history = load_history()
    print("Previously used articles:", len(history))

    article = select_article(articles, history)

    if article:
        draft = prepare_post(article)

        print("\nSelected article:")
        print(article["title"])

        print("\nPrepared Threads post:")
        print("------------------------------")
        print(draft)
        print("------------------------------")

        # النشر الفعلي
        success = publish_to_threads(draft)

        if success:
            save_history(history)
            commit_history()
            print("\nFinished successfully.")
        else:
            print("\nPublishing failed. History not saved.")
