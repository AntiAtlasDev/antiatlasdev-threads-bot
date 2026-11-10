import os
import re
import html
import time
import requests
from datetime import datetime, timezone, timedelta

API = "https://mastodon.social"
TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")
BLOG = "https://antiatlasdev-apps.blogspot.com/"

MAX_REPLIES_DAILY = 3
MAX_POSTS_DAILY = 5

SEARCH_TERMS = ["VPN recommendation", "DNS not working", "Android networking"]

def headers():
    return {"Authorization": f"Bearer {TOKEN}"}

def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"https?://\S+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def get_account():
    response = requests.get(f"{API}/api/v1/accounts/verify_credentials", headers=headers(), timeout=15)
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

def get_recent_activity(account_id):
    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    history_limit = since - timedelta(days=7)
    replied_ids = set()
    daily_replies = 0
    daily_posts = 0
    max_id = None

    for _ in range(5):
        params = {"limit": 40, "exclude_reblogs": "true"}
        if max_id: params["max_id"] = max_id
        response = requests.get(f"{API}/api/v1/accounts/{account_id}/statuses", headers=headers(), params=params, timeout=15)
        response.raise_for_status()
        statuses = response.json()
        if not statuses: break
        
        for status in statuses:
            created = datetime.fromisoformat(status["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
            if created < history_limit: break
            
            if status.get("in_reply_to_id"):
                replied_ids.add(str(status["in_reply_to_id"]))
                if created >= since: daily_replies += 1
            else:
                if created >= since: daily_posts += 1
        max_id = statuses[-1]["id"]
    
    return daily_replies, daily_posts, replied_ids

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

def main():
    if not TOKEN: raise RuntimeError("MASTODON_ACCESS_TOKEN is missing.")
    
    account = get_account()
    my_id = str(account["id"])
    print(f"Authenticated: @{account['acct']}")

    daily_replies, daily_posts, replied_ids = get_recent_activity(my_id)
    print(f"Replies today: {daily_replies}/{MAX_REPLIES_DAILY} | Posts today: {daily_posts}/{MAX_POSTS_DAILY}")

    # 1. محاولة الرد (إذا لم نصل للحد)
    if daily_replies < MAX_REPLIES_DAILY:
        for query in SEARCH_TERMS:
            try:
                posts = search_posts(query)
                for post in posts:
                    post_id = str(post["id"])
                    if post_id in replied_ids: continue
                    
                    # نص الرد
                    reply_text = "If you're looking for Android networking tools, I build open-source apps for VPNs and DNS. Check my blog: " + BLOG
                    
                    print(f"Replying to @{post['account'].get('acct')}...")
                    result = publish_reply(post, reply_text)
                    if result:
                        print(f"✅ Replied successfully: {result.get('url')}")
                        daily_replies += 1
                        break # نكتفي برد واحد في كل تشغيل
                if daily_replies >= MAX_REPLIES_DAILY: break
                time.sleep(5) # انتظار بسيط بين البحث
            except Exception as e:
                print(f"Search error: {e}")

    # 2. نشر مقال من المدونة
    if daily_posts < MAX_POSTS_DAILY:
        # هنا يمكنك جلب أحدث مقال من RSS
        # للتبسيط، سنرسل رسالة تعريفية
        post_text = f"Check out my latest Android tools and apps at AntiAtlasDev:\n{BLOG}"
        print("Publishing blog post...")
        result = publish_post(post_text)
        if result:
            print(f"✅ Published successfully: {result.get('url')}")

    print("Finished.")

if __name__ == "__main__":
    main()
