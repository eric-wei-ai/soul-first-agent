#!/usr/bin/env python3
"""File lock write utility for concurrent session safety."""
import sys
import fcntl
import os

def write_with_lock(filepath, content, mode="append"):
    filepath = os.path.expanduser(filepath)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    open_mode = "a" if mode == "append" else "w"
    with open(filepath, open_mode) as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(content + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)
    print(f"Written to {filepath} ({mode})")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 file_lock_write.py <filepath> <content> [--mode append|overwrite]")
        sys.exit(1)
    filepath = sys.argv[1]
    content = sys.argv[2]
    mode = "append"
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1]
    write_with_lock(filepath, content, mode)
