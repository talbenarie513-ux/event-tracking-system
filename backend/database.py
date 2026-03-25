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

        # USERS TABLE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'planning', 'development')),
                email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # EVENTS TABLE
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

        # MIGRATION — add completion_date if missing
        cursor.execute("PRAGMA table_info(events)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'completion_date' not in columns:
            cursor.execute('ALTER TABLE events ADD COLUMN completion_date DATE')

        # DATA FIXES
        cursor.execute("UPDATE events SET status = 'הושלם הטיפול' WHERE status = 'טופל'")
        cursor.execute("UPDATE events SET status = 'בבדיקת תחום תכנון' WHERE status = 'בבדיקת תחנתכנון'")
        cursor.execute("UPDATE events SET status = 'בבדיקת תחום תכנון' WHERE status = 'בבדיקת תחנת תכנון'")

        # EVENT FILES TABLE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                display_name TEXT,                    -- user-supplied friendly name; falls back to original_filename if NULL
                file_path TEXT NOT NULL,
                uploaded_by TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        ''')

        # MIGRATION — add display_name to event_files if the column doesn't exist yet
        cursor.execute("PRAGMA table_info(event_files)")
        ef_cols = [col[1] for col in cursor.fetchall()]
        if 'display_name' not in ef_cols:
            cursor.execute("ALTER TABLE event_files ADD COLUMN display_name TEXT")

        # STATUS HISTORY TABLE
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

        # AUDIT LOG TABLE
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

        # EMAIL LOG TABLE
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

        # EMAIL LIST TABLE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT,
                added_by TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # EMAIL NOTIFICATIONS TABLE
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

        # EVENT COMMENTS TABLE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                comment_text TEXT NOT NULL,
                author TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        ''')

        # USER LAST SEEN TABLE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_last_seen (
                user_name TEXT PRIMARY KEY,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ═══════════════════════════════════════════════════════════
        # FIELD PERMISSIONS TABLE — per ROLE
        # Controls which fields each role (admin/planning/development)
        # can edit. This is the "global" baseline permission layer.
        # ═══════════════════════════════════════════════════════════
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS field_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                field_name TEXT NOT NULL,
                can_edit INTEGER DEFAULT 1,
                UNIQUE(role, field_name)
            )
        ''')

        cursor.execute('SELECT COUNT(*) FROM field_permissions')
        if cursor.fetchone()[0] == 0:
            self._seed_default_permissions(cursor)

        # ═══════════════════════════════════════════════════════════
        # USER FIELD PERMISSIONS TABLE — per USER
        # Optional per-user overrides on top of the role permissions.
        # If a row exists here for a user+field, it takes precedence
        # over the role-level permission when loading the form.
        # Admins are always unrestricted — no rows are seeded for them.
        # ═══════════════════════════════════════════════════════════
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_field_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                can_edit INTEGER DEFAULT 1,
                UNIQUE(user_id, field_name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # Seed user_field_permissions from role defaults for any existing
        # non-admin users that don't yet have per-user rows.
        self._seed_user_permissions_from_roles(cursor)

        # DEFAULT ADMIN USER — only on a fresh install
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

    def _seed_default_permissions(self, cursor):
        """
        Writes the default role-level permission matrix into field_permissions.
        Called once on first run when the table is empty.
        """
        all_fields = [
            'registrationDate', 'firstContactDate', 'system', 'systemOther',
            'eventSummary', 'eventDetails', 'affectedCustomers',
            'urgency', 'priority', 'status', 'statusDetails',
            'eventClassification', 'statusDeadline', 'completionDate',
            'responsiblePerson', 'responsiblePersonOther',
            'priceQuote', 'additionalNotes',
        ]

        planning_blocked = {
            'responsiblePerson', 'responsiblePersonOther',
            'status', 'statusDetails', 'completionDate', 'priceQuote',
        }

        development_allowed = {
            'status', 'statusDetails', 'completionDate',
            'responsiblePerson', 'responsiblePersonOther',
            'statusDeadline', 'priceQuote', 'additionalNotes', 'eventClassification',
        }

        rows = []
        for field in all_fields:
            rows.append(('admin', field, 1))
            rows.append(('planning', field, 0 if field in planning_blocked else 1))
            rows.append(('development', field, 1 if field in development_allowed else 0))

        cursor.executemany(
            'INSERT OR IGNORE INTO field_permissions (role, field_name, can_edit) VALUES (?, ?, ?)',
            rows
        )

    def _seed_user_permissions_from_roles(self, cursor):
        """
        For every non-admin user that has no rows yet in user_field_permissions,
        copies their role's defaults from field_permissions into user_field_permissions.
        This is called on every startup so newly added users get seeded automatically.
        """
        cursor.execute("SELECT id, role FROM users WHERE role != 'admin'")
        users = cursor.fetchall()
        for user_id, role in users:
            cursor.execute(
                'SELECT COUNT(*) FROM user_field_permissions WHERE user_id = ?',
                (user_id,)
            )
            if cursor.fetchone()[0] == 0:
                # no per-user rows yet — copy from role defaults
                cursor.execute(
                    'SELECT field_name, can_edit FROM field_permissions WHERE role = ?',
                    (role,)
                )
                role_perms = cursor.fetchall()
                cursor.executemany(
                    '''INSERT OR IGNORE INTO user_field_permissions (user_id, field_name, can_edit)
                       VALUES (?, ?, ?)''',
                    [(user_id, fn, ce) for fn, ce in role_perms]
                )

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

    def seed_new_user_permissions(self, user_id, role):
        """
        Called from app.py after a new non-admin user is created.
        Seeds user_field_permissions from the user's role defaults so the
        per-user table is immediately populated for that user.
        """
        if role == 'admin':
            return  # admins are always unrestricted — nothing to seed
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'SELECT field_name, can_edit FROM field_permissions WHERE role = ?',
                (role,)
            )
            role_perms = cursor.fetchall()
            cursor.executemany(
                '''INSERT OR IGNORE INTO user_field_permissions (user_id, field_name, can_edit)
                   VALUES (?, ?, ?)''',
                [(user_id, fn, ce) for fn, ce in role_perms]
            )
            conn.commit()
        except Exception as e:
            print(f"Error seeding user permissions: {e}")
        finally:
            conn.close()