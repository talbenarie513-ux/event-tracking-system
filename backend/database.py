import sqlite3
import os

class Database:
    def __init__(self, db_path='event_system.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        return conn
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'planning', 'development')),
                email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Events table
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
        
        # Check and add missing columns
        cursor.execute("PRAGMA table_info(events)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'completion_date' not in columns:
            cursor.execute('ALTER TABLE events ADD COLUMN completion_date DATE')
            print("✅ Added completion_date column to events table")

        # *** MIGRATION: fix old status values to new names ***
        cursor.execute("UPDATE events SET status = 'הושלם הטיפול' WHERE status = 'טופל'")
        cursor.execute("UPDATE events SET status = 'בבדיקת תחום תכנון' WHERE status = 'בבדיקת תחנתכנון'")
        cursor.execute("UPDATE events SET status = 'בבדיקת תחום תכנון' WHERE status = 'בבדיקת תחנת תכנון'")

        # Event files table
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
        
        # Status history table
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

        # ── NEW: Audit log table — records every field change ────────────────
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
        
        # Email log table
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
        
        # Email list table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT,
                added_by TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Email notifications preferences table
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
        
        # Create default admin user if no users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO users (name, role, email)
                VALUES ('Admin', 'admin', 'admin@example.com')
            ''')
        
        conn.commit()
        self.populate_email_list()
        self.init_notification_rows()
        conn.close()
    
    def populate_email_list(self):
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

        