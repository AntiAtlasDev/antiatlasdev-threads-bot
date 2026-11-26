import os
import json
import time
import random
import subprocess
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ==============================
# CONFIGURATION
# ==============================

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"

HISTORY_FILE = "threads_used_articles.json"
STATE_FILE = "threads_daily_state.json"

ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
USER_ID = os.environ.get("THREADS_USER_ID")

MAX_POSTS_DAILY = 3
MAX_REPLIES_DAILY = 5

SEARCH_QUERIES = [
    "VPN",
    "Android",
    "DNS",
    "Mock location",
    "Image resizer"
]

THREADS_API = "https://graph.threads.com/v1.0"


# ==============================
# JSON FUNCTIONS
# ==============================

def load_json(filename, default):
    if not os.path.exists(filename):
        return default

    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"JSON load error ({filename}):", e)
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==============================
# RSS ARTICLES
# ==============================

def get_articles():
    try:
        response = requests.get(RSS_URL, timeout=30)
        response.raise_for_status()

        root = ET.fromstring(response.content)

        articles = []

        for item in root.findall("./channel/item"):
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()

            if title and link:
                clean_title = (
                    title.replace("AntiAtlasDev", "")
                    .replace("Anti Atlas Dev", "")
                    .strip()
                )

                articles.append({
                    "title": clean_title,
                    "link": link
                })

        print(f"RSS articles found: {len(articles)}")

        return articles

    except Exception as e:
        print("RSS error:", repr(e))
        return []


# ==============================
# DAILY STATE
# ==============================

def get_daily_state():
    today = datetime.now(timezone.utc).date().isoformat()

    default_state = {
        "date": today,
        "posts_count": 0,
        "replies_count": 0
    }

    state = load_json(STATE_FILE, default_state)

    if state.get("date") != today:
        state = default_state.copy()

    state.setdefault("posts_count", 0)
    state.setdefault("replies_count", 0)

    return state


# ==============================
# GITHUB HISTORY
# ==============================

def commit_history():
    try:
        subprocess.run(
            ["git", "config", "user.name", "AntiAtlasDev Bot"],
            check=True
        )

        subprocess.run(
            ["git", "config", "user.email", "bot@antiatlasdev.com"],
            check=True
        )

        subprocess.run(
            ["git", "add", HISTORY_FILE, STATE_FILE],
            check=True
        )

        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"]
        )

        if result.returncode == 1:
            subprocess.run(
                ["git", "commit", "-m", "Update Threads history"],
                check=True
            )

            subprocess.run(
                ["git", "push", "origin", "main"],
                check=True
            )

            print("History successfully saved to GitHub.")

        else:
            print("No history changes to save.")

    except Exception as e:
        print("Git history error:", repr(e))


# ==============================
# THREADS SEARCH DIAGNOSTIC
# ==============================

def search_and_reply():

    print("\n========== THREADS SEARCH DIAGNOSTIC ==========")

    if not ACCESS_TOKEN or not USER_ID:
        print("ERROR: Missing Threads credentials.")
        print("Check THREADS_ACCESS_TOKEN and THREADS_USER_ID.")
        return 0

    search_url = f"{THREADS_API}/keyword_search"

    random_queries = SEARCH_QUERIES.copy()
    random.shuffle(random_queries)

    for query in random_queries:

        print("\n----------------------------------------")
        print("Searching for:", query)

        params = {
            "q": query,
            "search_type": "RECENT",
            "fields": (
                "id,text,media_type,permalink,timestamp,"
                "username,has_replies,is_quote_post,is_reply"
            ),
            "limit": 25,
            "access_token": ACCESS_TOKEN
        }

        try:
            response = requests.get(
                search_url,
                params=params,
                timeout=30
            )

            print("HTTP Status:", response.status_code)

            try:
                result = response.json()
            except ValueError:
                print("Invalid JSON response:")
                print(response.text[:2000])
                continue

            if response.status_code != 200:
                print("META API ERROR:")

                print(json.dumps(
                    result,
                    indent=2,
                    ensure_ascii=False
                ))

                continue

            posts = result.get("data", [])

            print("Results found:", len(posts))

            if not posts:
                print("No posts returned for this keyword.")

                print("API response:")
                print(json.dumps(
                    result,
                    indent=2,
                    ensure_ascii=False
                ))

                continue

            for index, post in enumerate(posts[:10], start=1):

                print(f"\nPOST #{index}")

                print("ID:", post.get("id"))
                print("Username:", post.get("username"))
                print("Text:", post.get("text", "")[:300])
                print("Media type:", post.get("media_type"))
                print("Permalink:", post.get("permalink"))
                print("Is reply:", post.get("is_reply"))

            paging = result.get("paging")

            if paging:
                print("\nPagination:")
                print(json.dumps(
                    paging,
                    indent=2,
                    ensure_ascii=False
                ))

        except requests.exceptions.Timeout:
            print("ERROR: Threads API request timed out.")

        except requests.exceptions.RequestException as e:
            print("NETWORK ERROR:", repr(e))

        except Exception as e:
            print("UNEXPECTED ERROR:", repr(e))

    print("\n========== DIAGNOSTIC FINISHED ==========")

    # Diagnostic mode: no replies are published.
    return 0


