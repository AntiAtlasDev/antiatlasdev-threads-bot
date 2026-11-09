
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
    "android", "vpn", "wireguard", "openvpn",
    "shadowsocks", "v2ray", "xray", "proxy",
    "dns", "firewall", "mock location",
    "gps spoofing", "gps simulator",
    "location simulator", "mobile app",
    "android app", "android apps"
]

HELP_PHRASES = [
    "help", "how do", "how can",
    "anyone know", "does anyone know",
    "can someone", "could someone",
    "looking for", "recommend",
    "recommendation", "alternative",
    "any solution", "is there a way",
    "is it possible", "why does",
    "why is", "what should i",
    "what app", "which app",
    "need advice", "any advice"
]

PROBLEM_PHRASES = [
    "not working", "doesn't work",
    "does not work", "can't connect",
    "cannot connect", "unable to connect",
    "connection problem", "connection issue",
    "having trouble", "having problems",
    "keeps crashing", "app crashes",
    "error", "failed", "failure",
    "bug", "broken", "problem",
    "issue", "crash", "stopped working"
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
    content = re.sub(r"\s+", " ", content)
    return content.strip().lower()


def classify_post(content):
    text = clean_text(content)

    topics = [
        item for item in TOPICS
        if re.search(
            r"(?<!\w)" + re.escape(item) + r"(?!\w)",
            text
        )
    ]

    help_matches = [
        phrase for phrase in HELP_PHRASES
        if phrase in text
    ]

    problem_matches = [
        phrase for phrase in PROBLEM_PHRASES
        if phrase in text
    ]

    promo_matches = [
        phrase for phrase in PROMO_PHRASES
        if phrase in text
    ]

    if promo_matches:
        category = "PROMOTIONAL"
        score = 0

    elif not topics:
        category = "UNRELATED"
        score = 0

    elif help_matches and problem_matches:
        category = "HELP_AND_PROBLEM"
        score = 8

    elif help_matches:
        category = "HELP_REQUEST"
        score = 6

    elif problem_matches:
        category = "TECHNICAL_PROBLEM"
        score = 6

    elif "?" in text:
        category = "GENERAL_QUESTION"
        score = 3

    else:
        category = "GENERAL_DISCUSSION"
        score = 1

    return {
        "category": category,
        "score": score,
        "topics": topics[:5],
        "help": help_matches[:4],
        "problems": problem_matches[:4],
        "promo": promo_matches[:3],
        "text": text
    }


def main():
    if not TOKEN:
        print("ERROR: Missing access token.")
        return

    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }

    seen_ids = set()
    results = []

    for term in SEARCH_TERMS:
        print("\nSearching:", term)

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

            print("HTTP Status:", response.status_code)

            if response.status_code != 200:
                print("Search failed:", response.text[:200])
                continue

            statuses = response.json().get(
                "statuses", []
            )

            for status in statuses:
                post_id = status.get("id")

                if not post_id or post_id in seen_ids:
                    continue

                seen_ids.add(post_id)

                raw_content = status.get("content", "")
                classification = classify_post(raw_content)

                account = status.get("account", {})

                results.append({
                    "id": post_id,
                    "user": account.get("acct", "Unknown"),
                    "url": status.get("url", ""),
                    **classification
                })

        except requests.RequestException as error:
            print("Network error:", str(error))

    categories = {}

    for post in results:
        category = post["category"]
        categories[category] = categories.get(category, 0) + 1

    print("\n========== DIAGNOSTIC SUMMARY ==========")
    print("Unique posts checked:", len(seen_ids))

    for category, count in sorted(categories.items()):
        print(f"{category}: {count}")

    print("\n========== ALL CLASSIFIED POSTS ==========")

    for index, post in enumerate(results, 1):
        print(f"\nPost {index}")
        print("Category:", post["category"])
        print("Score:", post["score"])
        print("Topics:", ", ".join(post["topics"]))
        print("Help phrases:", ", ".join(post["help"]))
        print("Problem phrases:", ", ".join(post["problems"]))
        print("Promo phrases:", ", ".join(post["promo"]))
        print("User:", post["user"])
        print("URL:", post["url"])
        print("Text:", post["text"][:350])

    print("\nDiagnostic test completed.")
    print("No replies were published.")


if __name__ == "__main__":
    main()
    
