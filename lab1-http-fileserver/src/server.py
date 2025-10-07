#!/usr/bin/env python3
import argparse, os, socket, sys, urllib.parse, mimetypes, time
from email.utils import formatdate

# Restrict to these types per lab spec
ALLOWED_MIME = {
    ".html": "text/html; charset=utf-8",
    ".png":  "image/png",
    ".pdf":  "application/pdf",
}

SERVER_NAME = "TinyPy/0.1"

def http_date():
    return formatdate(usegmt=True)

def build_response(status_code, reason, headers=None, body=b""):
    if headers is None: headers = {}
    status_line = f"HTTP/1.1 {status_code} {reason}\r\n"
    if "Date" not in headers: headers["Date"] = http_date()
    if "Server" not in headers: headers["Server"] = SERVER_NAME
    if "Connection" not in headers: headers["Connection"] = "close"
    if body and "Content-Length" not in headers:
        headers["Content-Length"] = str(len(body))
    # Serialize headers
    header_blob = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    return (status_line + header_blob + "\r\n").encode("iso-8859-1") + body

def safe_join(root, url_path):
    # Decode %xx, strip query/fragment, prevent path traversal
    path = urllib.parse.urlparse(url_path).path
    path = urllib.parse.unquote(path)
    rel = os.path.normpath(path.lstrip("/"))
    full = os.path.normpath(os.path.join(root, rel))
    if os.path.commonpath([root, full]) != os.path.abspath(root):
        return None
    return full

def dir_listing_html(root, req_path, fs_path):
    # req_path always starts with '/', fs_path is absolute
    entries = []
    try:
        with os.scandir(fs_path) as it:
            for e in sorted(it, key=lambda x: (not x.is_dir(), x.name.lower())):
                name = e.name + ("/" if e.is_dir() else "")
                href = urllib.parse.quote(name)
                size = "-" if e.is_dir() else f"{e.stat().st_size} B"
                mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e.stat().st_mtime))
                entries.append(f"<tr><td><a href=\"{href}\">{name}</a></td><td>{mtime}</td><td>{size}</td></tr>")
    except PermissionError:
        entries.append("<tr><td colspan=3>Permission denied</td></tr>")

    parent = "/" if req_path == "/" else urllib.parse.quote(os.path.join(req_path, "..")).replace("\\","/")
    title = f"Index of {req_path}"
    body = f"""<!doctype html>
<html><meta charset="utf-8"><title>{title}</title>
<h1>{title}</h1>
<table border="1" cellpadding="6" cellspacing="0">
<tr><th>Name</th><th>Last Modified</th><th>Size</th></tr>
<tr><td><a href="{parent}">Parent Directory</a></td><td></td><td></td></tr>
{''.join(entries)}
</table>
</html>"""
    return body.encode("utf-8")

def handle_request(conn, addr, root):
    conn.settimeout(5)
    data = b""
    try:
        # read until end of headers
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
        resp = build_response(400, "Bad Request", {"Content-Type": "text/plain"}, b"bad request\n")
        conn.sendall(resp)
        return

    print(f'{addr[0]} "{method} {path} {version}"')
    if method != "GET":
        resp = build_response(405, "Method Not Allowed", {"Content-Type": "text/plain"}, b"only GET supported\n")
        conn.sendall(resp); return

    fs_path = safe_join(root, path)
    if not fs_path or not os.path.exists(fs_path):
        body = b"<!doctype html><h1>404 Not Found</h1>"
        resp = build_response(404, "Not Found", {"Content-Type": "text/html; charset=utf-8"}, body)
        conn.sendall(resp); return

    if os.path.isdir(fs_path):
        # generate listing
        body = dir_listing_html(os.path.abspath(root), path if path.endswith("/") else path + "/", fs_path)
        headers = {"Content-Type": "text/html; charset=utf-8"}
        resp = build_response(200, "OK", headers, body)
        conn.sendall(resp); return

    # file case
    ext = os.path.splitext(fs_path)[1].lower()
    if ext not in ALLOWED_MIME:
        body = b"<!doctype html><h1>404 Not Found</h1><p>Unknown file type</p>"
        resp = build_response(404, "Not Found", {"Content-Type": "text/html; charset=utf-8"}, body)
        conn.sendall(resp); return

    with open(fs_path, "rb") as f:
        content = f.read()
    headers = {
        "Content-Type": ALLOWED_MIME[ext],
        "Last-Modified": formatdate(os.path.getmtime(fs_path), usegmt=True),
    }
    resp = build_response(200, "OK", headers, content)
    conn.sendall(resp)

def serve(root, host, port):
    root = os.path.abspath(root)
    print(f"Serving {root} on {host}:{port}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(1)  # one at a time
        while True:
            conn, addr = s.accept()
            with conn:
                handle_request(conn, addr, root)

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Tiny HTTP file server (single-threaded)")
    p.add_argument("root", help="directory to serve")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    if not os.path.isdir(args.root):
        print("Root must be a directory", file=sys.stderr); sys.exit(2)
    serve(args.root, args.host, args.port)