"""Run the same incremental CLI on an interval; training/promotion remains explicit."""

import logging
import os
import subprocess
import sys
import time


def main():
    logging.basicConfig(level=logging.INFO)
    interval = int(os.getenv("SCHEDULE_INTERVAL_SECONDS", "21600"))
    timeout = int(os.getenv("SCHEDULE_TIMEOUT_SECONDS", "10800"))
    if interval < 60 or timeout < 1:
        raise ValueError("Scheduler interval must be >=60 seconds and timeout must be positive")
    command = [sys.executable, "-m", "football", "pipeline", "run", "--no-train", "--mode", "incremental",
        "--source", os.getenv("PROVIDER", "sofascore"), "--season-count", os.getenv("SCHEDULE_SEASON_COUNT", "1")]
    while True:
        started = time.monotonic()
        try:
            result = subprocess.run(command, timeout=timeout, check=False)
            logging.info("Scheduled CLI completed with exit code %d", result.returncode)
        except subprocess.TimeoutExpired:
            logging.error("Scheduled CLI exceeded its deadline; next run will mark the orphaned run interrupted")
        remaining = max(1, interval-(time.monotonic()-started))
        while remaining > 0:
            duration = min(remaining, 30)
            time.sleep(duration)
            remaining -= duration


if __name__ == "__main__":
    main()
