import sqlite3  # built-in — handles all communication with the SQLite .db file
import os        # built-in — used for file path operations

class Database:
    # Central database manager — every other file imports and uses this class

    def __init__(self, db_path='event_system.db'):
        # Runs automatically on Database() — sets the db file path and calls init_database() immediately
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        # Opens a fresh connection to the SQLite file — ⚠️ always call conn.close() after use or the file stays locked
        conn = sqlite3.connect(self.db_path)
        return conn
    
    def init_database(self):
        # Creates all tables if they don't exist yet — safe to run multiple times on startup
        conn = self.get_connection()
        cursor = conn.cursor()  # cursor = the "pen" that executes SQL commands
        
        # USERS TABLE — stores name, role, email. Role is enforced by CHECK so invalid values are rejected at db level
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'planning', 'development')),
                email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # EVENTS TABLE — the main table. id has no AUTOINCREMENT so custom IDs can be assigned manually
        # CHECK constraints on urgency, priority, status mean the db itself rejects invalid values
        # is_deleted = soft delete flag (1 = deleted, 0 = active) — rows are never truly removed
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                registration_date DATE NOT NULL,
                first_contact_date DATE,
                system TEXT NOT NULL,
                event_summary TEXT NOT NULL,
                event_details TEXT NOT NULL,
                affected_customers TEXT NOT NULL,
                urgency TEXT NOT NULL CHECK(urgency IN ('קריטית', 'גבוהה', 'בינונית', 'נמוכה')),
                priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 10),
                status TEXT NOT NULL CHECK(status IN (
                    'אירוע חדש',
                    'בטיפול',
                    'בהכנת הצעת מחיר',
                    'בפיתוח',
                    'בבדיקת איכות של פיתוח',
                    'ממתין לאישור הצעת מחיר',
                    'בבדיקת תחום תכנון',
                    'הושלם הטיפול',
                    'בהקפאה',
                    'טופל חלקית'
                )),
                status_details TEXT,
                event_classification TEXT CHECK(event_classification IN ('', 'תקלה', 'פיתוח', 'שאלה', 'אחר')),
                status_deadline DATE NOT NULL,
                completion_date DATE,
                responsible_person TEXT,
                price_quote REAL,
                additional_notes TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        
        # MIGRATION — checks if completion_date column exists and adds it if missing (handles older db versions)
        cursor.execute("PRAGMA table_info(events)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'completion_date' not in columns:
            cursor.execute('ALTER TABLE events ADD COLUMN completion_date DATE')
            print("✅ Added completion_date column to events table")

        # DATA FIXES — renames old status values from previous versions to current names. Harmless if nothing matches
        cursor.execute("UPDATE events SET status = 'הושלם הטיפול' WHERE status = 'טופל'")
        cursor.execute("UPDATE events SET status = 'בבדיקת תחום תכנון' WHERE status = 'בבדיקת תחנתכנון'")
        cursor.execute("UPDATE events SET status = 'בבדיקת תחום תכנון' WHERE status = 'בבדיקת תחנת תכנון'")

        # EVENT FILES TABLE — stores metadata about uploaded files. Actual files live on disk in /uploads/{event_id}/
        # ON DELETE CASCADE means if an event is deleted, its file records are deleted too
        # ⚠️ but the physical files on disk are NOT auto-deleted — that's handled manually in app.py
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                uploaded_by TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        ''')
        
        # STATUS HISTORY TABLE — records every status change over time for an event
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                changed_by TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        ''')

        # AUDIT LOG TABLE — records every single field change (who changed what, from what value, to what value)
        # This is what powers the history modal in the frontend
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                field_name TEXT,
                old_value TEXT,
                new_value TEXT,
                changed_by TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        ''')
        
        # EMAIL LOG TABLE — meant to log sent emails. Created but not heavily used in current code
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        ''')
        
        # EMAIL LIST TABLE — list of email addresses that receive notifications
        # UNIQUE on email prevents duplicates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT,
                added_by TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # EMAIL NOTIFICATIONS TABLE — stores per-user notification preferences (0 = off, 1 = on)
        # One row per user, UNIQUE on user_id prevents duplicates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                notify_status_change INTEGER DEFAULT 0,
                notify_weekly_report INTEGER DEFAULT 0,
                notify_new_event INTEGER DEFAULT 0,
                notify_responsible INTEGER DEFAULT 0,
                notify_overdue INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # DEFAULT ADMIN — if no users exist at all (fresh install), creates a default admin so the app isn't empty
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO users (name, role, email)
                VALUES ('Admin', 'admin', 'admin@example.com')
            ''')
        
        conn.commit()  # saves all the above changes to disk
        self.populate_email_list()   # auto-syncs user emails into the email_list table
        self.init_notification_rows() # ensures every user has a notification preferences row
        conn.close()
    
    def populate_email_list(self):
        # Copies all user emails into email_list so they appear in notification settings
        # INSERT OR IGNORE means existing emails are skipped — no duplicates
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT DISTINCT email, name FROM users WHERE email IS NOT NULL AND email != ""')
            existing_emails = cursor.fetchall()
            for email, name in existing_emails:
                cursor.execute('''
                    INSERT OR IGNORE INTO email_list (email, name, added_by)
                    VALUES (?, ?, ?)
                ''', (email, name, 'System'))
            conn.commit()
        except Exception as e:
            print(f"Error populating email list: {e}")
        finally:
            conn.close()

    def init_notification_rows(self):
        # Creates a notification preferences row for every user that doesn't have one yet
        # Without this, checking preferences for a new user would crash — no row to read
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT id FROM users')
            user_ids = cursor.fetchall()
            for (uid,) in user_ids:
                cursor.execute('''
                    INSERT OR IGNORE INTO email_notifications (user_id)
                    VALUES (?)
                ''', (uid,))
            conn.commit()
        except Exception as e:
            print(f"Error initializing notification rows: {e}")
        finally:
            conn.close()