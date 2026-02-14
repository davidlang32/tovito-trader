import os
from datetime import datetime
from pathlib import Path

log_file = Path("C:/tovito-trader/logs/test_task.log")
log_file.parent.mkdir(parents=True, exist_ok=True)

with open(log_file, "a") as f:
    f.write(f"Test ran at: {datetime.now()}\n")
    f.write(f"Working dir: {os.getcwd()}\n")
    f.write(f"User: {os.environ.get('USERNAME', 'unknown')}\n")
    f.write("SUCCESS\n\n")

print("Test completed")