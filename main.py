"""
Server Launcher for Event Management System
Starts the Flask server — connect via browser at http://YOUR_IP:5000
MULTI-USER VERSION - Allows network access for multiple users
"""

import sys        # built-in — lets us modify the Python module search path at runtime
import os         # built-in — used to build absolute file paths
import socket     # built-in — used to detect the machine's LAN IP address for display

# Add backend to path so we can import from the backend folder
sys.path.insert(0, 'backend')
from app import app  # imports the Flask app object from backend/app.py



def get_local_ip():
    """Detect the machine's LAN IP for display purposes."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))   # doesn't actually send data — just resolves the outbound interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "YOUR_IP_ADDRESS"


def start_flask_server():
    """Start Flask server — runs directly in the main thread (no desktop window needed)"""
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0    # tells Flask never to cache static files
    app.config['TEMPLATES_AUTO_RELOAD'] = True      # auto-reloads changed templates without restarting
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)


def main():
    print("=" * 50)
    print("  Event Management System - Multi-User Server")
    print("=" * 50)
    print()

    # Start Flask server (runs directly — no background thread needed without a GUI window)
    print("✅ Starting server...")
    print()

    local_ip = get_local_ip()

    print("📡 Server is accessible at:")
    print(f"   - Local: http://127.0.0.1:5000")
    print(f"   - Network: http://{local_ip}:5000")
    print()
    print("ℹ️  To find your IP address:")
    print("   - Windows: Run 'ipconfig' in CMD")
    print("   - Look for 'IPv4 Address'")
    print()
    print("🌐 Other users can connect by:")
    print(f"   1. Getting your IP address (e.g., {local_ip})")
    print("   2. Opening: http://YOUR_IP:5000 in their browser")
    print()
    print("=" * 50)
    print()

    # Start the email scheduler (runs in background)
    from email_notifications import start_scheduler
    start_scheduler()

    # Start the Flask server — blocks here until Ctrl+C
    start_flask_server()


if __name__ == '__main__':
    main()