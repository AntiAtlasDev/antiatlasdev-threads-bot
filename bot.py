
import os
import re
import json
import time
import random
import requests

import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from urllib.parse import quote


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

USER_AGENT = "facebookexternalhit/1.1"

SCRIPT_PATTERN = re.compile(
    r'<script[^>]*type="application/json"[^>]*>'
    r'(.*?)</script>',
    re.S
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
# THREADS PUBLIC SEARCH PAGE PARSER
# ==========================================

def collect_posts(node, posts, depth=0):

    if depth > 35 or node is None:
        return

    if isinstance(node, list):

        for item in node:
            collect_posts(item, posts, depth + 1)

    elif isinstance(node, dict):

        code = node.get("code")
        pk = node.get("pk")

        caption = node.get("caption")

        if (
            isinstance(code, str)
            and pk is not None
            and caption is not None
            and (
                "taken_at" in node
                or "like_count" in node
            )
        ):

            existing = posts.get(code)

            if (
                existing is None
                or len(json.dumps(node))
                > len(json.dumps(existing))
            ):
                posts[code] = node

        for value in node.values():
            collect_posts(value, posts, depth + 1)


def fetch_search_view(query, view):

    url = (
        "https://www.threads.com/search"
        f"?q={quote(query)}"
        f"&serp_type={view}"
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        print(
            f"Search page [{view}] HTTP:",
            response.status_code
        )

        response.raise_for_status()

        posts = {}

        for block in SCRIPT_PATTERN.findall(response.text):

            try:

                data = json.loads(block)

                collect_posts(data, posts)

            except (ValueError, TypeError):
                continue

        print(
            f"Search [{query}] [{view}]:",
            len(posts),
            "posts"
        )

        return list(posts.values())

    except requests.exceptions.RequestException as e:

        print("Search page request error:", repr(e))

        return []


def fetch_public_posts(query):

    collected = {}

    for view in ("recent", "default"):

        results = fetch_search_view(
            query,
            view
        )

        for post in results:

            code = post.get("code")

            if code:
                collected[code] = post

        time.sleep(2)

    return list(collected.values())


# ==========================================
# NORMALIZE PUBLIC POSTS
# ==========================================

def normalize_post(post, query):

    user = post.get("user") or {}

    caption = post.get("caption") or {}

    username = user.get("username", "")

    text = caption.get("text", "")

    post_id = post.get("pk")

    code = post.get("code")

    timestamp = post.get("taken_at", 0)

    if isinstance(post_id, int):
        post_id = str(post_id)

    if not isinstance(post_id, str):
        return None

    if not username or not code:
        return None

    if not isinstance(text, str):
        text = ""

    if not isinstance(timestamp, (int, float)):
        timestamp = 0

    return {
        "id": post_id,
        "code": code,
        "username": username,
        "text": text,
        "timestamp": timestamp,
        "url": (
            f"https://www.threads.com/"
            f"@{username}/post/{code}"
        ),
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

        if response.status_code != 200:

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

        publish_payload = {
            "creation_id": creation_id,
            "access_token": ACCESS_TOKEN
        }

        publish_response = requests.post(
            publish_url,
            data=publish_payload,
            timeout=30
        )

        print(
            "Reply publishing HTTP:",
            publish_response.status_code
        )

        if publish_response.status_code == 200:

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
# SEARCH AND REPLY
# ==========================================

def search_and_reply():

    print("\n========== PUBLIC THREADS SEARCH ==========")

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

        results = fetch_public_posts(query)

        for raw_post in results:

            post = normalize_post(
                raw_post,
                query
            )

            if not post:
                continue

            username = post["username"].lower().lstrip("@")

            if username == MY_USERNAME.lower():
                continue

            if post["id"] in replied_set:
                continue

            if not is_recent(post):
                continue

            if not is_relevant(post):
                continue

            candidates[post["id"]] = post

        time.sleep(3)

    print(
        "\nEligible posts:",
        len(candidates)
    )

    if not candidates:

        print(
            "No new eligible public posts found."
        )

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
                "Reply was not published. "
                "Post will remain eligible for retry."
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

        if response.status_code != 200:

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

        if publish_response.status_code == 200:

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
