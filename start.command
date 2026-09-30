#!/bin/bash
# Double-click to start the YKI player and open it in the browser.
cd "$(dirname "$0")"
python3 _app/server.py --open
