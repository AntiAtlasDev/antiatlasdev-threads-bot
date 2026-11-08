
import os
import secrets
import requests

from flask import Flask, request, redirect, session, abort

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

APP_ID = os.environ.get("THREADS_APP_ID")
APP_SECRET = os.environ.get("THREADS_APP_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")

SCOPES = (
    "threads_basic,"
    "threads_content_publish,"
    "threads_keyword_search,"
    "threads_manage_replies,"
    "threads_read_replies"
)

GRAPH_URL = "https://graph.threads.net"


@app.route("/")
def home():
    return """
    <h2>AntiAtlasDev Threads Bot</h2>
    <p>OAuth server is running.</p>
    <a href="/login">Connect Threads account</a>
    """


@app.route("/health")
def health():
    return {"status": "running"}


@app.route("/login")
def login():
    if not APP_ID or not REDIRECT_URI:
        abort(500, "Missing application configuration")

    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    url = "https://threads.net/oauth/authorize"

    params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "response_type": "code",
        "state": state
    }

    from urllib.parse import urlencode
    return redirect(url + "?" + urlencode(params))


@app.route("/callback")
def callback():
    error = request.args.get("error")
    if error:
        return "Threads authorization failed: " + error, 400

    code = request.args.get("code")
    state = request.args.get("state")

    if not code or state != session.pop("oauth_state", None):
        abort(400, "Invalid OAuth response or state")

    if not APP_ID or not APP_SECRET or not REDIRECT_URI:
        abort(500, "Missing application configuration")

    response = requests.post(
        GRAPH_URL + "/oauth/access_token",
        data={
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": code
        },
        timeout=30
    )

    response.raise_for_status()
    short_token = response.json()["access_token"]

    long_response = requests.get(
        GRAPH_URL + "/access_token",
        params={
            "grant_type": "th_exchange_token",
            "client_secret": APP_SECRET,
            "access_token": short_token
        },
        timeout=30
    )

    long_response.raise_for_status()
    token_data = long_response.json()

    token = token_data.get("access_token")

    if not token:
        return "Token exchange failed.", 500

    return """
    <h2>Threads authorization successful</h2>
    <p>Your long-lived access token:</p>
    <textarea rows="5" cols="60">""" + token + """</textarea>
    <p>Copy this token and store it as a private environment variable.
    Never share it or publish it.</p>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
