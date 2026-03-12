"""
Desktop Application Launcher for Event Management System
Opens the system in a standalone window (not browser)
MULTI-USER VERSION - Allows network access for multiple users
"""

import webview    # pywebview — creates a native desktop window that renders a local web page
import threading  # built-in — lets Flask run in the background while the GUI runs in the main thread
import time       # built-in — used to pause execution while Flask starts up
import sys        # built-in — lets us modify the Python module search path at runtime
import os         # built-in — used to build absolute file paths
import requests   # used by DownloadAPI to fetch file bytes from the local Flask server

# Add backend to path so we can import from the backend folder
sys.path.insert(0, 'backend')
from app import app  # imports the Flask app object from backend/app.py

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# global reference to the pywebview window — needed by DownloadAPI methods
# to call window.create_file_dialog()
window = None


class DownloadAPI:
    """
    Exposed to JavaScript as window.pywebview.api
    Called by the frontend instead of the normal <a>.click() download trick,
    which pywebview silently blocks in desktop app mode.
    """

    def save_file(self, file_id, filename):
        """
        Opens a native Save As dialog, fetches the file from Flask, writes it to disk.
        Returns {'ok': True, 'path': '...'} or {'ok': False, 'error': '...'}.
        """
        try:
            result = window.create_file_dialog(
                webview.FileDialog.SAVE,
                directory=os.path.expanduser('~\\Downloads'),
                save_filename=filename
            )
            if not result or not result[0]:
                return {'ok': False, 'error': 'cancelled'}

            save_path = result[0]
            response = requests.get(
                f'http://127.0.0.1:5000/api/files/{file_id}/download',
                timeout=30
            )
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(response.content)

            return {'ok': True, 'path': save_path}

        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def save_report(self, filename):
        """
        Opens a native Save As dialog and downloads the Excel report from Flask.
        Returns {'ok': True, 'path': '...'} or {'ok': False, 'error': '...'}.
        """
        try:
            result = window.create_file_dialog(
                webview.FileDialog.SAVE,
                directory=os.path.expanduser('~\\Downloads'),
                save_filename=filename
            )
            if not result or not result[0]:
                return {'ok': False, 'error': 'cancelled'}

            save_path = result[0]
            response = requests.get(
                'http://127.0.0.1:5000/api/reports/excel',
                timeout=60
            )
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(response.content)

            return {'ok': True, 'path': save_path}

        except Exception as e:
            return {'ok': False, 'error': str(e)}


def start_flask_server():
    """Start Flask server in background thread with network access"""
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0    # tells Flask never to cache static files
    app.config['TEMPLATES_AUTO_RELOAD'] = True      # auto-reloads changed templates without restarting
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)


def main():
    global window  # DownloadAPI methods need to call window.create_file_dialog

    print("=" * 50)
    print("  Event Management System - Multi-User Server")
    print("=" * 50)
    print()

    # Start Flask server in background thread
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    # daemon=True means this thread is killed automatically when the main program exits
    flask_thread.start()

    print("✅ Starting server...")
    print("⏳ Waiting for server to initialize...")

    # Wait for Flask to start before launching the window
    time.sleep(2)

    print("✅ Server is running!")
    print()
    print("📡 Server is accessible at:")
    print("   - Local: http://127.0.0.1:5000")
    print("   - Network: http://YOUR_IP_ADDRESS:5000")
    print()
    print("ℹ️  To find your IP address:")
    print("   - Windows: Run 'ipconfig' in CMD")
    print("   - Look for 'IPv4 Address'")
    print()
    print("🌐 Other users can connect by:")
    print("   1. Getting your IP address (e.g., 192.168.1.100)")
    print("   2. Opening: http://YOUR_IP:5000 in their browser")
    print()
    print("=" * 50)
    print()

    # Start the email scheduler (runs in background)
    from email_notifications import start_scheduler
    start_scheduler()

    # Create the DownloadAPI instance — exposed to JS as window.pywebview.api
    api = DownloadAPI()

    # Create the desktop window
    window = webview.create_window(
        title='מערכת מעקב וניהול בעיות - תכנון ופיתוח',
        url='http://127.0.0.1:5000',   # points the window at the local Flask server
        js_api=api,                     # exposes api as window.pywebview.api in JavaScript
        width=1600,
        height=900,
        resizable=True,
        fullscreen=False,
        min_size=(1200, 700),
        background_color='#667eea'
    )

    # Start the GUI event loop — blocks here until the window is closed
    webview.start(debug=False, http_server=False)


if __name__ == '__main__':
    main()