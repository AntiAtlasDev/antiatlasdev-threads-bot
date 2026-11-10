import os
import json
import subprocess
import requests
import xml.etree.ElementTree as ET
import re
from html import unescape

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "telegraph_used_articles.json"
ACCESS_TOKEN = os.environ.get("TELEGRAPH_ACCESS_TOKEN")
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
            
            # تنظيف الوصف من وسوم HTML
            desc_text = re.sub(r'<[^>]+>', '', unescape(desc_html or ""))
            desc_text = " ".join(desc_text.split())[:200] # أول 200 حرف
            
            if title and link:
                articles.append({"title": title, "link": link, "desc": desc_text})
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

def publish_to_telegraph(article):
    if not ACCESS_TOKEN:
        raise RuntimeError("TELEGRAPH_ACCESS_TOKEN is missing.")

    # بناء محتوى الصفحة (وصف + رابط)
    content = [
        {"tag": "p", "children": [article["desc"] + "..."]},
        {"tag": "p", "children": ["Read the full article on AntiAtlasDev:"]},
        {"tag": "p", "children": [{"tag": "a", "attrs": {"href": article["link"]}, "children": ["Read more here"]}]}
    ]

    payload = {
        "access_token": ACCESS_TOKEN,
        "title": article["title"],
        "author_name": "AntiAtlasDev",
        "content": content,
        "return_content": True
    }

    headers = {"Content-Type": "application/json"}
    
    response = requests.post("https://api.telegra.ph/createPage", json=payload, headers=headers, timeout=20)
    
    if response.status_code != 200:
        print(f"HTTP Error: {response.text}")
        return None
        
    data = response.json()
    if not data.get("ok"):
        print(f"Telegraph API Error: {data.get('error')}")
        return None
        
    print("✅ Published successfully:", data["result"]["url"])
    return data["result"]["url"]

def commit_history():
    try:
        subprocess.run(["git", "config", "user.name", "AntiAtlasDev Bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@antiatlasdev.com"], check=True)
        subprocess.run(["git", "add", HISTORY_FILE], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", "Update Telegraph history"], check=True)
            subprocess.run(["git", "push"], check=True)
    except Exception as e:
        print("Git error:", e)

if __name__ == "__main__":
    print("AntiAtlasDev Telegraph Bot")
    
    articles = get_articles()
    if not articles: raise SystemExit("No articles found.")
    
    history = load_history()
    article = next((a for a in articles if a["link"] not in history), None)
    
    if article:
        print("Selected:", article["title"])
        url = publish_to_telegraph(article)
        if url:
            history.append(article["link"])
            save_history(history)
            commit_history()
    else:
        print("No new articles to publish.")
