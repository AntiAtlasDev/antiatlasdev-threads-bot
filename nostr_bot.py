import os
import json
import subprocess
import asyncio
import time
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from nostr_sdk import Keys, Client, RelayUrl, Event, Filter, Kind, ReqTarget
from secp256k1 import PrivateKey

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "nostr_used_articles.json"
STATE_FILE = "nostr_daily_state.json"
PRIVATE_KEY_HEX = os.environ.get("NOSTR_PRIVATE_KEY")

MAX_REPLIES_DAILY = 2
MAX_POSTS_DAILY = 3

SEARCH_TERMS = ["VPN", "DNS", "Android", "Mock location", "Image resizer"]

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
    state = load_json(STATE_FILE, {"date": today, "posts_count": 0, "replies_count": 0, "replied_ids": []})
    if state.get("date") != today:
        state = {"date": today, "posts_count": 0, "replies_count": 0, "replied_ids": []}
    return state

def create_signed_event(content, private_key_hex, tags=None):
    sk = PrivateKey(bytes.fromhex(private_key_hex))
    pubkey_hex = sk.pubkey.serialize()[1:].hex()
    created_at = int(time.time())
    kind = 1
    if tags is None: tags = []
    
    event_data = [0, pubkey_hex, created_at, kind, tags, content]
    serialized = json.dumps(event_data, separators=(',', ':'), ensure_ascii=False)
    event_id = hashlib.sha256(serialized.encode()).hexdigest()
    sig = sk.schnorr_sign(bytes.fromhex(event_id), None, raw=True)
    
    return {
        "id": event_id, "pubkey": pubkey_hex, "created_at": created_at,
        "kind": kind, "tags": tags, "content": content, "sig": sig.hex()
    }

async def search_and_reply(client, state):
    if state["replies_count"] >= MAX_REPLIES_DAILY:
        print("Daily reply limit reached.")
        return 0

    for term in SEARCH_TERMS:
        print(f"Searching for: {term}")
        # استخدام Filter().search() للبحث عن الكلمات المفتاحية
        filter = Filter().kind(Kind(1)).search(term).limit(5)
        try:
            # الدالة الصحيحة في الإصدار الجديد هي fetch_events
            events = await client.fetch_events(ReqTarget.auto([filter]))
            
            for event in events:
                event_id = event.id().to_hex()
                if event_id in state["replied_ids"]:
                    continue
                    
                author_pubkey = event.pubkey().to_hex()
                if author_pubkey == client.keys().public_key().to_hex():
                    continue
                    
                reply_text = "If you're looking for Android tools, I build apps for VPNs and DNS. Check my profile!"
                
                # إنشاء وسوم الرد (e للمنشور، p لصاحب المنشور)
                tags = [["e", event_id, "", "reply"], ["p", author_pubkey]]
                
                reply_event = create_signed_event(reply_text, PRIVATE_KEY_HEX, tags)
                await client.send_event(Event.from_json(json.dumps(reply_event)))
                
                print(f"✅ Replied to event {event_id[:8]}...")
                state["replied_ids"].append(event_id)
                state["replies_count"] += 1
                time.sleep(5)
                return 1
        except Exception as e:
            print(f"Search error for {term}: {e}")

    return 0

async def publish_post(client, article, state):
    if state["posts_count"] >= MAX_POSTS_DAILY:
        print("Daily post limit reached.")
        return False

    post_text = f"Discover {article['title']} from AntiAtlasDev! 📱\n\nRead more:\n{article['link']}\n\n#Android #AppDevelopment"
    event_json = create_signed_event(post_text, PRIVATE_KEY_HEX)
    
    try:
        await client.send_event(Event.from_json(json.dumps(event_json)))
        print(f"✅ Published: {article['title']}")
        state["posts_count"] += 1
        return True
    except Exception as e:
        print(f"Publish error: {e}")
        return False

async def main():
    print("AntiAtlasDev Nostr Bot")
    state = get_daily_state()
    
    client = Client()
    await client.add_relay(RelayUrl.parse("wss://relay.damus.io"))
    await client.add_relay(RelayUrl.parse("wss://nos.lol"))
    await client.add_relay(RelayUrl.parse("wss://relay.primal.net"))
    await client.connect()

    if state["replies_count"] < MAX_REPLIES_DAILY:
        await search_and_reply(client, state)
    
    if state["posts_count"] < MAX_POSTS_DAILY:
        articles = get_articles()
        history = load_json(HISTORY_FILE, [])
        
        new_article = next((a for a in articles if a["link"] not in history), None)
        if new_article:
            if await publish_post(client, new_article, state):
                history.append(new_article["link"])
                save_json(HISTORY_FILE, history)
        else:
            print("No new articles to publish.")

    save_json(STATE_FILE, state)
    
    subprocess.run(["git", "config", "user.name", "Bot"], check=True)
    subprocess.run(["git", "config", "user.email", "bot@example.com"], check=True)
    subprocess.run(["git", "add", STATE_FILE, HISTORY_FILE], check=True)
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode == 1:
        subprocess.run(["git", "commit", "-m", "Update Nostr state"], check=True)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False)
        subprocess.run(["git", "push"], check=True)

    await client.disconnect()
    print(f"Finished. Posts: {state['posts_count']}, Replies: {state['replies_count']}")

if __name__ == "__main__":
    asyncio.run(main())
