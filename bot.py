
import os
import json
import time
import random
import requests
import xml.etree.ElementTree as ET

from datetime import datetime, timezone


# ==========================================
# CONFIGURATION
# ==========================================

RSS_URL = (
    "https://antiatlasdev-apps.blogspot.com/"
    "feeds/posts/default?alt=rss"
)

THREADS_API = "https://graph.threads.com/v1.0"

HISTORY_FILE = "threads_used_articles.json"
STATE_FILE = "threads_daily_state.json"
REPLIED_FILE = "threads_replied_posts.json"

ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
USER_ID = os.environ.get("THREADS_USER_ID")

MY_USERNAME = "antiatlasdev_apps"

MAX_POSTS_DAILY = 3
MAX_REPLIES_DAILY = 5

MAX_REPLIES_PER_RUN = 1

MAX_POST_AGE_HOURS = 168

SEARCH_QUERIES = [
    "VPN Android",
    "Android network",
    "DNS Android",
    "Mock location",
    "Image resizer Android",
    "Android apps"
]

SEARCH_FIELDS = (
    "id,text,username,timestamp,permalink,"
    "media_type,has_replies,is_quote_post,is_reply"
)


# ==========================================
# JSON FUNCTIONS
# ==========================================

def load_json(filename, default):

    if not os.path.exists(filename):
        return default

    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"JSON error ({filename}):", repr(e))
        return default


def save_json(filename, data):

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


# ==========================================
# DAILY STATE
# ==========================================

def get_daily_state():

    today = datetime.now(timezone.utc).date().isoformat()

    default = {
        "date": today,
        "posts_count": 0,
        "replies_count": 0
    }

    state = load_json(STATE_FILE, default)

    if state.get("date") != today:
        state = default.copy()

    state.setdefault("posts_count", 0)
    state.setdefault("replies_count", 0)

    return state


# ==========================================
# RSS ARTICLES
# ==========================================

def get_articles():

    try:

        response = requests.get(
            RSS_URL,
            timeout=30
        )

        response.raise_for_status()

        root = ET.fromstring(response.content)

        articles = []

        for item in root.findall("./channel/item"):

            title = item.findtext(
                "title",
                default=""
            ).strip()

            link = item.findtext(
                "link",
                default=""
            ).strip()

            if title and link:

                title = (
                    title.replace("AntiAtlasDev", "")
                    .replace("Anti Atlas Dev", "")
                    .strip()
                )

                articles.append({
                    "title": title,
                    "link": link
                })

        print("RSS articles:", len(articles))

        return articles

    except Exception as e:

        print("RSS ERROR:", repr(e))

        return []


# ==========================================
# OFFICIAL THREADS KEYWORD SEARCH
# ==========================================

def search_threads(query):

    search_url = f"{THREADS_API}/keyword_search"

    params = {
        "q": query,
        "search_type": "RECENT",
        "fields": SEARCH_FIELDS,
        "access_token": ACCESS_TOKEN
    }

    try:

        response = requests.get(
            search_url,
            params=params,
            timeout=30
        )

        print(
            f"Search [{query}] HTTP:",
            response.status_code
        )

        if not response.ok:

            print("SEARCH ERROR:")
            print(response.text[:1500])

            return []

        data = response.json()

        results = data.get("data", [])

        print(
            f"Results found for [{query}]:",
            len(results)
        )

        return results

    except Exception as e:

        print("SEARCH ERROR:", repr(e))

        return []


# ==========================================
# NORMALIZE POSTS
# ==========================================

def normalize_post(post, query):

    post_id = post.get("id")
    username = post.get("username", "")
    text = post.get("text", "")
    timestamp = post.get("timestamp", "")

    if not post_id or not username:
        return None

    if not isinstance(text, str):
        text = ""

    try:

        if isinstance(timestamp, str):

            timestamp = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            ).timestamp()

        elif not isinstance(timestamp, (int, float)):

            timestamp = 0

    except Exception:

        timestamp = 0

    url = post.get("permalink", "")

    return {
        "id": str(post_id),
        "username": username,
        "text": text,
        "timestamp": timestamp,
        "url": url,
        "query": query
    }


# ==========================================
# RELEVANCE FILTER
# ==========================================

def is_relevant(post):

    text = post["text"].lower()

    keywords = [
        "vpn",
        "android",
        "dns",
        "mock location",
        "fake gps",
        "image resizer",
        "image resize",
        "network",
        "wireguard",
        "openvpn",
        "proxy",
        "internet connection"
    ]

    return any(
        keyword in text
        for keyword in keywords
    )


# ==========================================
# POST AGE FILTER
# ==========================================

