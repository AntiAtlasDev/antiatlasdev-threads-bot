
import os
import json
import subprocess
from datetime import datetime, timezone

import requests
import xml.etree.ElementTree as ET
from atproto import Client

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"

HISTORY_FILE = "bluesky_used_articles.json"
STATE_FILE = "bluesky_daily_state.json"

DAILY_LIMIT = 10


def get_articles():
    try:
        response = requests.get(
            RSS_URL,
            headers={"User-Agent": "AntiAtlasDevBlueskyBot/1.0"},
            timeout=30
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        articles = []

        for item in root.findall("./channel/item"):
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


def load_json(filename, default):
    if not os.path.exists(filename):
        return default

    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        print("Could not read:", filename)
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_daily_state():
    today = datetime.now(timezone.utc).date().isoformat()

    state = load_json(STATE_FILE, {
        "date": today,
        "count": 0
    })

    if state.get("date") != today:
        state = {
            "date": today,
            "count": 0
        }

    return state


def select_article(articles, history):
    for article in articles:
        if article["link"] not in history:
            return article

    print("All articles have already been used.")
    return None


def publish_to_bluesky(text):
    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")

    if not handle or not password:
        raise RuntimeError("Bluesky secrets are missing.")

    client = Client()
    client.login(handle, password)

    response = client.send_post(text=text)

    if not response:
        raise RuntimeError("Bluesky publication failed.")

    print("Published successfully.")
    print("Post URI:", response.uri)


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
                ["git", "commit", "-m", "Update Bluesky publishing history"],
                check=True
            )
            subprocess.run(
                ["git", "push"],
                check=True
            )
            print("Bluesky history saved.")

        elif result.returncode == 0:
            print("No history changes.")

        else:
            raise RuntimeError("Git diff failed.")

    except Exception as error:
        print("History save error:", error)
        raise


if __name__ == "__main__":
    print("AntiAtlasDev Bluesky Bot")

    state = get_daily_state()
    print("Today's publications:", state["count"], "/", DAILY_LIMIT)

    if state["count"] >= DAILY_LIMIT:
        print("Daily limit reached. Stopping.")
        raise SystemExit(0)

    articles = get_articles()

    if not articles:
        raise SystemExit("No articles available.")

    history = load_json(HISTORY_FILE, [])
    article = select_article(articles, history)

    if not article:
        raise SystemExit("No unused articles available.")

    post_text = (
        f"Discover {article['title']} from AntiAtlasDev!\n\n"
        f"Read more:\n{article['link']}"
    )

    print("Selected article:", article["title"])

    # Publish first. Update history only after successful publication.
    publish_to_bluesky(post_text)

    history.append(article["link"])
    state["count"] += 1

    save_json(HISTORY_FILE, history)
    save_json(STATE_FILE, state)

    commit_history()

    print(
        "Daily publications:",
        state["count"],
        "/",
        DAILY_LIMIT
)
  
