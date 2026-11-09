
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
    "Android proxy",
    "Android app problem",
    "VPN not working",
    "DNS problem",
    "GPS problem",
    "Android help",
    "VPN recommendation"
]

TOPICS = [
    "vpn", "wireguard", "openvpn",
    "shadowsocks", "v2ray", "xray",
    "proxy", "dns", "firewall",
    "mock location", "gps spoofing",
    "gps simulator", "location simulator"
]

HELP_PHRASES = [
    "need help", "please help",
    "can someone help", "how do i",
    "how can i", "anyone know",
    "does anyone know", "looking for help",
    "can anyone recommend",
    "any recommendations", "which app",
    "any alternative", "any solution",
    "is there a way", "is it possible",
    "what app", "what should i"
]

PROBLEM_PHRASES = [
    "not working", "doesn't work",
    "does not work", "can't connect",
    "cannot connect", "unable to connect",
    "connection problem", "connection issue",
    "having trouble", "having problems",
    "keeps crashing", "app crashes",
    "error when", "failed to connect",
    "stopped working", "getting an error"
]

PROMO_PHRASES = [
    "sponsored", "affiliate link",
    "promo code", "buy now",
    "limited offer", "giveaway",
    "discount code", "advertisement",
    "introducing our", "meet our new",
    "download now", "get started today",
    "launching our"
]


def clean_text(content):
    content = re.sub(r"<[^>]+>", " ", content)
    content = html.unescape(content)
    content = re.sub(r"https?://\S+", " ", content)
    return re.sub(r"\s+", " ", content).strip().lower()


def matches(text, phrases):
    return [
        p for p in phrases
        if p in text
    ]


def classify(content):
    text = clean_text(content)

    topics = [
        topic for topic in TOPICS
        if re.search(
            r"(?<!\w)" + re.escape(topic) + r"(?!\w)",
            text
        )
    ]

    if not topics:
        return "UNRELATED", 0

    if matches(text, PROMO_PHRASES):
        return "PROMOTIONAL", 0

    help_found = matches(text, HELP_PHRASES)
    problem_found = matches(text, PROBLEM_PHRASES)

    if help_found and problem_found:
        return "HELP_AND_PROBLEM", 8

    if help_found:
        return "HELP_REQUEST", 6

    if problem_found:
        return "TECHNICAL_PROBLEM", 6

    if "?" in text:
        return "GENERAL_QUESTION", 3

    return "GENERAL_DISCUSSION", 1


def main():
    if not TOKEN:
        print("ERROR: Missing access token.")
        return

    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }

    seen = set()
    results = []

    for term in SEARCH_TERMS:
        try:
            response = requests.get(
                f"{API_URL}/api/v2/search",
                headers=headers,
                params={
                    "q": term,
                    "type": "statuses",
                    "limit": 20
                },
                timeout=30
            )

            if response.status_code != 200:
                print("Search failed:", response.status_code)
                continue

            for status in response.json().get("statuses", []):
                post_id = status.get("id")

                if not post_id or post_id in seen:
                    continue

                seen.add(post_id)

                category, score = classify(
                    status.get("content", "")
                )

                results.append({
                    "category": category,
                    "score": score,
                    "user": status.get(
                        "account", {}
                    ).get("acct", "Unknown"),
                    "url": status.get("url", ""),
                    "text": clean_text(
                        status.get("content", "")
                    )
                })

        except requests.RequestException as error:
            print("Network error:", error)

    counts = {}

    for post in results:
        category = post["category"]
        counts[category] = counts.get(category, 0) + 1

    print("\n===== FILTER SUMMARY =====")
    print("Unique posts:", len(seen))

    for category, count in sorted(counts.items()):
        print(f"{category}: {count}")

    candidates = [
        post for post in results
        if post["score"] >= 6
    ]

    candidates.sort(
        key=lambda post: post["score"],
        reverse=True
    )

    print("\n===== TOP 5 CANDIDATES =====")

    for index, post in enumerate(candidates[:5], 1):
        print(f"\n{index}. {post['category']}")
        print("User:", post["user"])
        print("URL:", post["url"])
        print("Text:", post["text"][:220])

    print("\nTest completed. No replies published.")
    print("Total candidates:", len(candidates))


if __name__ == "__main__":
    main()
