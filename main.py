"""
Desktop Application Launcher for Event Management System
Opens the system in a standalone window (not browser)
MULTI-USER VERSION - Allows network access for multiple users
"""

import webview
import threading
import time
import sys
import os

# Add backend to path so we can import from the backend folder
sys.path.insert(0, 'backend')
from app import app

# Get the absolute path to the project directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def start_flask_server():
    """Start Flask server in background thread with network access"""
    # Disable Flask caching
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Run Flask with network access (0.0.0.0 allows other computers to connect)
    # threaded=True allows multiple users simultaneously
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)

def main():
    """Main function to launch desktop application"""

    print("=" * 50)
    print("  Event Management System - Multi-User Server")
    print("=" * 50)
    print()

    # Start Flask server in background thread
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
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

    # Start the email scheduler (runs in background — stub mode until SMTP is configured)
    # To configure SMTP, open backend/email_notifications.py and fill in SMTP_CONFIG
    from email_notifications import start_scheduler
    start_scheduler()

    # Create the desktop window
    window = webview.create_window(
        title='מערכת מעקב וניהול בעיות - תכנון ופיתוח',
        url='http://127.0.0.1:5000',
        width=1600,
        height=900,
        resizable=True,
        fullscreen=False,
        min_size=(1200, 700),
        background_color='#667eea'
    )

    # Start the GUI event loop
    webview.start(debug=False, http_server=False)

if __name__ == '__main__':
    main()