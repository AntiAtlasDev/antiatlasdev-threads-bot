
import os
import requests
import xml.etree.ElementTree as ET

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"


def get_articles():
    try:
        response = requests.get(
            RSS_URL,
            headers={"User-Agent": "AntiAtlasDevThreadsBot/1.0"},
            timeout=30
        )

        print("RSS HTTP status:", response.status_code)
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

        return articles

    except (requests.RequestException, ET.ParseError) as error:
        print("RSS error:", str(error))
        return []


def select_article(articles):
    if not articles:
        return None

    run_number = int(os.environ.get("GITHUB_RUN_NUMBER", "1"))

    index = (run_number - 1) % len(articles)

    print("Total articles:", len(articles))
    print("Selected article number:", index + 1)

    return articles[index]


def prepare_post(article):
    return (
        f"Discover {article['title']} from AntiAtlasDev!\n\n"
        f"Read more:\n{article['link']}"
    )


if __name__ == "__main__":
    print("AntiAtlasDev Threads Bot")
    print("Mode: DRY RUN - No publishing")

    articles = get_articles()
    article = select_article(articles)

    if article:
        draft = prepare_post(article)

        print("\nSelected article:")
        print(article["title"])

        print("\nPrepared Threads post:")
        print("------------------------------")
        print(draft)
        print("------------------------------")

        print("\nDry run completed successfully.")
        print("Nothing was published.")
    else:
        print("No articles available.")
