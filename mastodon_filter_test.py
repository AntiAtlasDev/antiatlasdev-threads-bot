
import os
import re
import html
import requests

API_URL = "https://mastodon.social"
TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")

SEARCH_TERMS = [
    "Android VPN",
    "WireGuard",
    "OpenVPN",
    "Android DNS",
    "Android GPS",
    "Android firewall",
    "mock location",
    "Android proxy"
]

TOPIC_KEYWORDS = [
    "android", "vpn", "wireguard", "openvpn",
    "shadowsocks", "v2ray", "xray", "proxy",
    "dns", "firewall", "mock location",
    "gps spoofing", "gps simulator",
    "location simulator", "mobile app",
    "android app", "smartphone"
]

INTENT_KEYWORDS = [
    "how do i", "how can i", "how to",
    "anyone know", "does anyone", "can anyone",
    "looking for", "need help", "help me",
    "recommend", "recommendation",
    "suggestion", "what is the best",
    "which app", "any alternative",
    "having trouble", "not working",
    "problem with", "issue with",
    "is there a way", "any solution",
    "does anyone recommend"
]

PROMO_KEYWORDS = [
    "sponsored", "affiliate link", "promo code",
    "buy now", "limited offer", "giveaway",
    "discount code", "advertisement"
]


def clean_text(content):
    content = re.sub(r"<[^>]+>", " ", content)
    content = html.unescape(content)
    return re.sub(r"\s+", " ", content).strip()


def is_candidate(text):
    text = text.lower()

    if any(word in text for word in PROMO_KEYWORDS):
        return False

    has_topic = any(
        word in text for word in TOPIC_KEYWORDS
    )

    has_intent = (
        "?" in text or
        any(word in text for word in INTENT_KEYWORDS)
    )

    return has_topic and has_intent


def main():
    if not TOKEN:
        print("ERROR: Missing access token.")
        return

    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }

    seen_ids = set()
    candidates = []

    for term in SEARCH_TERMS:
        print(f"\nSearching: {term}")

        try:
            response = requests.get(
                f"{API_URL}/api/v2/search",
                headers=headers,
                params={
                    "q": term,
                    "type": "statuses",
                    "limit": 10
                },
                timeout=30
            )

            print("HTTP Status:", response.status_code)

            if response.status_code != 200:
                print("Search failed:", response.text[:300])
                continue

            for status in response.json().get("statuses", []):
                post_id = status.get("id")

                if not post_id or post_id in seen_ids:
                    continue

                seen_ids.add(post_id)

                content = clean_text(
                    status.get("content", "")
                )

                if not is_candidate(content):
                    continue

                account = status.get("account", {})

                candidates.append({
                    "id": post_id,
                    "user": account.get("acct", "Unknown"),
                    "url": status.get("url", ""),
                    "text": content
                })

        except requests.RequestException as error:
            print("Network error:", str(error))

    print("\n========== FILTER RESULTS ==========")
    print("Unique posts checked:", len(seen_ids))
    print("Potential conversations:", len(candidates))

    for index, post in enumerate(candidates, 1):
        print(f"\nCandidate {index}")
        print("User:", post["user"])
        print("URL:", post["url"])
        print("Text:", post["text"][:350])

    print("\nTest completed. No replies were published.")


if __name__ == "__main__":
    main()
