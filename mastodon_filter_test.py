
import os
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse

API_URL = "https://mastodon.social"
ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")

SEARCH_TERMS = [
    "VPN recommendation",
    "VPN not working",
    "DNS problem",
]

TOPICS = [
    "vpn", "wireguard", "openvpn", "shadowsocks",
    "v2ray", "xray", "proxy", "dns", "firewall",
    "mock location", "gps spoofing", "gps simulator",
    "location simulator", "socks5", "doh", "dot",
    "dns over https", "dns over tls",
]

PROMO_PHRASES = [
    "buy now", "discount", "promo code",
    "referral link", "sign up using",
    "follow me", "giveaway",
]

HELP_PHRASES = [
    "need help", "can someone help",
    "any advice", "any suggestions",
    "how do i", "how can i", "does anyone know",
    "looking for", "recommend", "recommendation",
    "alternative to", "alternatives to",
    "what vpn", "which vpn", "any vpn",
]

PROBLEM_PHRASES = [
    "not working", "doesn't work", "does not work",
    "stopped working", "connection failed",
    "cannot connect", "can't connect",
    "blocked", "leaking", "leak",
    "issue with", "problem with", "error",
    "slow connection", "disconnects",
]

RECOMMENDATION_TERMS = [
    "recommend", "recommendation", "alternative",
    "alternatives", "suggestion", "suggestions",
    "looking for", "which vpn", "what vpn",
]

HARDWARE_TERMS = [
    "gpu", "cpu", "ram", "ssd", "motherboard",
    "graphics card", "processor", "laptop",
]

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Accept": "application/json",
})
session.mount(
    "https://",
    HTTPAdapter(max_retries=0)
)


def contains_any(text, phrases):
    return any(phrase in text for phrase in phrases)


def classify(post):
    content = post.get("content", "")
    text = content.lower()

    # Remove HTML tags
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return "UNRELATED", 0

    # Must mention at least one relevant topic
    if not contains_any(text, TOPICS):
        return "UNRELATED", 0

    # Exclude obvious advertisements
    if contains_any(text, PROMO_PHRASES):
        return "PROMOTIONAL", 0

    # Exclude unrelated hardware discussions
    if contains_any(text, HARDWARE_TERMS):
        return "UNRELATED", 0

    has_help = contains_any(text, HELP_PHRASES)
    has_problem = contains_any(text, PROBLEM_PHRASES)
    has_recommendation = contains_any(text, RECOMMENDATION_TERMS)

    if has_recommendation:
        return "RECOMMENDATION", 10

    if has_help and has_problem:
        return "HELP_AND_PROBLEM", 9

    if has_problem:
        return "TECHNICAL_PROBLEM", 8

    if has_help:
        return "HELP_REQUEST", 8

    if "?" in text:
        return "GENERAL_QUESTION", 6

    return "GENERAL_DISCUSSION", 4


def search_posts(term):
    print(f"Searching: {term}", flush=True)

    try:
        response = session.get(
            f"{API_URL}/api/v2/search",
            params={
                "q": term,
                "type": "statuses",
                "limit": 10,
            },
            timeout=(3, 5),
        )

        print(
            f"HTTP {response.status_code}: {term}",
            flush=True
        )

        response.raise_for_status()
        data = response.json()

        return data.get("statuses", [])

    except requests.RequestException as error:
        print(f"Search failed ({term}): {error}", flush=True)
        return []

    except ValueError:
        print(f"Invalid JSON response ({term})", flush=True)
        return []


def main():
    if not ACCESS_TOKEN:
        print("ERROR: MASTODON_ACCESS_TOKEN is missing.")
        return

    unique_posts = {}

    for term in SEARCH_TERMS:
        posts = search_posts(term)

        for post in posts:
            post_id = post.get("id")
            if post_id:
                unique_posts[post_id] = post

    print("\n========== SEARCH SUMMARY ==========", flush=True)
    print(f"Unique posts: {len(unique_posts)}", flush=True)

    results = []

    for post in unique_posts.values():
        category, score = classify(post)

        results.append({
            "post": post,
            "category": category,
            "score": score,
        })

    categories = {}

    for item in results:
        category = item["category"]
        categories[category] = categories.get(category, 0) + 1

    print("\n========== CATEGORIES ==========", flush=True)

    for category, count in sorted(categories.items()):
        print(f"{category}: {count}", flush=True)

    candidates = [
        item for item in results
        if item["score"] >= 6
    ]

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    print("\n========== TOP CANDIDATES ==========", flush=True)

    if not candidates:
        print("No suitable candidates found.", flush=True)

    for index, item in enumerate(candidates[:10], 1):
        post = item["post"]

        account = post.get("account", {})
        username = account.get("acct", "Unknown")

        content = post.get("content", "")
        import re
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()

        url = post.get("url", "")

        print(f"\n{index}. @{username}", flush=True)
        print(
            f"Category: {item['category']} | Score: {item['score']}",
            flush=True
        )
        print(f"Text: {content[:500]}", flush=True)
        print(f"URL: {url}", flush=True)

    print("\n========== TEST FINISHED ==========", flush=True)
    print("No replies were published.", flush=True)


if __name__ == "__main__":
    main()
