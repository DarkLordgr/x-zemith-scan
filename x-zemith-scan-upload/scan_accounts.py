#!/usr/bin/env python3
"""Read-only X watchlist scanner using TwitterAPI.io.

The API credential is read only from the TWITTERAPI_IO_KEY environment
variable. It is never written to the digest or committed to the repository.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"
PER_ACCOUNT = max(1, min(20, int(os.environ.get("PER_ACCOUNT", "10"))))
LOOKBACK_HOURS = max(1, min(168, int(os.environ.get("LOOKBACK_HOURS", "26"))))
WATCHLIST = os.environ.get("WATCHLIST", "accounts.txt")
OUT_DIR = os.environ.get("OUT_DIR", "digest")
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN = 0.35
MAX_ATTEMPTS = 5


def api_get(query, api_key):
    """Run one Latest search; never log the credential or response bodies."""
    params = urllib.parse.urlencode({"query": query, "queryType": "Latest"})
    request = urllib.request.Request(
        API_URL + "?" + params,
        headers={
            "X-API-Key": api_key,
            "User-Agent": "daily-content-scan/2.0",
        },
    )

    for attempt in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                sys.exit(
                    "ERROR: TwitterAPI.io rejected the API key. Update the "
                    "TWITTERAPI_IO_KEY GitHub Actions secret; do not paste it in chat."
                )
            retryable = error.code == 429 or error.code in (500, 502, 503, 504)
            if retryable and attempt + 1 < MAX_ATTEMPTS:
                time.sleep(2 ** attempt)
                continue
            print(f"WARN: TwitterAPI.io returned HTTP {error.code}; query skipped.", file=sys.stderr)
            return {}
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(2 ** attempt)
                continue
            print(f"WARN: network error; query skipped ({type(error).__name__}).", file=sys.stderr)
            return {}
    return {}


def load_watchlist():
    handles = []
    with open(WATCHLIST, encoding="utf-8") as source:
        for line in source:
            handle = line.split("#", 1)[0].strip().lstrip("@").strip()
            if handle and handle not in handles:
                handles.append(handle)
    if not handles:
        sys.exit(f"ERROR: no handles found in {WATCHLIST}")
    return handles


def parse_created(value):
    """Parse either Twitter's traditional timestamp or an ISO-8601 value."""
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def fetch_account_posts(handle, api_key, since, until):
    query = (
        f"from:{handle} since_time:{since} until_time:{until} "
        "-filter:replies"
    )
    data = api_get(query, api_key)
    tweets = data.get("tweets") or []
    returned_count = len(tweets)

    # Keep original posts even if the provider returns reposts in a search page.
    originals = [
        post for post in tweets
        if not post.get("retweeted_tweet")
        and not post.get("text", "").startswith("RT @")
    ]
    originals.sort(
        key=lambda post: parse_created(post.get("createdAt", "")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return originals[:PER_ACCOUNT], returned_count


def fmt_post(handle, post):
    author = post.get("author") or {}
    author_handle = author.get("userName") or handle
    created = parse_created(post.get("createdAt", ""))
    timestamp = (
        created.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if created else post.get("createdAt") or "no timestamp"
    )
    post_id = post.get("id", "")
    url = post.get("url") or f"https://x.com/{author_handle}/status/{post_id}"
    likes = int(post.get("likeCount") or 0)
    reposts = int(post.get("retweetCount") or 0) + int(post.get("quoteCount") or 0)
    return {
        "text": " ".join(post.get("text", "").split()),
        "likes": likes,
        "reposts": reposts,
        "url": url,
        "ts": timestamp,
        "created": created or datetime.min.replace(tzinfo=timezone.utc),
        "score": likes + reposts,
    }


def main():
    api_key = os.environ.get("TWITTERAPI_IO_KEY")
    if not api_key:
        sys.exit(
            "ERROR: TWITTERAPI_IO_KEY is not set.\n"
            "Add it as a GitHub Actions repository secret named TWITTERAPI_IO_KEY.\n"
            "Do not paste the key into chat or commit it to the repository."
        )

    handles = load_watchlist()
    now = datetime.now(timezone.utc)
    since_dt = now - timedelta(hours=LOOKBACK_HOURS)
    since = int(since_dt.timestamp())
    until = int(now.timestamp())

    all_posts = []
    sections = []
    returned_count = 0
    included_count = 0

    for handle in handles:
        posts, api_count = fetch_account_posts(handle, api_key, since, until)
        returned_count += api_count
        included_count += len(posts)
        time.sleep(SLEEP_BETWEEN)

        if not posts:
            sections.append(f"\n## @{handle}\n\n(no matching recent posts returned)\n")
            continue

        formatted = [fmt_post(handle, post) for post in posts]
        author_name = (posts[0].get("author") or {}).get("name") or handle
        all_posts.extend((handle, post) for post in formatted)
        lines = [f"\n## @{handle} - {author_name}", ""]
        for post in formatted:
            lines.append(f"- [{post['ts']}] {post['text']}")
            lines.append(
                f"  {post['url']} - {post['likes']} likes / {post['reposts']} reposts"
            )
        sections.append("\n".join(lines) + "\n")

    top = sorted(
        all_posts,
        key=lambda pair: (pair[1]["score"], pair[1]["created"]),
        reverse=True,
    )[:15]
    today = now.strftime("%Y-%m-%d")
    out = [
        f"# X morning scan - {today}",
        "",
        f"Accounts: {len(handles)} | posts included: {included_count} | "
        f"API posts returned: {returned_count} | "
        f"window: previous {LOOKBACK_HOURS} hours | "
        f"generated {now.strftime('%Y-%m-%d %H:%M')} UTC",
        "",
        "Source: TwitterAPI.io advanced_search, queryType=Latest. "
        "Read-only scan; no posting or account actions.",
        "",
        "## Top posts by engagement",
        "",
    ]
    if not top:
        out.append("No matching posts were returned in this scan window.")
    for handle, post in top:
        out.append(f"- **@{handle}** ({post['score']} pts): {post['text']}")
        out.append(f"  {post['url']}")
    out.append("\n## All accounts")
    out.extend(sections)

    os.makedirs(OUT_DIR, exist_ok=True)
    text = "\n".join(out) + "\n"
    for path in (
        os.path.join(OUT_DIR, f"digest-{today}.md"),
        os.path.join(OUT_DIR, "latest.md"),
    ):
        with open(path, "w", encoding="utf-8") as destination:
            destination.write(text)
    print(
        f"OK: wrote {OUT_DIR}/digest-{today}.md "
        f"({included_count} posts included from {len(handles)} accounts)"
    )


if __name__ == "__main__":
    main()
