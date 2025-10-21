# File: src/client.py
#!/usr/bin/env python3
import os, sys, socket

USAGE = "Usage: client.py server_host server_port filename"

def recv_all(sock):
    chunks = []
    while True:
        b = sock.recv(4096)
        if not b: break
        chunks.append(b)
    return b"".join(chunks)

def parse_headers(raw):
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1", errors="replace").split("\r\n")
    status_line = lines[0]
    parts = status_line.split(" ", 2)
    code = int(parts[1]) if len(parts) >= 2 else 0
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return code, headers, body

def main():
    if len(sys.argv) != 4:
        print(USAGE); sys.exit(2)
    host, port, filename = sys.argv[1], int(sys.argv[2]), sys.argv[3].lstrip("/")
    path = "/" + filename

    req = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode("ascii")
    with socket.create_connection((host, port), timeout=5) as s:
        s.sendall(req)
        raw = recv_all(s)

    code, headers, body = parse_headers(raw)
    ctype = headers.get("content-type", "")
    if code != 200:
        print(f"HTTP {code}\n{body.decode('utf-8', errors='replace')}")
        sys.exit(1)

    if ctype.startswith("text/html"):
        print(body.decode("utf-8", errors="replace"))
    elif ctype.startswith("image/png") or ctype.startswith("application/pdf"):
        os.makedirs("downloads", exist_ok=True)
        out = os.path.join("downloads", os.path.basename(filename))
        with open(out, "wb") as f: f.write(body)
        print(f"Saved {ctype} to {out}")
    else:
        print(f"Unknown content-type {ctype}, length={len(body)}")

if __name__ == "__main__":
    main()