def is_recent(post):

    timestamp = post.get("timestamp", 0)

    if not timestamp:
        return False

    now = datetime.now(timezone.utc).timestamp()

    age = now - timestamp

    max_age = MAX_POST_AGE_HOURS * 3600

    return 0 <= age <= max_age


# ==========================================
# GENERATE CONTEXTUAL REPLY
# ==========================================

def generate_reply(post):

    text = post["text"].lower()

    if "mock location" in text or "fake gps" in text:

        replies = [
            "For Android mock-location testing, make sure the app and developer location settings are configured correctly.",
            "If you're testing GPS behavior on Android, checking location permissions and accuracy settings can help."
        ]

    elif "dns" in text:

        replies = [
            "For Android DNS troubleshooting, checking Private DNS settings and testing the resolver can help identify the issue.",
            "DNS problems on Android can sometimes come from the selected resolver or network configuration."
        ]

    elif "vpn" in text or "wireguard" in text or "openvpn" in text:

        replies = [
            "When troubleshooting an Android VPN, checking the server configuration, DNS settings and connection logs is a good starting point.",
            "For VPN issues on Android, testing the server and DNS configuration separately can help narrow down the problem."
        ]

    elif "image" in text:

        replies = [
            "For Android image resizing, checking the output dimensions and compression quality helps preserve image clarity.",
            "When resizing images, the right balance between dimensions and compression quality makes a big difference."
        ]

    else:

        replies = [
            "For Android troubleshooting, checking permissions and network settings is often a useful starting point."
        ]

    return random.choice(replies)


# ==========================================
# PUBLISH REPLY
# ==========================================

def publish_reply(post, reply_text):

    if not ACCESS_TOKEN or not USER_ID:

        print("ERROR: Missing Threads credentials.")

        return False

    print(
        f"Preparing reply to @{post['username']}"
    )

    create_url = f"{THREADS_API}/{USER_ID}/threads"

    payload = {
        "media_type": "TEXT",
        "text": reply_text,
        "reply_to_id": post["id"],
        "access_token": ACCESS_TOKEN
    }

    try:

        response = requests.post(
            create_url,
            data=payload,
            timeout=30
        )

        print(
            "Reply creation HTTP:",
            response.status_code
        )

        if not response.ok:

            print("REPLY CREATION ERROR:")
            print(response.text[:2000])

            return False

        creation_id = response.json().get("id")

        if not creation_id:

            print("ERROR: Missing reply creation ID.")

            return False

        time.sleep(5)

        publish_url = (
            f"{THREADS_API}/"
            f"{USER_ID}/threads_publish"
        )

        publish_response = requests.post(
            publish_url,
            data={
                "creation_id": creation_id,
                "access_token": ACCESS_TOKEN
            },
            timeout=30
        )

        print(
            "Reply publishing HTTP:",
            publish_response.status_code
        )

        if publish_response.ok:

            print(
                f"SUCCESS: Replied to @{post['username']}"
            )

            print("Post:", post["url"])

            return True

        print("REPLY PUBLISH ERROR:")
        print(publish_response.text[:2000])

        return False

    except Exception as e:

        print("REPLY ERROR:", repr(e))

        return False


# ==========================================
# SEARCH AND REPLY WITH DIAGNOSTICS
# ==========================================

