
import os
import re
import html
import requests

API_URL = "https://mastodon.social"
TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")

SEARCH_TERMS = [
    "Android VPN problem",
    "Android VPN recommendation",
    "Android WireGuard",
    "Android OpenVPN",
    "Android DNS problem",
    "Android GPS problem",
    "Android proxy",
    "Android firewall",
    "Android app not working",
    "Android mock location",
    "Android VPN alternative",
    "smartphone VPN problem",
    "Android connection issue"
]

TOPICS = [
    "vpn", "wireguard", "openvpn",
    "shadowsocks", "v2ray", "xray",
    "proxy", "dns", "firewall",
    "mock location", "gps spoofing",
    "gps simulator", "location simulator"
]

ANDROID_CONTEXT = [
    "android", "android phone", "android app",
    "android device", "android tablet",
    "smartphone", "mobile phone",
    "samsung galaxy", "google pixel",
    "oneplus", "xiaomi phone",
    "redmi phone", "mobile device"
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
    "what app", "what should i",
    "what vpn", "which vpn"
]

PROBLEM_PHRASES = [
    "not working", "doesn't work",
    "does not work", "can't connect",
    "cannot connect", "unable to connect",
    "connection problem", "connection issue",
    "having trouble", "having problems",
    "keeps crashing", "app crashes",
    "error when", "failed to connect",
    "stopped working", "getting an error",
    "doesn't connect", "not connecting",
    "connection keeps dropping"
]

PROMO_PHRASES = [
    "sponsored", "affiliate link",
    "promo code", "buy now",
    "limited offer", "giveaway",
    "discount code", "advertisement",
    "introducing our", "meet our new",
    "download now", "get started today",
    "launching our", "use my referral",
    "sign up using my link"
]

HARDWARE_TERMS = [
    "gpu", "graphics card", "ssd",
    "ram prices", "processor",
    "motherboard", "chipset",
    "graphics driver", "benchmark"
]


def clean_text(content):
    content = re.sub(r"<[^>]+>", " ", content)
    content = html.unescape(content)
    content = re.sub(r"https?://\S+", " ", content)
    return re.sub(r"\s+", " ", content).strip().lower()


def matches(text, phrases):
    found = []

    for phrase in phrases:
        pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"

        if re.search(pattern, text):
            found.append(phrase)

    return found


def classify(content):
    text = clean_text(content)

    topics = matches(text, TOPICS)

    if not topics:
        return "UNRELATED", 0

    if matches(text, PROMO_PHRASES):
        return "PROMOTIONAL", 0

    android_found = matches(text, ANDROID_CONTEXT)

    if not android_found:
        return "NON_ANDROID", 0

    if matches(text, HARDWARE_TERMS):
        return "HARDWARE", 0

    help_found = matches(text, HELP_PHRASES)
    problem_found = matches(text, PROBLEM_PHRASES)

    if help_found and problem_found:
        return "HELP_AND_PROBLEM", 9

    if help_found:
        return "HELP_REQUEST", 7

    if problem_found:
        return "TECHNICAL_PROBLEM", 7

    if "?" in text:
        return "GENERAL_QUESTION", 4

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

                text = clean_text(
                    status.get("content", "")
                )

                category, score = classify(text)

                results.append({
                    "category": category,
                    "score": score,
                    "user": status.get(
                        "account", {}
                    ).get("acct", "Unknown"),
                    "url": status.get("url", ""),
                    "text": text
                })

        except requests.RequestException as error:
            print("Network error:", error)

    counts = {}

    for post in results:
        category = post["category"]
        counts[category] = counts.get(category, 0) + 1

    print("\n===== ANDROID FILTER SUMMARY =====")
    print("Unique posts:", len(seen))

    for category, count in sorted(counts.items()):
        print(f"{category}: {count}")

    candidates = [
        post for post in results
        if post["score"] >= 7
    ]

    candidates.sort(
        key=lambda post: post["score"],
        reverse=True
    )

    print("\n===== TOP 5 ANDROID CANDIDATES =====")

    for index, post in enumerate(candidates[:5], 1):
        print(f"\n{index}. {post['category']}")
        print("User:", post["user"])
        print("URL:", post["url"])
        print("Text:", post["text"][:220])

    print("\nTest completed. No replies published.")
    print("Total candidates:", len(candidates))


if __name__ == "__main__":
    main()
