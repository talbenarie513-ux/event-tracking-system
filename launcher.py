"""
launcher.py — Client Launcher for Event Management System
──────────────────────────────────────────────────────────
This file runs on each USER's computer (not the server).
It opens a native desktop window that connects to the Flask
server running on the server machine.

No Flask, no database, no heavy packages needed here —
just pywebview to create the window.

HOW TO USE:
  1. Change SERVER_URL below to your server's IP address
  2. Run build_client.bat to turn this into a .exe
  3. Send the generated dist\EventManagementSystem\ folder to each user
"""

import webview  # pywebview — creates a native desktop window that renders a web page
                # install with:  pip install pywebview
                # this is the ONLY package needed on client machines

# ─────────────────────────────────────────────────────────────
# ⚠️  CHANGE THIS before building the .exe
# Replace XXX with your server machine's actual IP address.
# To find it: run "ipconfig" in CMD on the server machine
#             and look for "IPv4 Address" (e.g. 192.168.1.105)
# ─────────────────────────────────────────────────────────────
SERVER_URL = 'http://192.168.1.XXX:5000'

# create_window() defines the desktop window — does not open it yet
# title       = text shown in the window title bar and taskbar
# url         = the page to load — points at the server, not localhost
# width/height = initial window size in pixels
# resizable   = user can resize the window freely
# fullscreen  = False means it opens as a normal window, not full screen
# min_size    = smallest the window can be resized to (width, height)
# background_color = color shown for a split second while the page loads
window = webview.create_window(
    title='מערכת מעקב וניהול בעיות - תכנון ופיתוח',
    url=SERVER_URL,
    width=1600,
    height=900,
    resizable=True,
    fullscreen=False,
    min_size=(1200, 700),
    background_color='#667eea'
)

# webview.start() actually opens the window and enters the GUI event loop
# this line BLOCKS until the user closes the window — when they close it, the app exits
# debug=False      = no developer tools panel
# http_server=False = pywebview won't start its own server — Flask on the server handles that
webview.start(debug=False, http_server=False)