def search_and_reply():

    print("\n========== THREADS KEYWORD SEARCH ==========")

    if not ACCESS_TOKEN or not USER_ID:

        print("Missing Threads credentials.")

        return 0

    replied_history = load_json(
        REPLIED_FILE,
        []
    )

    replied_set = set(replied_history)

    queries = SEARCH_QUERIES.copy()

    random.shuffle(queries)

    candidates = {}

    for query in queries:

        print("\nSearching:", query)

        results = search_threads(query)

        for raw_post in results:

            post = normalize_post(
                raw_post,
                query
            )

            if not post:

                print("[SKIP] Invalid post data:")
                print(json.dumps(
                    raw_post,
                    ensure_ascii=False
                )[:1500])

                continue

            username = (
                post["username"]
                .lower()
                .lstrip("@")
            )

            text = post["text"]
            timestamp = post["timestamp"]

            print("\n--------------------------------")
            print("Username:", username)
            print("Post ID:", post["id"])
            print("Text:", text[:300])
            print("Timestamp:", timestamp)
            print("URL:", post["url"])

            # 1. Ignore own account

            if username == MY_USERNAME.lower():

                print("[SKIP] Own account")

                continue

            # 2. Ignore already replied posts

            if post["id"] in replied_set:

                print("[SKIP] Already replied")

                continue

            # 3. Check timestamp

            if not timestamp:

                print("[SKIP] Missing timestamp")

                continue

            age_hours = (
                datetime.now(timezone.utc).timestamp()
                - timestamp
            ) / 3600

            print(
                "Post age:",
                round(age_hours, 2),
                "hours"
            )

            if not is_recent(post):

                print(
                    "[SKIP] Post is outside "
                    "the allowed age"
                )

                continue

            # 4. Check relevance

            if not is_relevant(post):

                print(
                    "[SKIP] No relevant keyword "
                    "in post text"
                )

                continue

            print("[ELIGIBLE] Post passed all filters")

            candidates[post["id"]] = post

        time.sleep(3)

    print(
        "\nEligible posts:",
        len(candidates)
    )

    if not candidates:

        print("No new eligible posts found.")

        return 0

    ordered = sorted(
        candidates.values(),
        key=lambda p: p["timestamp"],
        reverse=True
    )

    replies_made = 0

    for post in ordered:

        if replies_made >= MAX_REPLIES_PER_RUN:
            break

        print("\nCandidate:")
        print("User:", post["username"])
        print("Text:", post["text"][:300])
        print("URL:", post["url"])

        reply_text = generate_reply(post)

        print("Reply text:", reply_text)

        if publish_reply(post, reply_text):

            replied_history.append(post["id"])

            replied_set.add(post["id"])

            save_json(
                REPLIED_FILE,
                replied_history[-5000:]
            )

            replies_made += 1

        else:

            print(
                "[ERROR] Reply was not published."
            )

        time.sleep(15)

    print(
        "\nReplies successfully published:",
        replies_made
    )

    return replies_made


# ==========================================
# PUBLISH NORMAL POST
# ==========================================

def publish_post(text):

    if not ACCESS_TOKEN or not USER_ID:

        print("Missing Threads credentials.")

        return False

    print("\nPublishing blog post...")

    create_url = f"{THREADS_API}/{USER_ID}/threads"

    payload = {
        "media_type": "TEXT",
        "text": text,
        "access_token": ACCESS_TOKEN
    }

    try:

        response = requests.post(
            create_url,
            data=payload,
            timeout=30
        )

        if not response.ok:

            print("POST CREATE ERROR:")
            print(response.text[:2000])

            return False

        creation_id = response.json().get("id")

        if not creation_id:

            print("Missing creation ID.")

            return False

        time.sleep(5)

        publish_url = (
            f"{THREADS_API}/"
            f"{USER_ID}/threads_publish"
        )

        publish_response = requests.post(
            publish_url,
            data={
                "creation_id": creation_id,
                "access_token": ACCESS_TOKEN
            },
            timeout=30
        )

        if publish_response.ok:

            print("Blog post published successfully.")

            return True

        print("POST PUBLISH ERROR:")
        print(publish_response.text[:2000])

        return False

    except Exception as e:

        print("POST ERROR:", repr(e))

        return False


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    print("================================")
    print("AntiAtlasDev Threads Bot")
    print("================================")

    state = get_daily_state()

    # 1. SEARCH AND REPLY

    if state["replies_count"] < MAX_REPLIES_DAILY:

        new_replies = search_and_reply()

        state["replies_count"] += new_replies

    else:

        print("Daily reply limit reached.")

    # 2. PUBLISH BLOG ARTICLES

    if state["posts_count"] < MAX_POSTS_DAILY:

        articles = get_articles()

        history = load_json(
            HISTORY_FILE,
            []
        )

        article = next(
            (
                a for a in articles
                if a["link"] not in history
            ),
            None
        )

        if article:

            draft = (
                f"📱 New App: {article['title']}\n\n"
                f"Read more here:\n"
                f"{article['link']}\n\n"
                "#Android #AppDevelopment"
            )

            if publish_post(draft):

                history.append(article["link"])

                state["posts_count"] += 1

                save_json(
                    HISTORY_FILE,
                    history
                )

        elif articles:

            print(
                "No new articles. "
                "Recycling an old one."
            )

            recycled = random.choice(articles)

            draft = (
                f"🔄 Flashback: {recycled['title']}\n\n"
                f"Read more here:\n"
                f"{recycled['link']}\n\n"
                "#Android #AppDevelopment"
            )

            if publish_post(draft):

                state["posts_count"] += 1

        else:

            print("No RSS articles available.")

    else:

        print("Daily post limit reached.")

    # 3. SAVE DAILY STATE

    save_json(
        STATE_FILE,
        state
    )

    print("\n================================")
    print("Finished.")
    print("Posts:", state["posts_count"])
    print("Replies:", state["replies_count"])
    print("================================")
    
