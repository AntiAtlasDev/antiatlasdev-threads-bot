import os
import json
import subprocess
import requests
import xml.etree.ElementTree as ET
import re
from html import unescape
from datetime import datetime, timezone  # <-- تمت إضافة هذا السطر

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "paperwf_used_articles.json"

ACCESS_TOKEN = os.environ.get("PAPERWF_ACCESS_TOKEN")
ALIAS = os.environ.get("PAPERWF_ALIAS", "antiatlaasdev") 
HOMEPAGE_URL = "https://antiatlasdev-apps.blogspot.com/"

def get_articles():
    try:
        response = requests.get(RSS_URL, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        articles = []
        for item in root.findall("./channel/item"):
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            desc_html = item.findtext("description", default="")
            desc_text = re.sub(r'<[^>]+>', '', unescape(desc_html or ""))
            if title and link:
                articles.append({"title": title, "link": link, "desc": desc_text[:300]})
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

def publish_to_paperwf(article):
    if not ACCESS_TOKEN:
        raise RuntimeError("PAPERWF_ACCESS_TOKEN is missing.")

    content = f"{article['desc']}\n\n[Read the full article on AntiAtlasDev]({HOMEPAGE_URL})"

    # المسار الصحيح لـ API الخاص بـ WriteFreely
    url = f"https://paper.wf/api/collections/{ALIAS}/posts"
    
    payload = {
        "title": article["title"],
        "body": content,
        "created": datetime.now(timezone.utc).isoformat()
    }

    headers = {
        "Authorization": f"Token {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers, timeout=20)
    
    if response.status_code not in (200, 201):
        print(f"Paper.wf API Error: {response.status_code} - {response.text}")
        return None
        
    print("✅ Published successfully on Paper.wf!")
    return response.json().get("slug", "Published")

def commit_history():
    try:
        subprocess.run(["git", "config", "user.name", "AntiAtlasDev Bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@antiatlasdev.com"], check=True)
        subprocess.run(["git", "add", HISTORY_FILE], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", "Update Paper.wf history"], check=True)
            subprocess.run(["git", "push"], check=True)
    except Exception as e:
        print("Git error:", e)

if __name__ == "__main__":
    print("AntiAtlasDev Paper.wf Bot")
    
    articles = get_articles()
    if not articles: raise SystemExit("No articles found.")
    
    history = load_history()
    article = next((a for a in articles if a["link"] not in history), None)
    
    if article:
        print("Selected:", article["title"])
        url = publish_to_paperwf(article)
        if url:
            history.append(article["link"])
            save_history(history)
            commit_history()
    else:
        print("No new articles to publish.")
