
import os
import requests
import re
from html import unescape

MASTODON_URL = "https://mastodon.social"
ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")


def main():
    if not ACCESS_TOKEN:
        print("ERROR: MASTODON_ACCESS_TOKEN is missing.")
        return

    print("Searching Mastodon for: Android")

    try:
        response = requests.get(
            f"{MASTODON_URL}/api/v2/search",
            headers={
                "Authorization": f"Bearer {ACCESS_TOKEN}"
            },
            params={
                "q": "Android",
                "type": "statuses",
                "limit": 5
            },
            timeout=30
        )

        print("HTTP Status:", response.status_code)

        if response.status_code != 200:
            print("Search failed:", response.text[:500])
            return

        data = response.json()
        statuses = data.get("statuses", [])

        print("Search successful.")
        print("Posts found:", len(statuses))

        for index, status in enumerate(statuses, 1):
            account = status.get("account", {})
            content = re.sub(
                r"<[^>]+>", " ", status.get("content", "")
            )
            content = unescape(content).strip()

            print(f"\nPost {index}")
            print("User:", account.get("acct", "Unknown"))
            print("URL:", status.get("url", ""))
            print("Text:", content[:300])

    except requests.RequestException as error:
        print("Network error:", str(error))


if __name__ == "__main__":
    main()
  
