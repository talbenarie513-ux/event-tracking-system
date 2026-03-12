import sqlite3
conn = sqlite3.connect('backend/event_system.db')
c = conn.cursor()

# Try fetching it directly
c.execute("SELECT * FROM events WHERE id = -5")
row = c.fetchone()
print("Direct lookup:", row)

# Also check the raw min ID
c.execute("SELECT MIN(id) FROM events")
print("Minimum ID in DB:", c.fetchone())

conn.close()