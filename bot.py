
import requests
import xml.etree.ElementTree as ET

RSS_URL = "https://antiatlasdev-apps.blogspot.com/feeds/posts/default?alt=rss"


def get_latest_post():
    try:
        response = requests.get(
            RSS_URL,
            headers={"User-Agent": "AntiAtlasDevThreadsBot/1.0"},
            timeout=30
        )

        print("RSS HTTP status:", response.status_code)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        item = root.find("./channel/item")

        if item is None:
            print("No articles found in RSS feed.")
            return None

        title = item.findtext("title", default="Untitled").strip()
        link = item.findtext("link", default="").strip()

        if not link:
            print("Article link is missing.")
            return None

        return {
            "title": title,
            "link": link
        }

    except (requests.RequestException, ET.ParseError) as error:
        print("RSS error:", str(error))
        return None


def prepare_post(article):
    return (
        f"New on AntiAtlasDev: {article['title']}\n\n"
        f"Read more: {article['link']}"
    )


if __name__ == "__main__":
    print("AntiAtlasDev Threads Bot")
    print("Mode: DRY RUN - No publishing")

    article = get_latest_post()

    if article:
        draft = prepare_post(article)

        print("\nArticle found:")
        print(article["title"])

        print("\nPrepared Threads post:")
        print("------------------------------")
        print(draft)
        print("------------------------------")

        print("\nDry run completed successfully.")
        print("Nothing was published.")
    else:
        print("\nCould not prepare a post.")
