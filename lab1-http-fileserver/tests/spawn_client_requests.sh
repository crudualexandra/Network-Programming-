# fires N background curls to generate concurrent loadn d
#!/usr/bin/env bashwq1  
set -euo pipefail

host=${1:?host}; port=${2:?port}; path=${3:?path}
N=${N:-10}
url="http://${host}:${port}${path}"

echo "Spawning $N client requests to $url"
pids=()
for i in $(seq 1 "$N"); do
  curl -s -o /dev/null "$url" &   # run in background
  pids+=($!)
done
for pid in "${pids[@]}"; do
  wait "$pid"                     # wait for ALL, after the loop
done
echo "Done."