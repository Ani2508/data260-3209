"""Copy stdin to the screen and to a log file, adding a timestamp to every line.

Usage: <command> 2>&1 | python3 code/tslog.py reports/hw06/RUN_LOG.txt
"""
import sys
from datetime import datetime

with open(sys.argv[1], "a", encoding="utf-8") as log:
    for line in sys.stdin:
        print(line, end="", flush=True)
        log.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {line}")
        log.flush()
