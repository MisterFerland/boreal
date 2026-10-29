import time
import urllib.request
import urllib.error

for attempt in range(60):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/health/ready", timeout=2):
            print("BOREAL API, worker and engine ready.")
            break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(1)
else:
    raise SystemExit("Readiness timed out; inspect API and worker logs.")
