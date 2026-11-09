
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

TOPICS = [
    "android", "vpn", "wireguard", "openvpn",
    "shadowsocks", "v2ray", "xray", "proxy",
    "dns", "firewall", "mock location",
    "gps spoofing", "gps simulator",
    "location simulator", "android app",
    "mobile app"
]

HELP_REQUESTS = [
    "how do i", "how can i", "how to",
    "can someone help", "could someone help",
    "need help", "please help",
    "anyone know how", "does anyone know",
    "looking for an app", "looking for a vpn",
    "looking for an alternative",
    "can anyone recommend", "any recommendations",
    "which app should i", "what app can i",
    "not working", "doesn't work",
    "does not work", "having trouble",
    "having problems", "cannot connect",
    "can't connect", "connection problem",
    "is there a way to"
]

PROMO_PHRASES = [
    "sponsored", "affiliate link", "promo code",
    "buy now", "limited offer", "giveaway",
    "discount code", "advertisement",
    "meet our new", "introducing",
    "check out our", "download now",
    "available now", "new release",
    "launching today", "get started today"
]


def clean_text(content):
    content = re.sub(r"<[^>]+>", " ", content)
    content = html.unescape(content)
    content = re.sub(r"https?://\S+", " ", content)
    return re.sub(r"\s+", " ", content).strip().lower()


def contains_topic(text):
    return any(
        re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text)
        for word in TOPICS
    )


def is_candidate(text):
    text = clean_text(text)

    if any(phrase in text for phrase in PROMO_PHRASES):
        return False

    if not contains_topic(text):
        return False

    # A clear help request is required.
    if not any(phrase in text for phrase in HELP_REQUESTS):
        return False

    return True


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

                raw_content = status.get("content", "")

                if not is_candidate(raw_content):
                    continue

                account = status.get("account", {})

                candidates.append({
                    "id": post_id,
                    "user": account.get("acct", "Unknown"),
                    "url": status.get("url", ""),
                    "text": clean_text(raw_content)
                })

        except requests.RequestException as error:
            print("Network error:", str(error))

    print("\n========== FILTER RESULTS ==========")
    print("Unique posts checked:", len(seen_ids))
    print("Potential help requests:", len(candidates))

    for index, post in enumerate(candidates, 1):
        print(f"\nCandidate {index}")
        print("User:", post["user"])
        print("URL:", post["url"])
        print("Text:", post["text"][:400])

    print("\nTest completed. No replies were published.")


if __name__ == "__main__":
    main()
