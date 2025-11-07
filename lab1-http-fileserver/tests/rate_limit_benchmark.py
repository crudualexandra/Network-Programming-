#!/usr/bin/env python3
import argparse, time, statistics
from collections import defaultdict
import requests, threading

def hammer(label, url, rps, duration, timeout, results):
    sess = requests.Session()
    stop = time.perf_counter() + duration
    period = 1.0 / float(rps)
    sent = ok = rl = other = 0
    lat = []
    next_at = time.perf_counter()
    while True:
        now = time.perf_counter()
        if now >= stop: break
        if now < next_at:
            time.sleep(max(0.0, next_at - now))
        t0 = time.perf_counter()
        try:
            r = sess.get(url, timeout=timeout)
            dt = time.perf_counter() - t0
            sent += 1
            if r.status_code == 200:
                ok += 1; lat.append(dt)
            elif r.status_code == 429:
                rl += 1
            else:
                other += 1
        except Exception:
            other += 1
        next_at += period
    results[label]["sent"] += sent
    results[label]["ok"] += ok
    results[label]["rl"] += rl
    results[label]["other"] += other
    results[label]["lat"].extend(lat)

def summarize(label, res, duration):
    sent, ok, rl, other, lat = res["sent"], res["ok"], res["rl"], res["other"], res["lat"]
    okps = ok / duration
    rlps = rl / duration
    med = statistics.median(lat) if lat else 0.0
    p95 = lat[int(0.95*len(lat))-1] if lat else 0.0
    print(f"[{label}] sent={sent} ok={ok} (ok/s={okps:.2f}) 429={rl} (429/s={rlps:.2f}) other={other} | median={med:.3f}s p95={p95:.3f}s")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="client")
    ap.add_argument("--url", default="http://localhost:8001/books/sample.pdf")
    ap.add_argument("--rps", type=float, default=5.0)
    ap.add_argument("--duration", type=int, default=10)
    ap.add_argument("--timeout", type=float, default=5.0)
    args = ap.parse_args()

    res = defaultdict(lambda: {"sent":0,"ok":0,"rl":0,"other":0,"lat":[]})
    t = threading.Thread(target=hammer, args=(args.label, args.url, args.rps, args.duration, args.timeout, res))
    t.start(); t.join()
    summarize(args.label, res[args.label], args.duration)

if __name__ == "__main__":
    main()