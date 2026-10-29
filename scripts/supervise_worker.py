"""Local-only worker supervisor: restart a real exited process, never emulate a crash."""

import signal
import subprocess
import sys
import time

stopping = False
child = None


def stop(*_):
    global stopping
    stopping = True
    if child and child.poll() is None:
        child.terminate()


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
while not stopping:
    child = subprocess.Popen([sys.executable, "-m", "boreal.worker"])
    code = child.wait()
    print(f'{{"event":"worker_process_exited","exit_code":{code}}}', flush=True)
    if not stopping:
        time.sleep(1)
