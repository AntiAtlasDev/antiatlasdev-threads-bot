
import os
import json
import subprocess
import requests
import xml.etree.ElementTree as ET

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"
HISTORY_FILE = "used_articles.json"


def get_articles():
    try:
        response = requests.get(
            RSS_URL,
            headers={"User-Agent": "AntiAtlasDevThreadsBot/1.0"},
            timeout=30
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        items = root.findall("./channel/item")

        articles = []

        for item in items:
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


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        print("History file could not be read.")
        return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)


def select_article(articles, history):
    unused = [
        article for article in articles
        if article["link"] not in history
    ]

    if not unused:
        print("All articles have been used.")
        print("Starting a new cycle.")
        history.clear()
        unused = articles

    if not unused:
        return None

    article = unused[0]
    history.append(article["link"])

    return article


def prepare_post(article):
    return (
        f"Discover {article['title']} from AntiAtlasDev!\n\n"
        f"Read more:\n{article['link']}"
    )


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
            ["git", "add", HISTORY_FILE],
            check=True
        )

        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"]
        )

        if result.returncode == 1:
            subprocess.run(
                ["git", "commit", "-m", "Update used articles history"],
                check=True
            )
            subprocess.run(
                ["git", "push"],
                check=True
            )
            print("Article history saved to GitHub.")

        elif result.returncode == 0:
            print("No history changes to save.")

        else:
            raise RuntimeError("Git diff failed.")

    except Exception as error:
        print("Git history save error:", error)
        raise


if __name__ == "__main__":
    print("AntiAtlasDev Threads Bot")
    print("Mode: DRY RUN - No publishing")

    articles = get_articles()

    if not articles:
        print("No articles available. Stopping.")
        raise SystemExit(1)

    history = load_history()
    print("Previously used articles:", len(history))

    article = select_article(articles, history)

    if article:
        draft = prepare_post(article)

        print("\nSelected article:")
        print(article["title"])

        print("\nPrepared Threads post:")
        print("------------------------------")
        print(draft)
        print("------------------------------")

        save_history(history)
        commit_history()

        print("\nDry run completed successfully.")
        print("Nothing was published.")
