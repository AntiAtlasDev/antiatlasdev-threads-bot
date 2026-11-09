
import os
import re
import html
import requests
from requests.adapters import HTTPAdapter

API_URL = "https://mastodon.social"
ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")

SEARCH_TERMS = [
    "VPN recommendation",
    "VPN not working",
    "DNS problem",
]

TOPIC_PATTERN = re.compile(
    r"\b(vpn|wireguard|openvpn|shadowsocks|v2ray|xray|"
    r"proxy|dns|firewall|socks5|doh|dot|"
    r"mock location|gps spoofing|gps simulator|"
    r"location simulator|dns over https|dns over tls)\b",
    re.IGNORECASE,
)

RECOMMENDATION_PATTERN = re.compile(
    r"\b(recommend(?:ation|ations|ed)?|"
    r"suggest(?:ion|ions|ed)?|"
    r"alternative(?:s)? to|"
    r"looking for|"
    r"which vpn|what vpn|"
    r"any good vpn|"
    r"need a vpn|"
    r"need vpn)\b",
    re.IGNORECASE,
)

HELP_PATTERN = re.compile(
    r"\b(need help|can someone help|"
    r"how do i|how can i|"
    r"any advice|"
    r"does anyone know|"
    r"can't configure|cannot configure|"
    r"help with)\b",
    re.IGNORECASE,
)

PROBLEM_PATTERN = re.compile(
    r"\b(not working|doesn't work|does not work|"
    r"stopped working|connection failed|"
    r"cannot connect|can't connect|"
    r"blocked|leaking|leak|"
    r"issue|problem|error|"
    r"disconnects|slow connection)\b",
    re.IGNORECASE,
)

PROMO_PATTERN = re.compile(
    r"\b(buy now|discount code|promo code|"
    r"referral link|giveaway|"
    r"sign up using my link)\b",
    re.IGNORECASE,
)

SENSITIVE_PATTERN = re.compile(
    r"\b(election|elections|political|politics|"
    r"politician|fascist|fascists|fascism|"
    r"nazi|nazis|religion|religious|"
    r"prayer|god|jesus|allah|"
    r"suicide|psychological help|"
    r"mental health hotline)\b",
    re.IGNORECASE,
)

HARDWARE_PATTERN = re.compile(
    r"\b(gpu|cpu|ram|ssd|motherboard|"
    r"graphics card|processor)\b",
    re.IGNORECASE,
)

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Accept": "application/json",
})
session.mount(
    "https://",
    HTTPAdapter(max_retries=0)
)


def clean_text(content):
    content = html.unescape(content or "")
    content = re.sub(r"<[^>]+>", " ", content)
    content = re.sub(r"\s+", " ", content)
    return content.strip()


def split_sentences(text):
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def classify(post):
    text = clean_text(post.get("content", ""))
    if not text:
        return "UNRELATED", 0

    # Exclude sensitive discussions
    if SENSITIVE_PATTERN.search(text):
        return "SENSITIVE", 0

    # Exclude advertisements
    if PROMO_PATTERN.search(text):
        return "PROMOTIONAL", 0

    sentences = split_sentences(text)

    for sentence in sentences:
        has_topic = bool(TOPIC_PATTERN.search(sentence))

        if not has_topic:
            continue

        # Ignore hardware-focused sentences
        if HARDWARE_PATTERN.search(sentence):
            continue

        if RECOMMENDATION_PATTERN.search(sentence):
            return "RECOMMENDATION", 10

        if HELP_PATTERN.search(sentence):
            return "HELP_REQUEST", 9

        if PROBLEM_PATTERN.search(sentence):
            return "TECHNICAL_PROBLEM", 9

        if "?" in sentence:
            return "RELATED_QUESTION", 7

    return "GENERAL_DISCUSSION", 0


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
        return response.json().get("statuses", [])

    except requests.RequestException as error:
        print(f"Search failed: {error}", flush=True)
        return []

    except ValueError:
        print("Invalid JSON response.", flush=True)
        return []


def main():
    if not ACCESS_TOKEN:
        print("ERROR: MASTODON_ACCESS_TOKEN is missing.")
        return

    unique_posts = {}

    for term in SEARCH_TERMS:
        for post in search_posts(term):
            post_id = post.get("id")
            if post_id:
                unique_posts[post_id] = post

    print("\n========== SEARCH SUMMARY ==========")
    print(f"Unique posts: {len(unique_posts)}")

    categories = {}
    candidates = []

    for post in unique_posts.values():
        category, score = classify(post)

        categories[category] = categories.get(category, 0) + 1

        if score >= 7:
            candidates.append({
                "post": post,
                "category": category,
                "score": score,
            })

    print("\n========== CATEGORIES ==========")

    for category, count in sorted(categories.items()):
        print(f"{category}: {count}")

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    print("\n========== QUALIFIED CANDIDATES ==========")

    if not candidates:
        print("No qualified candidates found.")

    for index, item in enumerate(candidates[:10], 1):
        post = item["post"]
        account = post.get("account", {})

        username = account.get("acct", "Unknown")
        text = clean_text(post.get("content", ""))
        url = post.get("url", "")

        print(f"\n{index}. @{username}")
        print(
            f"Category: {item['category']} "
            f"| Score: {item['score']}"
        )
        print(f"Text: {text[:500]}")
        print(f"URL: {url}")

    print("\n========== TEST FINISHED ==========")
    print("No replies were published.")


if __name__ == "__main__":
    main()
