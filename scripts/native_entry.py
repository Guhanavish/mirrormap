"""PyInstaller entrypoint for both the CLI and native hooks."""
from projectmirror.__main__ import cmd_main

if __name__ == "__main__":
    raise SystemExit(cmd_main())
