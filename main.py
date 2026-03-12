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

# Add backend to path so we can import from the backend folder
sys.path.insert(0, 'backend')  # inserts 'backend' at the front of sys.path so Python finds app.py there
from app import app  # imports the Flask app object from backend/app.py

# Get the absolute path to the project directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # stores the folder where main.py lives — used if needed for paths

def start_flask_server():
    """Start Flask server in background thread with network access"""
    # Disable Flask caching
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0    # tells Flask never to cache static files
    app.config['TEMPLATES_AUTO_RELOAD'] = True      # auto-reloads changed templates without restarting

    # Run Flask with network access (0.0.0.0 allows other computers to connect)
    # threaded=True allows multiple users simultaneously
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)
    # host='0.0.0.0' binds to all network interfaces so other computers on the network can connect
    # use_reloader=False prevents Flask from spawning a second process (which would break threading)

def main():
    """Main function to launch desktop application"""

    print("=" * 50)
    print("  Event Management System - Multi-User Server")
    print("=" * 50)
    print()

    # Start Flask server in background thread
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    # daemon=True means this thread will be killed automatically when the main program exits
    flask_thread.start()

    print("✅ Starting server...")
    print("⏳ Waiting for server to initialize...")

    # Wait for Flask to start before launching the window
    time.sleep(2)  # 2-second pause gives Flask time to bind to port 5000 before the window tries to load it

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

    # Start the email scheduler (runs in background — stub mode until SMTP is configured)
    # To configure SMTP, open backend/email_notifications.py and fill in SMTP_CONFIG
    from email_notifications import start_scheduler
    start_scheduler()  # starts the APScheduler background thread for daily/weekly email jobs

    # Create the desktop window
    window = webview.create_window(
        title='מערכת מעקב וניהול בעיות - תכנון ופיתוח',
        url='http://127.0.0.1:5000',  # points the window at the local Flask server
        width=1600,
        height=900,
        resizable=True,
        fullscreen=False,
        min_size=(1200, 700),    # prevents the window from being resized smaller than this
        background_color='#667eea'  # purple background shown briefly while the page loads
    )

    # Start the GUI event loop
    webview.start(debug=False, http_server=False)
    # webview.start() blocks here and runs the GUI — when the window is closed this line returns and the app exits
    # http_server=False means pywebview doesn't start its own server — Flask is already handling that

if __name__ == '__main__':
    main()