# ==============================
# PUBLISH THREADS POST
# ==============================

def publish_post(text):

    if not ACCESS_TOKEN or not USER_ID:
        print("ERROR: Missing Threads credentials.")
        return False

    print("\nPublishing post...")

    create_url = f"{THREADS_API}/{USER_ID}/threads"

    create_payload = {
        "media_type": "TEXT",
        "text": text,
        "access_token": ACCESS_TOKEN
    }

    try:
        response = requests.post(
            create_url,
            data=create_payload,
            timeout=30
        )

        if response.status_code != 200:
            print("Create post error:", response.status_code)
            print(response.text[:2000])
            return False

        creation_id = response.json().get("id")

        if not creation_id:
            print("ERROR: No creation ID returned.")
            print(response.text[:1000])
            return False

        print("Post container created:", creation_id)

        time.sleep(5)

        publish_url = f"{THREADS_API}/{USER_ID}/threads_publish"

        publish_payload = {
            "creation_id": creation_id,
            "access_token": ACCESS_TOKEN
        }

        publish_response = requests.post(
            publish_url,
            data=publish_payload,
            timeout=30
        )

        if publish_response.status_code == 200:
            print("Published post successfully.")
            return True

        print("Publish error:", publish_response.status_code)
        print(publish_response.text[:2000])

        return False

    except Exception as e:
        print("Publishing error:", repr(e))
        return False


# ==============================
# MAIN
# ==============================

if __name__ == "__main__":

    print("================================")
    print("AntiAtlasDev Threads Bot")
    print("================================")

    state = get_daily_state()

    # 1. SEARCH DIAGNOSTIC
    # Does not publish replies.

    if state["replies_count"] < MAX_REPLIES_DAILY:

        search_and_reply()

    else:
        print("Daily reply limit reached.")

    # 2. PUBLISH BLOG ARTICLES

    if state["posts_count"] < MAX_POSTS_DAILY:

        articles = get_articles()

        history = load_json(HISTORY_FILE, [])

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
                f"Read more here:\n{article['link']}\n\n"
                "#Android #AppDevelopment"
            )

            if publish_post(draft):

                history.append(article["link"])

                save_json(HISTORY_FILE, history)

                state["posts_count"] += 1

        elif articles:

            print("No new articles. Recycling an old one (Flashback)...")

            recycled = random.choice(articles)

            draft = (
                f"🔄 Flashback: {recycled['title']}\n\n"
                f"Read more here:\n{recycled['link']}\n\n"
                "#Android #AppDevelopment"
            )

            if publish_post(draft):
                state["posts_count"] += 1

        else:
            print("No RSS articles available.")

    else:
        print("Daily post limit reached.")

    # 3. SAVE STATE

    save_json(STATE_FILE, state)

    # 4. SAVE HISTORY TO GITHUB

    commit_history()

    print("\n================================")
    print("Finished.")
    print("Posts:", state["posts_count"])
    print("Replies:", state["replies_count"])
    print("================================")
              
