#!/usr/bin/env python3
"""
client.py — Simple HTTP/1.1 client for the lab.

Usage:
  python3 client.py <server_host> <server_port> <filename>

Behavior (per lab spec):
  - For HTML (pages and directory listings): print the response body to stdout.
  - For PNG/PDF: save the file into ./downloads/ and print the saved path.

Notes:
  - Timeout is configurable via env var CLIENT_TIMEOUT (seconds), default 20s.
  - Uses GET and expects the server to close the connection (Connection: close).
"""
import os
import sys
import socket

USAGE = "Usage: client.py server_host server_port filename"
DEFAULT_TIMEOUT = float(os.getenv("CLIENT_TIMEOUT", "20.0"))  # seconds


def recv_all(sock: socket.socket) -> bytes:
    """Read until the server closes the connection or a timeout occurs."""
    chunks = []
    while True:
        try:
            b = sock.recv(4096)
        except socket.timeout:
            # Stop waiting; return what we have (better than hanging forever)
            break
        if not b:
            break
        chunks.append(b)
    return b"".join(chunks)


def parse_headers(raw: bytes):
    """Split raw HTTP response into (status_code, headers_dict, body_bytes)."""
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1", errors="replace").split("\r\n")
    status_line = lines[0] if lines else ""
    parts = status_line.split(" ", 2)
    try:
        code = int(parts[1]) if len(parts) >= 2 else 0
    except ValueError:
        code = 0
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return code, headers, body


def is_html(ctype: str) -> bool:
    return ctype.startswith("text/html")


def is_binary_save(ctype: str) -> bool:
    return ctype.startswith("image/png") or ctype.startswith("application/pdf")


def main():
    if len(sys.argv) != 4:
        print(USAGE)
        sys.exit(2)

    host = sys.argv[1]
    try:
        port = int(sys.argv[2])
    except ValueError:
        print(USAGE)
        sys.exit(2)

    filename = sys.argv[3].lstrip("/")
    path = "/" + filename if filename else "/"

    # Build a minimal GET request
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("ascii")

    # Connect, set timeouts for both connect and recv, then read all bytes
    with socket.create_connection((host, port), timeout=DEFAULT_TIMEOUT) as s:
        s.settimeout(DEFAULT_TIMEOUT)
        s.sendall(req)
        raw = recv_all(s)

    code, headers, body = parse_headers(raw)
    ctype = headers.get("content-type", "")

    if code != 200:
        # Print status and any text body (e.g., 404 / 429) for visibility
        text = body.decode("utf-8", errors="replace")
        print(f"HTTP {code}\n{text}")
        sys.exit(1)

    if is_html(ctype):
        # Print HTML (page or directory listing)
        print(body.decode("utf-8", errors="replace"))
        return

    if is_binary_save(ctype):
        os.makedirs("downloads", exist_ok=True)
        # If the request path ends with '/', give a default filename
        base = os.path.basename(filename) or "index.html"
        out_path = os.path.join("downloads", base)
        with open(out_path, "wb") as f:
            f.write(body)
        print(f"Saved {ctype} to {out_path}")
        return

    # Fallback for unknown content types
    print(f"Unknown content-type: {ctype or '(none)'}; bytes={len(body)}")


if __name__ == "__main__":
    main()