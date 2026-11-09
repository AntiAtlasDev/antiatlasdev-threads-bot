import os
import json
import subprocess
import random
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser

import requests
import xml.etree.ElementTree as ET

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
API_URL = "https://dev.to/api/articles"

HISTORY_FILE = "devto_used_articles.json"
STATE_FILE = "devto_daily_state.json"

# نشر مقال واحد يومياً هو الخيار الأفضل والأكثر أماناً في Dev.to
DAILY_LIMIT = 1


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def clean_description(value):
    parser = TextExtractor()
    parser.feed(unescape(value or ""))
    return " ".join(" ".join(parser.parts).split())[:450]


def get_articles():
    response = requests.get(RSS_URL, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    articles = []

    for item in root.findall("./channel/item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        description = clean_description(
            item.findtext("description", "")
        )

        if title and link:
            articles.append({
                "title": title[:200],
                "link": link,
                "description": description
            })

    print("Total articles:", len(articles))
    return articles


def load_json(filename, default):
    if not os.path.exists(filename):
        return default

    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def publish(article):
    api_key = os.environ.get("DEVTO_API_KEY")

    if not api_key:
        raise RuntimeError("DEVTO_API_KEY is missing.")

    description = article["description"] or (
        "Discover this Android app and development article from AntiAtlasDev."
    )

    # إضافة مقدمة تقنية قصيرة لتجنب اعتبار المقال "محتوى غير مكتمل"
    intros = [
        "In this article, we explore a practical Android development topic. ",
        "Android development is constantly evolving. Here is a quick look at a useful tool. ",
        "If you're interested in Android utilities and networking, this is for you. "
    ]
    intro_text = random.choice(intros)

    body = (
        f"{intro_text}\n\n"
        f"{description}\n\n"
        f"### Read the full original article:\n"
        f"[{article['title']}]({article['link']})\n\n"
        "---\n"
        "**About the Author:** I'm an independent Android developer at AntiAtlasDev, "
        "building networking tools, VPN clients, and utilities. "
        "Follow me for more Android development updates!"
    )

    payload = {
        "article": {
            "title": article["title"],
            "body_markdown": body,
            "published": True,
            "canonical_url": article["link"],
            "description": description[:160],
            # تحسين الوسوم
            "tags": ["android", "mobile", "programming", "opensource", "appdev"]
        }
    }

    response = requests.post(
        API_URL,
        headers={
            "api-key": api_key,
            "Accept": "application/vnd.forem.api-v1+json",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=30
    )

    if response.status_code != 201:
        raise RuntimeError(
            f"DEV.to error {response.status_code}: {response.text[:1000]}"
        )

    result = response.json()
    print("Published successfully:", result.get("url"))


def commit_history():
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

    result = subprocess.run(["git", "diff", "--cached", "--quiet"])

    if result.returncode == 1:
        subprocess.run(
            ["git", "commit", "-m", "Update DEV.to history"],
            check=True
        )
        subprocess.run(["git", "push"], check=True)


if __name__ == "__main__":
    print("AntiAtlasDev DEV.to Bot")

    today = datetime.now(timezone.utc).date().isoformat()

    # استخدام .get() لتجنب أخطاء الملفات القديمة
    state = load_json(STATE_FILE, {
        "date": today,
        "count": 0
    })

    if state.get("date") != today:
        state = {"date": today, "count": 0}
    elif "count" not in state:
        state["count"] = 0

    current_count = state.get("count", 0)
    print("Today's publications:", current_count, "/", DAILY_LIMIT)

    if current_count >= DAILY_LIMIT:
        print("Daily limit reached.")
        raise SystemExit(0)

    articles = get_articles()
    history = load_json(HISTORY_FILE, [])

    article = next(
        (a for a in articles if a["link"] not in history),
        None
    )

    if not article:
        print("No unused articles.")
        raise SystemExit(0)

    print("Selected:", article["title"])

    publish(article)

    history.append(article["link"])
    state["count"] = current_count + 1

    save_json(HISTORY_FILE, history)
    save_json(STATE_FILE, state)
    commit_history()

    print("Daily publications:", state.get("count", 0), "/", DAILY_LIMIT)
