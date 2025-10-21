# Laboratory 2

Created: October 21, 2025 6:19 PM
Class: Network Programming

# **Concurrent HTTP File Server (Threads + Delay)**

## **Purpose**

Upgrade the Lab-1 server to handle **multiple simultaneous connections** and to **simulate work** with a configurable delay; validate concurrency using both our own client and a small script based on the requests library.

## **Theoretical notes**

- **Concurrency model:** I/O-bound servers benefit from a **thread pool**; each request is handled by a worker thread.
- **HTTP remains stateless:** each connection serves one request; concurrency changes *how many* we serve in parallel, not the protocol.
- **Throughput vs latency:** with a fixed per-request delay, more workers reduce overall **wall-time** for many concurrent requests.

## **Work progress**

1. **Implement concurrency & delay** in server.py (thread pool + --workers, --delay).
2. **Compose command** updated to pass --workers 8 --delay 0.5.
3. **Verify runtime args**
    
    — docker inspect $(docker compose ps -q web) --format '{{.Args}}' (shows workers/delay).
    
    ![image.png](Laboratory%202/image.png)
    
4. **Watch concurrent requests**
    
    —  docker compose logs -f web (overlapping GET lines).
    
    ![image.png](Laboratory%202/image%201.png)
    
5. **Own client, many in parallel**
    
    —  time bash tests/spawn_client_requests.sh localhost 8000 /books/ (≈1.1–1.2s with 10 requests, 8 workers, 0.5s delay).
    
    ![image.png](Laboratory%202/image%202.png)
    
6. **Requests-based load**
    
    —  python3 tests/stress_requests.py (summary with avg and p95).
    
    ![image.png](Laboratory%202/image%203.png)
    

## **Code additions**

- “from concurrent.futures import ThreadPoolExecutor” — imports Python’s thread-pool utility used to run many request handlers in parallel.
- “pool.submit(handle_request, conn, addr, root, delay) “— hands an accepted socket to a worker thread so new connections can be accepted immediately
- “time.sleep(delay)” — introduces a configurable per-request pause to simulate CPU/DB work and make concurrency visible in timing tests.

## **Conclusion**

The server now handles many clients concurrently using a thread pool, while an artificial delay lets us observe overlap. Tests with our client and requests confirmed major speedup versus single-threaded mode. The Compose setup keeps runs reproducible, simple, and LAN-accessible.