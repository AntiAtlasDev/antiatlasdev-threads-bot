import os
import json
import subprocess
import asyncio
import requests
import xml.etree.ElementTree as ET
from nostr_sdk import Keys, Client, EventBuilder

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "nostr_used_articles.json"
PRIVATE_KEY_HEX = os.environ.get("NOSTR_PRIVATE_KEY")

def get_articles():
    try:
        response = requests.get(RSS_URL, timeout=15)
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

async def publish_to_nostr(article):
    if not PRIVATE_KEY_HEX:
        raise RuntimeError("NOSTR_PRIVATE_KEY is missing.")

    # إعداد المفاتيح والعميل
    keys = Keys.parse(PRIVATE_KEY_HEX)
    client = Client(keys)

    # إضافة خوادم الترحيل (Relays) - لاحظ استخدام await
    await client.add_relay("wss://relay.damus.io")
    await client.add_relay("wss://nos.lol")
    await client.add_relay("wss://relay.primal.net")
    await client.connect()

    # تجهيز محتوى المنشور (استخدام text_note بدلاً من new_text_note)
    post_text = f"Discover {article['title']} from AntiAtlasDev! 📱\n\nRead more:\n{article['link']}\n\n#Android #AppDevelopment"
    
    # إنشاء الحدث (EventBuilder.text_note موجودة في الإصدارات الحديثة) [citation:1]
    builder = EventBuilder.text_note(post_text)
    
    # توقيع الحدث وإرساله (لاحظ await)
    event = builder.to_event(keys)
    
    print("Publishing to Nostr relays...")
    output = await client.send_event(event)
    
    print(f"✅ Published successfully on Nostr! Event ID: {output.id().to_hex()}")
    await client.disconnect()
    return True

def commit_history():
    try:
        subprocess.run(["git", "config", "user.name", "AntiAtlasDev Bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@antiatlasdev.com"], check=True)
        subprocess.run(["git", "add", HISTORY_FILE], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", "Update Nostr history"], check=True)
            subprocess.run(["git", "push"], check=True)
    except Exception as e:
        print("Git error:", e)

async def main():
    print("AntiAtlasDev Nostr Bot")
    
    articles = get_articles()
    if not articles: raise SystemExit("No articles found.")
    
    history = load_history()
    article = next((a for a in articles if a["link"] not in history), None)
    
    if article:
        print("Selected:", article["title"])
        # تشغيل دالة النشر غير المتزامنة
        if await publish_to_nostr(article):
            history.append(article["link"])
            save_history(history)
            commit_history()
    else:
        print("No new articles to publish.")

if __name__ == "__main__":
    # تشغيل البرنامج باستخدام asyncio
    asyncio.run(main())
