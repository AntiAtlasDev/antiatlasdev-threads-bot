
import os
import requests

TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
URL = "https://graph.threads.net/v1.0/keyword_search"

params = {
    "q": "Instagram",
    "search_type": "RECENT",
    "fields": "id,text,username,permalink,timestamp",
    "limit": 10,
    "access_token": TOKEN
}

try:
    if not TOKEN:
        print("ERROR: THREADS_ACCESS_TOKEN is not configured.")
    else:
        response = requests.get(URL, params=params, timeout=30)

        print("HTTP status:", response.status_code)
        data = response.json()

        if response.ok:
            posts = data.get("data", [])
            print("Search successful.")
            print("Posts found:", len(posts))

            for post in posts:
                print("--------------------")
                print("User:", post.get("username"))
                print("Text:", post.get("text", "")[:250])
                print("Link:", post.get("permalink"))
        else:
            print("Search error:", data.get("error", {}))

except Exception as error:
    print("Error:", str(error))
