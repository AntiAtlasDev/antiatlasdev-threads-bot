
import os
import json
import html
import subprocess
import requests
import xml.etree.ElementTree as ET

from datetime import datetime, timezone

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"

HISTORY_FILE = "telegram_used_articles.json"
STATE_FILE = "telegram_daily_state.json"

DAILY_LIMIT = 10


def get_articles():
    try:
        response = requests.get(
            RSS_URL,
            headers={"User-Agent": "AntiAtlasDevTelegramBot/1.0"},
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

    if not isinstance(state, dict) or state.get("date") != today:
        state = {
            "date": today,
            "count": 0
        }

    return state


def select_article(articles, history):
    for article in articles:
        if article["link"] not in history:
            return article

    print("No unused articles available.")
    return None


def publish_to_telegram(article):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise RuntimeError("Telegram secrets are missing.")

    title = html.escape(article["title"])

    message = (
        f"📢 <b>{title}</b>\n\n"
        "Discover more from AntiAtlasDev!\n\n"
        f"🔗 {html.escape(article['link'], quote=True)}"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        },
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            "Telegram API error: " + str(result)
        )

    print("Published successfully.")
    print("Telegram message ID:", result["result"]["message_id"])


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
                ["git", "commit", "-m", "Update Telegram publishing history"],
                check=True
            )

            subprocess.run(
                ["git", "pull", "--rebase", "origin", "main"],
                check=True
            )

            subprocess.run(
                ["git", "push"],
                check=True
            )

            print("Telegram history saved to GitHub.")

        elif result.returncode == 0:
            print("No history changes.")

        else:
            raise RuntimeError("Git diff failed.")

    except Exception as error:
        print("History save error:", error)
        raise


if __name__ == "__main__":
    print("AntiAtlasDev Telegram Bot")

    state = get_daily_state()

    print(
        "Today's publications:",
        state["count"],
        "/",
        DAILY_LIMIT
    )

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

    print("Selected article:", article["title"])

    # Publish first; update history only after successful publication.
    publish_to_telegram(article)

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
  
