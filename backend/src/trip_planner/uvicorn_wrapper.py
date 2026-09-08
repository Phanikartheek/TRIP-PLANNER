"""
Uvicorn wrapper that dynamically resolves $PORT if passed as a literal string
by container runtimes (such as Railway or Render).
"""

import os
import sys

import uvicorn.main


def main():
    port = os.environ.get("PORT", "8000")
    new_argv = []
    for arg in sys.argv:
        if arg in ("$PORT", "${PORT}", "${PORT:-8000}"):
            new_argv.append(port)
        else:
            new_argv.append(arg)
    sys.argv = new_argv
    uvicorn.main.main()


if __name__ == "__main__":
    main()
