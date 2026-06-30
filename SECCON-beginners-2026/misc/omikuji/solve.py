#!/usr/bin/env python3
import random
import re
import socket
import sys

FLAG_RE = re.compile(rb"ctf4b\{[^}]*\}")
HOST, PORT = "URL", [PORT]
ROUNDS = 5
NAME = "a"


def recv_until(sock, marker):
    buf = b""
    while marker not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
    return buf


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT

    rng = random.Random()
    rng.seed(NAME)
    predictions = [rng.randint(1, 1000000) for _ in range(ROUNDS)]

    sock = socket.create_connection((host, port), timeout=10)
    recv_until(sock, b"name > ")
    sock.sendall(NAME.encode() + b"\n")

    for n in predictions:
        recv_until(sock, b"> ")
        sock.sendall(str(n).encode() + b"\n")

    data = recv_until(sock, b"}")
    data += sock.recv(4096)
    sock.close()

    m = FLAG_RE.search(data)
    print(m.group().decode() if m else data.decode("latin-1", "replace"))


if __name__ == "__main__":
    main()
