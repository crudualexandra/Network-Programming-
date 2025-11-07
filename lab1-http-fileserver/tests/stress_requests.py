#generates many concurrent GETs using Python threads to validate concurrency 
#!/usr/bin/env python3
import requests, time
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = "http://localhost:8001/books/"  # change if needed
TOTAL = 40
CONCURRENCY = 8
TIMEOUT = 10

def one(i):
    t0 = time.perf_counter()
    r = requests.get(URL, timeout=TIMEOUT)
    dt = time.perf_counter() - t0
    return (i, r.status_code, dt)

def main():
    t0 = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futs = [pool.submit(one, i) for i in range(TOTAL)]
        for f in as_completed(futs):
            results.append(f.result())
    t1 = time.perf_counter()
    times = [dt for (_, code, dt) in results if code == 200]
    times.sort()
    p95 = times[int(0.95 * len(times))-1] if times else 0.0
    print(f"OK {len(times)}/{TOTAL} in {t1 - t0:.2f}s | avg={sum(times)/len(times):.3f}s | p95={p95:.3f}s")

if __name__ == "__main__":
    main()