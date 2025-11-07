#!/usr/bin/env python3
import argparse, os, socket, sys, urllib.parse, time, threading, mimetypes
from email.utils import formatdate
from concurrent.futures import ThreadPoolExecutor

ALLOWED_MIME = {
    ".html": "text/html; charset=utf-8",
    ".png":  "image/png",
    ".pdf":  "application/pdf",
}
SERVER_NAME = "TinyPy/0.3"


hit_counter = {}             # { "/books/sample.pdf": int }
counter_lock = threading.Lock()

# token bucket per IP: {ip: (tokens, last_time)}
rl_state = {}
rl_lock = threading.Lock()

# ----------------------------------

def http_date():
    return formatdate(usegmt=True)

def build_response(code, reason, headers=None, body=b""):
    if headers is None: headers = {}
    headers.setdefault("Date", http_date())
    headers.setdefault("Server", SERVER_NAME)
    headers.setdefault("Connection", "close")
    if body and "Content-Length" not in headers:
        headers["Content-Length"] = str(len(body))
    status = f"HTTP/1.1 {code} {reason}\r\n"
    head = "".join(f"{k}: {v}\r\n" for k,v in headers.items())
    return (status + head + "\r\n").encode("iso-8859-1") + body

def safe_join(root, url_path):
    path = urllib.parse.urlparse(url_path).path
    path = urllib.parse.unquote(path)
    rel  = os.path.normpath(path.lstrip("/"))
    full = os.path.normpath(os.path.join(root, rel))
    if os.path.commonpath([os.path.abspath(root), full]) != os.path.abspath(root):
        return None
    return full

def dir_listing_html(root, req_path, fs_path):
    rows = []
    with os.scandir(fs_path) as it:
        for e in sorted(it, key=lambda x: (not x.is_dir(), x.name.lower())):
            name = e.name + ("/" if e.is_dir() else "")
            href = urllib.parse.quote(name)
            size = "-" if e.is_dir() else f"{e.stat().st_size} B"
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e.stat().st_mtime))
            # hits column (only for files)
            req_key = (req_path if req_path.endswith("/") else req_path + "/") + e.name
            hits = hit_counter.get(req_key, 0) if not e.is_dir() else "-"
            rows.append(f"<tr><td><a href=\"{href}\">{name}</a></td><td>{mtime}</td><td>{size}</td><td>{hits}</td></tr>")
    parent = "/" if req_path == "/" else urllib.parse.quote(os.path.join(req_path, "..")).replace("\\","/")
    title = f"Directory listing for {req_path}"
    html = f"""<!doctype html>
<meta charset="utf-8"><title>{title}</title>
<h1>{title}</h1>
<table border="1" cellpadding="6" cellspacing="0">
<tr><th>File / Directory</th><th>Last Modified</th><th>Size</th><th>Hits</th></tr>
<tr><td><a href="{parent}">Parent Directory</a></td><td></td><td></td><td>-</td></tr>
{''.join(rows)}
</table>"""
    return html.encode("utf-8")

def token_bucket_allow(ip, rate, burst):
    # disabled
    if rate <= 0:
        return True
    now = time.monotonic()
    with rl_lock:
        tokens, last = rl_state.get(ip, (burst, now))
        # refill
        tokens = min(burst, tokens + (now - last) * rate)
        if tokens >= 1.0:
            tokens -= 1.0
            rl_state[ip] = (tokens, now)
            return True
        rl_state[ip] = (tokens, now)
        return False

def handle_request(conn, addr, root, args):
    conn.settimeout(5)
    try:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk: break
            data += chunk
    except socket.timeout:
        return

    try:
        header_text = data.decode("iso-8859-1", errors="replace")
        request_line = header_text.split("\r\n", 1)[0]
        method, path, version = request_line.split()
    except Exception:
        conn.sendall(build_response(400, "Bad Request", {"Content-Type":"text/plain"}, b"bad request\n"))
        return

    # simulate work
    if args.delay > 0:
        time.sleep(args.delay)

    # HEAD allowed
    if method not in ("GET","HEAD"):
        conn.sendall(build_response(405,"Method Not Allowed",{"Content-Type":"text/plain"}, b"only GET/HEAD supported\n"))
        return
    send_body = (method == "GET")

    # rate limiting per IP
    ip = addr[0]
    burst = args.burst if args.burst is not None else max(1, int(args.rate))
    if not token_bucket_allow(ip, args.rate, burst):
        conn.sendall(build_response(429,"Too Many Requests",{"Content-Type":"text/plain"}, b"rate limit\n"))
        return

    fs_path = safe_join(root, path)
    if not fs_path or not os.path.exists(fs_path):
        conn.sendall(build_response(404,"Not Found",{"Content-Type":"text/html; charset=utf-8"}, b"<!doctype html><h1>404 Not Found</h1>"))
        return

    if os.path.isdir(fs_path):
        body = dir_listing_html(root, path if path.endswith("/") else path + "/", fs_path)
        headers = {"Content-Type":"text/html; charset=utf-8", "Content-Length": str(len(body))}
        if not send_body: body = b""
        conn.sendall(build_response(200,"OK",headers, body))
        return

    # increment hits (for files)
    # key must match what listing uses
    req_key = path
    if args.counter_mode == "naive":
        # race-prone on purpose
        current = hit_counter.get(req_key, 0)
        if args.counter_sleep: time.sleep(args.counter_sleep)
        hit_counter[req_key] = current + 1
    else:
        with counter_lock:
            current = hit_counter.get(req_key, 0)
            if args.counter_sleep: time.sleep(args.counter_sleep)
            hit_counter[req_key] = current + 1

    ext = os.path.splitext(fs_path)[1].lower()
    if ext not in ALLOWED_MIME:
        conn.sendall(build_response(404,"Not Found",{"Content-Type":"text/html; charset=utf-8"}, b"<!doctype html><h1>404 Not Found</h1><p>Unknown type</p>"))
        return

    size = os.path.getsize(fs_path)
    headers = {
        "Content-Type": ALLOWED_MIME[ext],
        "Last-Modified": formatdate(os.path.getmtime(fs_path), usegmt=True),
        "Content-Length": str(size),
    }
    if not send_body:
        conn.sendall(build_response(200,"OK",headers, b""))
        return
    with open(fs_path, "rb") as f:
        content = f.read()
    conn.sendall(build_response(200,"OK",headers, content))

def serve(root, host, port, workers, args):
    root = os.path.abspath(root)
    print(f"Serving {root} on {host}:{port}  workers={workers}  delay={args.delay}s  counter={args.counter_mode}  rate={args.rate}/s")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s, ThreadPoolExecutor(max_workers=workers) as pool:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(workers * 2) #ensures multiple 
        #clients can connect simultaneously instead of queuing at the TCP handshake.
        while True:
            conn, addr = s.accept()
            pool.submit(handle_request, conn, addr, root, args)

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Concurrent HTTP file server")
    p.add_argument("root", help="directory to serve")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--delay", type=float, default=0.0, help="per-request artificial delay (sec)")
    p.add_argument("--counter-mode", choices=["naive","locked"], default="locked")
    p.add_argument("--counter-sleep", type=float, default=0.0, help="extra sleep inside counter update (to show races)")
    p.add_argument("--rate", type=float, default=0.0, help="token bucket rate per IP (req/sec); 0 disables")
    p.add_argument("--burst", type=int, default=None, help="token bucket burst (defaults to rate)")
    args = p.parse_args()
    if not os.path.isdir(args.root):
        print("root must be a directory", file=sys.stderr); sys.exit(2)
    serve(args.root, args.host, args.port, args.workers, args)