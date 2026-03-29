# ============================================================
# app.py — Flask REST API for the Event Management System
# This file defines every HTTP endpoint the frontend calls.
# It runs on the server machine and is started by main.py.
# All data lives in event_system.db (SQLite) managed by database.py.
# ============================================================

from flask import Flask, request, jsonify, send_file, send_from_directory, make_response
from flask_cors import CORS          # allows cross-origin requests (needed when the
                                     # frontend runs on a different origin, e.g. file://)
from database import Database        # our SQLite manager — handles connections & table setup
import os
import mimetypes                     # guesses MIME type from file extension (e.g. .pdf → application/pdf)
import base64                        # encodes binary file data as a string for JSON responses
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename  # sanitises uploaded filenames to prevent path traversal attacks

# email trigger functions — imported here so they can be called from event routes
from email_notifications import (
    trigger_new_event,
    trigger_status_change,
    trigger_responsible_assigned,
    trigger_event_changed,
)

app = Flask(__name__)
CORS(app)  # enable Cross-Origin Resource Sharing for all routes

# ── CACHE-BUSTING RESPONSE HEADER ────────────────────────────────────────────

@app.after_request
def add_header(response):
    """
    Adds no-cache headers to EVERY response.
    Prevents the browser / pywebview from serving stale data
    when the user re-opens the same URL after data has changed.
    """
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma']  = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # also disable Flask's own file caching

# statuses that mean an event is "closed" — used to exclude them from overdue queries
CLOSED_STATUSES = ('הושלם הטיפול', 'טופל חלקית', 'בהקפאה')

# absolute path to the directory this file lives in — used to build safe file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_next_available_id(cursor):
    """
    Returns the next integer ID to use for a new event.
    Uses MAX(id)+1 rather than SQLite's AUTOINCREMENT because event IDs
    are manually assignable (users can specify a custom ID when creating).
    ⚠️ Race condition risk: two simultaneous creates could get the same ID.
    In practice this is rare with a small team, but worth noting.
    """
    cursor.execute('SELECT MAX(id) FROM events')
    max_id = cursor.fetchone()[0]
    return (max_id + 1) if max_id else 1

# single shared Database instance — reused across all requests in this process
db = Database()

# where uploaded files are saved on disk
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

# whitelist of allowed file extensions — requests with other extensions are rejected
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'doc', 'docx', 'pdf', 'png', 'jpg', 'jpeg',
                      'msg', 'shp', 'zip', 'eml', 'csv', 'txt', 'gif', 'webp', 'svg'}

# create the uploads directory if it doesn't exist yet
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """
    Returns True if the filename has an extension in the allowed list.
    '.' in filename guard prevents files with no extension from passing.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def resolve_file_path(stored_path):
    """
    Attempts to find a file on disk even if the stored path is relative,
    uses backslashes, or was saved on a different machine.
    
    Tries four strategies in order:
    1. Absolute path as stored — works if the path is already correct.
    2. Joined with BASE_DIR — handles relative paths.
    3. Normalised (backslash → forward slash, leading slash stripped).
    4. Path from the 'uploads/' segment onwards — handles moved installations.
    
    Returns the stored_path unchanged if none of the strategies found the file;
    the caller is responsible for checking whether the file actually exists.
    """
    if os.path.exists(stored_path):
        return stored_path
    candidate = os.path.join(BASE_DIR, stored_path)
    if os.path.exists(candidate):
        return candidate
    normalised = stored_path.replace('\\', '/').lstrip('/')
    candidate2 = os.path.join(BASE_DIR, normalised)
    if os.path.exists(candidate2):
        return candidate2
    candidate3 = os.path.join(os.getcwd(), normalised)
    if os.path.exists(candidate3):
        return candidate3
    # extract everything after 'uploads/' and look in the current UPLOAD_FOLDER
    parts = normalised.replace('\\', '/').split('uploads/', 1)
    if len(parts) == 2:
        candidate4 = os.path.join(UPLOAD_FOLDER, parts[1])
        if os.path.exists(candidate4):
            return candidate4
    return stored_path  # give up — caller will get a 404

def row_to_event(row):
    """
    Converts a raw SQLite row tuple (from SELECT * FROM events) into a
    Python dict with named keys. All API responses use this function so
    there is a single source of truth for the field order.
    
    Column order must match the events table definition in database.py:
    id, registration_date, first_contact_date, system, event_summary,
    event_details, affected_customers, urgency, priority, status,
    status_details, event_classification, status_deadline, completion_date,
    responsible_person, price_quote, additional_notes, created_by,
    created_at, updated_at, is_deleted
    """
    return {
        'id':                   row[0],
        'registration_date':    row[1],
        'first_contact_date':   row[2],
        'system':               row[3],
        'event_summary':        row[4],
        'event_details':        row[5],
        'affected_customers':   row[6],
        'urgency':              row[7],
        'priority':             row[8],
        'status':               row[9],
        'status_details':       row[10],
        'event_classification': row[11],
        'status_deadline':      row[12],
        'completion_date':      row[13],
        'responsible_person':   row[14],
        'price_quote':          row[15],
        'additional_notes':     row[16],
        'created_by':           row[17],
        'created_at':           row[18],
        'updated_at':           row[19],
        'is_deleted':           row[20],
    }

# Maps database column names to human-readable Hebrew labels.
# Used when building the audit log entries so the history timeline
# shows field names the user understands rather than snake_case keys.
FIELD_LABELS = {
    'registration_date':    'תאריך רישום',
    'first_contact_date':   'תאריך פנייה ראשונה',
    'system':               'מערכת',
    'event_summary':        'תמצית האירוע',
    'event_details':        'פירוט האירוע',
    'affected_customers':   'לקוחות מושפעים',
    'urgency':              'דחיפות',
    'priority':             'עדיפות',
    'status':               'סטטוס',
    'status_details':       'פירוט סטטוס',
    'event_classification': 'סיווג האירוע',
    'status_deadline':      'לו"ז',
    'completion_date':      'תאריך השלמה',
    'responsible_person':   'גורם אחראי',
    'price_quote':          'הצעת מחיר',
    'additional_notes':     'הערות נוספות',
    'file':                 'קובץ מצורף',
    'comment':              'הערה',
}

def log_audit(cursor, event_id, action, changed_by, changes=None):
    """
    Writes one or more rows to the audit_log table.

    For simple actions (created / deleted / restored) — inserts a single row
    with no field detail (field_name, old_value, new_value are NULL).

    For field-level changes (updated / file_uploaded) — inserts one row per
    changed field, storing the old and new values so the history timeline can
    show exactly what changed.

    Parameters:
        cursor     — active SQLite cursor (caller manages the connection/commit).
        event_id   — the event this log entry belongs to.
        action     — 'created' | 'updated' | 'deleted' | 'restored' | 'file_uploaded'
        changed_by — the username who made the change.
        changes    — dict of { field_name: (old_value, new_value) } for 'updated' actions.
                     None for simple actions.
    """
    if action in ('created', 'deleted', 'restored') or not changes:
        cursor.execute('''
            INSERT INTO audit_log (event_id, action, changed_by)
            VALUES (?, ?, ?)
        ''', (event_id, action, changed_by))
    else:
        # insert one row per changed field
        for field, (old_val, new_val) in changes.items():
            cursor.execute('''
                INSERT INTO audit_log (event_id, action, field_name, old_value, new_value, changed_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (event_id, action, field,
                  str(old_val) if old_val is not None else '',
                  str(new_val) if new_val is not None else '',
                  changed_by))

# parent directory of backend/ — where index.html and app.js live
ROOT_DIR = os.path.dirname(BASE_DIR)

# ── STATIC FILE SERVING ───────────────────────────────────────────────────────

@app.route('/')
def serve_index():
    """Serves the main HTML file from the root directory."""
    return send_from_directory(ROOT_DIR, 'index.html')

@app.route('/app.js')
def serve_js():
    """Serves the frontend JavaScript from the root directory."""
    return send_from_directory(ROOT_DIR, 'app.js')

# ══════════════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════════════

@app.route('/api/users', methods=['GET'])
def get_users():
    """
    Returns all users ordered by name.
    Used to populate the login dropdown and the responsible-person dropdown.
    Response: [ { id, name, role, email }, ... ]
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, role, email FROM users ORDER BY name')
    users = [{'id': r[0], 'name': r[1], 'role': r[2], 'email': r[3]} for r in cursor.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
def add_user():
    """
    Creates a new user.
    Also:
     - Adds the user's email to the email distribution list (email_list table).
     - Creates an empty email_notifications row for the user.
     - Seeds per-user field permissions from the role defaults (via db.seed_new_user_permissions).
    
    Request body: { name, role, email }
    Response: { success, message }
    """
    data = request.json
    if not data.get('email'):
        return jsonify({'success': False, 'error': 'אימייל הוא שדה חובה'}), 400
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (name, role, email) VALUES (?, ?, ?)',
                       (data['name'], data['role'], data['email']))
        user_id = cursor.lastrowid  # get the auto-assigned ID of the new user
        # add to distribution list (INSERT OR IGNORE avoids duplicate-email errors)
        cursor.execute('INSERT OR IGNORE INTO email_list (email, name, added_by) VALUES (?, ?, ?)',
                       (data['email'], data['name'], 'System'))
        # create notification preference row (all off by default)
        cursor.execute('INSERT OR IGNORE INTO email_notifications (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()
        # seed per-user permissions AFTER committing (opens a fresh connection internally)
        db.seed_new_user_permissions(user_id, data['role'])
        return jsonify({'success': True, 'message': 'המשתמש נוסף בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """
    Updates an existing user's name, role, and email.
    Side effects of a name change:
     - Updates events.responsible_person to the new name.
     - Updates events.created_by to the new name.
     - Updates all audit_log.changed_by entries.
     - Updates audit_log old/new values where they reference the old name.
     - Updates status_history.changed_by.
     - Updates event_comments.author.
    This keeps the data consistent when a user is renamed.
    
    If the role changes and the user has no per-user permission overrides yet,
    seeds fresh permissions from the new role's defaults.
    
    Request body: { name, role, email }
    Response: { success, message }
    """
    data = request.json
    if not data.get('email'):
        return jsonify({'success': False, 'error': 'אימייל הוא שדה חובה'}), 400
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        # read the current values so we can detect changes
        cursor.execute('SELECT name, email, role FROM users WHERE id = ?', (user_id,))
        old = cursor.fetchone()
        old_name  = old[0] if old else None
        old_email = old[1] if old else None
        old_role  = old[2] if old else None
        new_name  = data['name']
        new_email = data['email']
        new_role  = data['role']

        cursor.execute('UPDATE users SET name = ?, role = ?, email = ? WHERE id = ?',
                       (new_name, new_role, new_email, user_id))

        # keep email_list in sync with the user's email
        if old_email:
            cursor.execute('UPDATE email_list SET email = ?, name = ? WHERE email = ?',
                           (new_email, new_name, old_email))

        # propagate a name change to all tables that store the username as text
        if old_name and old_name != new_name:
            cursor.execute('UPDATE events SET responsible_person = ? WHERE responsible_person = ?',
                           (new_name, old_name))
            cursor.execute('UPDATE events SET created_by = ? WHERE created_by = ?',
                           (new_name, old_name))
            cursor.execute('UPDATE audit_log SET changed_by = ? WHERE changed_by = ?',
                           (new_name, old_name))
            cursor.execute('''UPDATE audit_log SET old_value = ?
                              WHERE field_name = 'responsible_person' AND old_value = ?''',
                           (new_name, old_name))
            cursor.execute('''UPDATE audit_log SET new_value = ?
                              WHERE field_name = 'responsible_person' AND new_value = ?''',
                           (new_name, old_name))
            cursor.execute('UPDATE status_history SET changed_by = ? WHERE changed_by = ?',
                           (new_name, old_name))
            cursor.execute('UPDATE event_comments SET author = ? WHERE author = ?',
                           (new_name, old_name))

        # if role changed and no per-user overrides exist yet, seed from new role defaults
        if old_role and old_role != new_role and new_role != 'admin':
            cursor.execute(
                'SELECT COUNT(*) FROM user_field_permissions WHERE user_id = ?', (user_id,)
            )
            existing_count = cursor.fetchone()[0]
            if existing_count == 0:
                conn.commit()
                conn.close()
                db.seed_new_user_permissions(user_id, new_role)
                return jsonify({'success': True, 'message': 'המשתמש עודכן בהצלחה'})

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'המשתמש עודכן בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """
    Deletes a user by ID.
    ⚠️ Does NOT cascade to events — the user's name remains in responsible_person
    fields. This is intentional so the event history is not destroyed.
    Response: { success, message }
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'המשתמש נמחק בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════
# EVENTS — LIST
# ══════════════════════════════════════════════════════════════════

@app.route('/api/events', methods=['GET'])
def get_events():
    """
    Returns a filtered list of events.

    Query parameters (all optional):
      show_deleted=true  — include soft-deleted rows (is_deleted = 1)
      status=<value>     — filter by exact status
      urgency=<value>    — filter by exact urgency
      search=<text>      — partial match on summary, system, and details

    Default behaviour (no params): returns all non-deleted events, newest first.
    Response: [ event_dict, ... ]
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    show_deleted   = request.args.get('show_deleted', 'false').lower() == 'true'
    status_filter  = request.args.get('status')
    urgency_filter = request.args.get('urgency')
    search         = request.args.get('search', '').strip()

    query  = 'SELECT * FROM events WHERE id > 0'  # id > 0 excludes any sentinel/placeholder rows
    params = []

    if not show_deleted:
        query += ' AND (is_deleted = 0 OR is_deleted IS NULL)'
    if status_filter:
        query += ' AND status = ?'
        params.append(status_filter)
    if urgency_filter:
        query += ' AND urgency = ?'
        params.append(urgency_filter)
    if search:
        # search across three text fields simultaneously
        query += ' AND (event_summary LIKE ? OR system LIKE ? OR event_details LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])

    query += ' ORDER BY id DESC'  # newest IDs first
    cursor.execute(query, params)
    events = [row_to_event(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(events)

# ══════════════════════════════════════════════════════════════════
# EVENTS — SINGLE
# ══════════════════════════════════════════════════════════════════

@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    """
    Returns a single event by ID, including its attached files.
    The files array contains metadata only (no file content) — each file
    has its own /api/files/<id>/view and /api/files/<id>/download endpoints.
    Response: event_dict + { files: [ { id, original_filename, ... } ] }
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Event not found'}), 404
    event = row_to_event(row)
    # attach the file list to the event dict
    cursor.execute('''
        SELECT id, original_filename, file_path, uploaded_by, uploaded_at
        FROM event_files WHERE event_id = ?
    ''', (event_id,))
    event['files'] = [
        {'id': r[0], 'original_filename': r[1], 'file_path': r[2],
         'uploaded_by': r[3], 'uploaded_at': r[4]}
        for r in cursor.fetchall()
    ]
    conn.close()
    return jsonify(event)

# ══════════════════════════════════════════════════════════════════
# EVENTS — HISTORY (AUDIT LOG)
# ══════════════════════════════════════════════════════════════════

@app.route('/api/events/<int:event_id>/history', methods=['GET'])
def get_event_history(event_id):
    """
    Returns the full audit trail for an event.
    
    Response structure:
    {
      event_id, created_by, created_at,
      entries: [
        { action, field_name, field_label, old_value, new_value, changed_by, changed_at },
        ...
      ]
    }
    
    The frontend groups consecutive 'updated' entries with the same
    changed_by + changed_at into a single timeline card.
    field_label is the Hebrew display name from FIELD_LABELS.
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT created_by, created_at FROM events WHERE id = ?', (event_id,))
    event_row = cursor.fetchone()
    if not event_row:
        conn.close()
        return jsonify({'error': 'Event not found'}), 404

    cursor.execute('''
        SELECT action, field_name, old_value, new_value, changed_by, changed_at
        FROM audit_log WHERE event_id = ? ORDER BY changed_at ASC
    ''', (event_id,))

    entries = []
    for r in cursor.fetchall():
        entries.append({
            'action':      r[0],
            'field_name':  r[1],
            'field_label': FIELD_LABELS.get(r[1], r[1]) if r[1] else None,
            'old_value':   r[2],
            'new_value':   r[3],
            'changed_by':  r[4],
            'changed_at':  r[5],
        })

    conn.close()
    return jsonify({
        'event_id':   event_id,
        'created_by': event_row[0],
        'created_at': event_row[1],
        'entries':    entries,
    })

# ══════════════════════════════════════════════════════════════════
# EVENTS — CREATE
# ══════════════════════════════════════════════════════════════════

@app.route('/api/events', methods=['POST'])
def create_event():
    """
    Creates a new event.

    Request body: event fields dict (see eventData in app.js handleEventSubmit).
    
    Key behaviours:
    - Validates priority (1–10) and price_quote (≥ 0).
    - Accepts an optional event_id for manual ID assignment; generates one
      automatically via get_next_available_id() if omitted.
    - Admin users get relaxed required-field enforcement (defaults are used
      for any missing field so the form can be saved partially).
    - Sets completion_date automatically when status is 'הושלם הטיפול'.
    - Inserts an initial status_history row and an audit_log 'created' row.
    - Triggers email notifications (new event, responsible person assigned).
    
    Response: { success, message, event_id }
    """
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'לא התקבלו נתונים'}), 400

    user_role = data.get('user_role', '')

    # ── validate priority ──
    priority = data.get('priority')
    if priority is not None:
        try:
            priority = int(priority)
            if priority < 1 or priority > 10:
                return jsonify({'success': False, 'error': 'עדיפות חייבת להיות בין 1 ל-10'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'ערך עדיפות לא תקין'}), 400

    # ── validate price_quote ──
    price_quote = data.get('price_quote')
    if price_quote is not None and price_quote != '':
        try:
            price_quote = float(price_quote)
            if price_quote < 0:
                return jsonify({'success': False, 'error': 'הצעת מחיר לא יכולה להיות שלילית'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'ערך הצעת מחיר לא תקין'}), 400
    else:
        price_quote = None

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        # ── resolve event ID ──
        event_id = data.get('event_id')
        if event_id:
            try:
                event_id = int(event_id)
                if event_id < 1:
                    conn.close()
                    return jsonify({'success': False, 'error': 'מספר אירוע חייב להיות חיובי'}), 400
            except (ValueError, TypeError):
                conn.close()
                return jsonify({'success': False, 'error': 'מספר אירוע לא תקין'}), 400
            # check for duplicate ID
            cursor.execute('SELECT id FROM events WHERE id = ?', (event_id,))
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': f'מספר אירוע {event_id} כבר קיים במערכת'}), 400
        else:
            event_id = get_next_available_id(cursor)  # auto-assign

        # ── field values (admin mode allows empty required fields) ──
        if user_role == 'admin':
            # provide sensible defaults for any missing field so admin can save partial events
            registration_date  = data.get('registration_date') or datetime.now().strftime('%Y-%m-%d')
            system             = data.get('system') or 'לא צוין'
            event_summary      = data.get('event_summary') or f'אירוע #{event_id}'
            event_details      = data.get('event_details') or ''
            affected_customers = data.get('affected_customers') or 'לא צוין'
            urgency            = data.get('urgency') or 'בינונית'
            priority           = priority or 5
            status             = data.get('status') or 'אירוע חדש'
            status_deadline    = data.get('status_deadline') or (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        else:
            # non-admin: use values as-is (HTML5 required validation should have caught empties)
            registration_date  = data.get('registration_date', '')
            system             = data.get('system', '')
            event_summary      = data.get('event_summary', '')
            event_details      = data.get('event_details', '')
            affected_customers = data.get('affected_customers', '')
            urgency            = data.get('urgency', 'בינונית')
            priority           = priority if priority is not None else int(data.get('priority', 5))
            status             = data.get('status', 'אירוע חדש')
            status_deadline    = data.get('status_deadline', '')

        # ── completion date logic ──
        completion_date = None
        if status == 'הושלם הטיפול':
            completion_date = data.get('completion_date') or datetime.now().strftime('%Y-%m-%d')

        created_by = data.get('created_by', 'Unknown')

        cursor.execute('''
            INSERT INTO events (
                id, registration_date, first_contact_date, system, event_summary,
                event_details, affected_customers, urgency, priority, status,
                status_details, event_classification, status_deadline, completion_date,
                responsible_person, price_quote, additional_notes, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event_id, registration_date, data.get('first_contact_date'), system,
            event_summary, event_details, affected_customers, urgency, priority, status,
            data.get('status_details', ''), data.get('event_classification', ''),
            status_deadline, completion_date,
            data.get('responsible_person', ''), price_quote,
            data.get('additional_notes', ''), created_by
        ))

        # record initial status in status_history
        cursor.execute('INSERT INTO status_history (event_id, status, changed_by) VALUES (?, ?, ?)',
                       (event_id, status, created_by))
        # record creation in audit_log
        log_audit(cursor, event_id, 'created', created_by)
        conn.commit()
        conn.close()

        # ── trigger email notifications ──
        # build a minimal event dict for the notification functions
        full_event = {
            "id": event_id, "system": system, "event_summary": event_summary,
            "event_details": event_details, "affected_customers": affected_customers,
            "urgency": urgency, "priority": priority, "status": status,
            "status_deadline": status_deadline, "registration_date": registration_date,
            "responsible_person": data.get("responsible_person", ""),
            "status_details": data.get("status_details", ""),
        }
        try:
            trigger_new_event(full_event, created_by)
            if data.get("responsible_person"):
                trigger_responsible_assigned(full_event, "", created_by)
        except Exception:
            pass  # email errors must not fail the API response

        return jsonify({'success': True, 'message': 'האירוע נוצר בהצלחה', 'event_id': event_id})

    except Exception as e:
        conn.close()
        print(f"Error creating event: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════
# EVENTS — UPDATE
# ══════════════════════════════════════════════════════════════════

@app.route('/api/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    """
    Updates an existing event.

    Key behaviours:
    - Validates priority and price_quote.
    - Allows the event ID itself to be changed (event_id in the body),
      with a duplicate-check.
    - Automatically sets completion_date when status becomes 'הושלם הטיפול'.
    - Compares old vs new values for every field and writes only changed
      fields to audit_log (so the history shows exactly what changed).
    - Adds a status_history row when the status changes.
    - Triggers email notifications for status changes and responsible person changes.
    
    Request body: event fields dict + updated_by.
    Response: { success, message }
    """
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'לא התקבלו נתונים'}), 400

    # ── validate priority ──
    priority = data.get('priority')
    if priority is not None:
        try:
            priority = int(priority)
            if priority < 1 or priority > 10:
                return jsonify({'success': False, 'error': 'עדיפות חייבת להיות בין 1 ל-10'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'ערך עדיפות לא תקין'}), 400

    # ── validate price_quote ──
    price_quote = data.get('price_quote')
    if price_quote is not None and price_quote != '':
        try:
            price_quote = float(price_quote)
            if price_quote < 0:
                return jsonify({'success': False, 'error': 'הצעת מחיר לא יכולה להיות שלילית'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'ערך הצעת מחיר לא תקין'}), 400
    else:
        price_quote = None

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        # load the current row so we can diff old vs new values for the audit log
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        old_row = cursor.fetchone()
        if not old_row:
            conn.close()
            return jsonify({'success': False, 'error': 'Event not found'}), 404

        old             = row_to_event(old_row)
        old_status      = old['status']
        old_id          = old['id']
        old_responsible = old['responsible_person']

        # ── resolve new ID (may have been changed in the form) ──
        new_id = data.get('event_id', old_id)
        if new_id is None:
            new_id = old_id
        try:
            new_id = int(new_id)
            if new_id < 1:
                conn.close()
                return jsonify({'success': False, 'error': 'מספר אירוע חייב להיות חיובי'}), 400
        except (ValueError, TypeError):
            new_id = old_id

        if new_id != old_id:
            # check that the new ID isn't already taken by a different event
            cursor.execute('SELECT id FROM events WHERE id = ? AND id != ?', (new_id, old_id))
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': f'מספר אירוע {new_id} כבר קיים במערכת'}), 400

        new_status = data.get('status', old_status)
        completion_date = data.get('completion_date')

        # auto-set/clear completion date based on status
        if new_status == 'הושלם הטיפול' and not completion_date:
            completion_date = datetime.now().strftime('%Y-%m-%d')
        elif new_status != 'הושלם הטיפול':
            completion_date = None  # clear it if status moved away from "completed"

        updated_by = data.get('updated_by') or data.get('created_by') or 'Unknown'

        cursor.execute('''
            UPDATE events SET
                id = ?, registration_date = ?, first_contact_date = ?, system = ?,
                event_summary = ?, event_details = ?, affected_customers = ?,
                urgency = ?, priority = ?, status = ?, status_details = ?,
                event_classification = ?, status_deadline = ?, completion_date = ?,
                responsible_person = ?, price_quote = ?, additional_notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            new_id,
            data.get('registration_date',    old.get('registration_date')),
            data.get('first_contact_date',   old.get('first_contact_date')),
            data.get('system',               old.get('system')),
            data.get('event_summary',        old.get('event_summary')),
            data.get('event_details',        old.get('event_details')),
            data.get('affected_customers',   old.get('affected_customers')),
            data.get('urgency',              old.get('urgency')),
            priority if priority is not None else data.get('priority', old.get('priority')),
            new_status,
            data.get('status_details',       old.get('status_details', '')),
            data.get('event_classification', old.get('event_classification', '')),
            data.get('status_deadline',      old.get('status_deadline')),
            completion_date,
            data.get('responsible_person',   old.get('responsible_person', '')),
            price_quote,
            data.get('additional_notes',     old.get('additional_notes', '')),
            event_id  # WHERE clause uses the OLD id (before any rename)
        ))

        # record status change in history table (separate from audit_log)
        if new_status != old_status:
            cursor.execute('INSERT INTO status_history (event_id, status, changed_by) VALUES (?, ?, ?)',
                           (new_id, new_status, updated_by))

        def _s(v):
            """Normalises a value to a stripped string for comparison."""
            return str(v).strip() if v is not None else ''

        # build a dict of every new value keyed by field name
        new_data = {
            'registration_date':    data.get('registration_date'),
            'first_contact_date':   data.get('first_contact_date'),
            'system':               data.get('system'),
            'event_summary':        data.get('event_summary'),
            'event_details':        data.get('event_details'),
            'affected_customers':   data.get('affected_customers'),
            'urgency':              data.get('urgency'),
            'priority':             priority if priority is not None else data.get('priority'),
            'status':               new_status,
            'status_details':       data.get('status_details', ''),
            'event_classification': data.get('event_classification', ''),
            'status_deadline':      data.get('status_deadline'),
            'completion_date':      completion_date,
            'responsible_person':   data.get('responsible_person', ''),
            'price_quote':          price_quote,
            'additional_notes':     data.get('additional_notes', ''),
        }

        # find fields that actually changed and build the changes dict for audit_log
        changes = {}
        for field, new_val in new_data.items():
            old_val_str = _s(old.get(field))
            new_val_str = _s(new_val)
            if old_val_str != new_val_str:
                changes[field] = (old_val_str, new_val_str)

        if changes:
            log_audit(cursor, new_id, 'updated', updated_by, changes)

        conn.commit()

        # ── trigger email notifications ──
        # open a second connection because conn is still open during the trigger calls
        try:
            conn2 = db.get_connection()
            cur2  = conn2.cursor()
            cur2.execute("SELECT * FROM events WHERE id = ?", (new_id,))
            updated_row = cur2.fetchone()
            conn2.close()

            if updated_row:
                updated_event = row_to_event(updated_row)
                if new_status != old_status:
                    # status change: notifies notify_status_change subscribers + responsible person
                    trigger_status_change(updated_event, old_status, updated_by)
                elif changes:
                    # non-status field changes: notify only the responsible person directly
                    # (notify_responsible subscribers only get the assignment email, not ongoing changes)
                    trigger_event_changed(updated_event, changes, updated_by)
                new_responsible = data.get("responsible_person", "")
                if new_responsible != (old_responsible or ""):
                    # responsible person changed: notify the new person + notify_responsible subscribers
                    trigger_responsible_assigned(updated_event, old_responsible or "", updated_by)
        except Exception:
            pass  # notification failure must not fail the API response

        conn.close()
        return jsonify({'success': True, 'message': 'האירוע עודכן בהצלחה'})

    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        print(f"Error updating event {event_id}: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════
# EVENTS — DELETE / RESTORE
# ══════════════════════════════════════════════════════════════════

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    """
    Soft-deletes an event by setting is_deleted = 1.
    The row stays in the database and can be restored via the restore endpoint.
    Also writes a 'deleted' entry to the audit_log.
    
    The changed_by value is read from the JSON body; falls back to created_by
    or 'System' if the body is empty.
    
    Response: { success, message }
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        # only soft-delete if the event exists and isn't already deleted
        cursor.execute(
            'SELECT id, created_by FROM events WHERE id = ? AND (is_deleted = 0 OR is_deleted IS NULL)',
            (event_id,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'האירוע לא נמצא או כבר נמחק'}), 404

        cursor.execute(
            'UPDATE events SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (event_id,)
        )
        try:
            body = request.get_json(silent=True) or {}
            changed_by = body.get('changed_by') or row[1] or 'System'
        except Exception:
            changed_by = row[1] or 'System'

        log_audit(cursor, event_id, 'deleted', changed_by)
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'האירוע נמחק בהצלחה'})
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        print(f"Error deleting event {event_id}: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events/<int:event_id>/restore', methods=['PUT'])
def restore_event(event_id):
    """
    Restores a soft-deleted event by setting is_deleted = 0.
    Also writes a 'restored' entry to the audit_log.
    Response: { success, message }
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM events WHERE id = ? AND is_deleted = 1', (event_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'האירוע לא נמצא או אינו במצב מחוק'}), 404

        cursor.execute(
            'UPDATE events SET is_deleted = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (event_id,)
        )
        log_audit(cursor, event_id, 'restored', 'System')
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'האירוע שוחזר בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════
# FILES — UPLOAD
# ══════════════════════════════════════════════════════════════════

@app.route('/api/events/<int:event_id>/files', methods=['POST'])
def upload_file(event_id):
    """
    Accepts a multipart/form-data upload and saves the file to:
    backend/uploads/<event_id>/<timestamp>_<secure_filename>
    
    secure_filename() strips path separators and other dangerous characters
    from the original filename to prevent directory traversal attacks.
    The timestamp prefix ensures uniqueness even if the same filename
    is uploaded twice.
    
    Also inserts a row into event_files and writes a 'file_uploaded'
    entry to the audit_log.
    
    Form fields: file (the file), uploaded_by (username string).
    Response: { success, message, file_id, filename }
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'File type not allowed'}), 400

    # create per-event subdirectory if it doesn't exist
    event_folder = os.path.join(UPLOAD_FOLDER, str(event_id))
    if not os.path.exists(event_folder):
        os.makedirs(event_folder)

    timestamp  = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename   = secure_filename(file.filename)
    # store as a relative path (relative to BASE_DIR) so moving the install doesn't break lookups
    rel_path   = os.path.join('uploads', str(event_id), f"{timestamp}_{filename}")
    abs_path   = os.path.join(BASE_DIR, rel_path)
    file.save(abs_path)

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        display_name = request.form.get('display_name', '').strip() or filename
        cursor.execute('''
            INSERT INTO event_files (event_id, original_filename, file_path, uploaded_by, display_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (event_id, filename, rel_path, request.form.get('uploaded_by', 'Unknown'), display_name))
        file_id     = cursor.lastrowid
        uploaded_by = request.form.get('uploaded_by', 'Unknown')
        # log file upload in audit_log using the 'file' field key with old='' and new=filename
        log_audit(cursor, event_id, 'file_uploaded', uploaded_by, changes={'file': ('', filename)})
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'הקובץ הועלה בהצלחה', 'file_id': file_id, 'filename': filename})
    except Exception as e:
        conn.close()
        if os.path.exists(abs_path):
            os.remove(abs_path)  # clean up the saved file if the DB insert failed
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events/<int:event_id>/files', methods=['GET'])
def get_event_files(event_id):
    """
    Returns metadata for all files attached to an event, newest first.
    Response: [ { id, original_filename, file_path, uploaded_by, uploaded_at }, ... ]
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, original_filename, file_path, uploaded_by, uploaded_at
        FROM event_files WHERE event_id = ? ORDER BY uploaded_at DESC
    ''', (event_id,))
    files = [{'id': r[0], 'original_filename': r[1], 'file_path': r[2],
              'uploaded_by': r[3], 'uploaded_at': r[4]} for r in cursor.fetchall()]
    conn.close()
    return jsonify(files)

# ══════════════════════════════════════════════════════════════════
# FILES — DOWNLOAD
# ══════════════════════════════════════════════════════════════════

@app.route('/api/files/<int:file_id>', methods=['GET'])
def download_file(file_id):
    """
    Legacy download endpoint — sends the file as an attachment.
    The frontend now uses /download (below) which returns raw bytes
    for blob URL creation. This endpoint remains for compatibility.
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT original_filename, file_path FROM event_files WHERE id = ?', (file_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'File not found'}), 404
    file_path = resolve_file_path(row[1])
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found on disk'}), 404
    return send_file(file_path, as_attachment=True, download_name=row[0])

@app.route('/api/files/<int:file_id>/download', methods=['GET'])
def download_file_blob(file_id):
    """
    Downloads a file as raw binary with the correct Content-Type and
    Content-Disposition headers.
    Used by the frontend to create a blob URL for in-browser download.
    Also used by the pywebview DownloadAPI in main.py to fetch the raw bytes.
    
    Reading the full file into memory is acceptable here because file sizes
    are limited (office documents, images) and the team is small.
    For large files a streaming response would be more appropriate.
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT original_filename, file_path FROM event_files WHERE id = ?', (file_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'File not found'}), 404
    file_path = resolve_file_path(row[1])
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found on disk'}), 404
    mime, _ = mimetypes.guess_type(row[0])
    if not mime:
        mime = 'application/octet-stream'  # fallback for unknown file types
    with open(file_path, 'rb') as f:
        data = f.read()
    response = make_response(data)
    response.headers['Content-Type']        = mime
    response.headers['Content-Disposition'] = f'attachment; filename="{row[0]}"'
    response.headers['Content-Length']      = len(data)
    return response

# ══════════════════════════════════════════════════════════════════
# FILE PREVIEW HELPERS
# Each function converts a specific file format to HTML or base64
# so the frontend can render it inline without a separate viewer app.
# ══════════════════════════════════════════════════════════════════

def _xlsx_to_html(file_path):
    """
    Converts an .xlsx Excel file to an HTML table string.
    Uses openpyxl with data_only=True to read computed cell values
    rather than the underlying formulas.
    Renders each sheet as a separate table with a heading.
    First row is styled as a header row.
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        html_parts = []
        for sheet in wb.worksheets:
            html_parts.append(f'<h3 style="color:#667eea;margin:16px 0 8px;">גיליון: {sheet.title}</h3>')
            html_parts.append('<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;font-size:13px;direction:ltr;">')
            for r_idx, row in enumerate(sheet.iter_rows(values_only=True)):
                tag = 'th' if r_idx == 0 else 'td'
                bg  = 'background:#667eea;color:#fff;' if r_idx == 0 else ('background:#f7fafc;' if r_idx % 2 == 0 else 'background:#fff;')
                html_parts.append('<tr>')
                for cell in row:
                    val = '' if cell is None else str(cell)
                    html_parts.append(f'<{tag} style="border:1px solid #e2e8f0;padding:6px 10px;{bg}text-align:right;">{val}</{tag}>')
                html_parts.append('</tr>')
            html_parts.append('</table></div>')
        return ''.join(html_parts)
    except Exception as e:
        return f'<p style="color:red;">שגיאה בקריאת קובץ Excel: {e}</p>'

def _xls_to_html(file_path):
    """
    Converts an old-format .xls file to an HTML table string using xlrd.
    xlrd >= 2.0 only supports .xls (not .xlsx), so this is specifically
    for legacy Excel files from Excel 97–2003.
    Falls back gracefully if xlrd is not installed.
    """
    try:
        import xlrd
        wb = xlrd.open_workbook(file_path)
        html_parts = []
        for sheet in wb.sheets():
            html_parts.append(f'<h3 style="color:#667eea;margin:16px 0 8px;">גיליון: {sheet.name}</h3>')
            html_parts.append('<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;font-size:13px;direction:ltr;">')
            for r_idx in range(sheet.nrows):
                tag = 'th' if r_idx == 0 else 'td'
                bg  = 'background:#667eea;color:#fff;' if r_idx == 0 else ('background:#f7fafc;' if r_idx % 2 == 0 else 'background:#fff;')
                html_parts.append('<tr>')
                for cell in sheet.row_values(r_idx):
                    val = '' if cell is None else str(cell)
                    html_parts.append(f'<{tag} style="border:1px solid #e2e8f0;padding:6px 10px;{bg}text-align:right;">{val}</{tag}>')
                html_parts.append('</tr>')
            html_parts.append('</table></div>')
        return ''.join(html_parts)
    except ImportError:
        return '<p style="color:#c05621;">קובץ .xls ישן — נסה להמיר ל-.xlsx</p>'
    except Exception as e:
        return f'<p style="color:red;">שגיאה בקריאת קובץ XLS: {e}</p>'

def _csv_to_html(file_path):
    """
    Converts a CSV file to an HTML table string.
    Uses utf-8-sig encoding to handle Excel-exported CSVs that start
    with a UTF-8 BOM character. errors='replace' prevents crashes on
    files with encoding issues.
    """
    try:
        import csv, codecs
        html_parts = ['<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;font-size:13px;direction:ltr;">']
        with codecs.open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.reader(f)
            for r_idx, row in enumerate(reader):
                tag = 'th' if r_idx == 0 else 'td'
                bg  = 'background:#667eea;color:#fff;' if r_idx == 0 else ('background:#f7fafc;' if r_idx % 2 == 0 else 'background:#fff;')
                html_parts.append('<tr>')
                for cell in row:
                    html_parts.append(f'<{tag} style="border:1px solid #e2e8f0;padding:6px 10px;{bg}text-align:right;">{cell}</{tag}>')
                html_parts.append('</tr>')
        html_parts.append('</table></div>')
        return ''.join(html_parts)
    except Exception as e:
        return f'<p style="color:red;">שגיאה בקריאת קובץ CSV: {e}</p>'

def _docx_to_html(file_path):
    """
    Converts a .docx Word document to an HTML string using python-docx.
    Renders:
     - Heading paragraphs as <h2>/<h3> etc.
     - Normal paragraphs as <p> with blank paragraphs as <br>.
     - Tables as styled HTML tables with a header row.
    Does not preserve bold/italic/colour within paragraphs (only structure).
    Falls back gracefully if python-docx is not installed.
    """
    try:
        from docx import Document
        doc = Document(file_path)
        html_parts = ['<div style="font-size:14px;line-height:1.8;direction:rtl;">']
        for para in doc.paragraphs:
            if para.style.name.startswith('Heading'):
                level = para.style.name[-1] if para.style.name[-1].isdigit() else '2'
                html_parts.append(f'<h{level} style="color:#667eea;">{para.text}</h{level}>')
            else:
                if para.text.strip():
                    html_parts.append(f'<p style="margin:6px 0;">{para.text}</p>')
                else:
                    html_parts.append('<br>')
        for table in doc.tables:
            html_parts.append('<div style="overflow-x:auto;margin:10px 0;"><table style="border-collapse:collapse;width:100%;font-size:13px;">')
            for r_idx, row in enumerate(table.rows):
                tag = 'th' if r_idx == 0 else 'td'
                bg  = 'background:#667eea;color:#fff;' if r_idx == 0 else ('background:#f7fafc;' if r_idx % 2 == 0 else '')
                html_parts.append('<tr>')
                for cell in row.cells:
                    html_parts.append(f'<{tag} style="border:1px solid #e2e8f0;padding:6px 10px;{bg}">{cell.text}</{tag}>')
                html_parts.append('</tr>')
            html_parts.append('</table></div>')
        html_parts.append('</div>')
        return ''.join(html_parts)
    except ImportError:
        return '<p style="color:#c05621;">ספריית python-docx לא מותקנת.</p>'
    except Exception as e:
        return f'<p style="color:red;">שגיאה בקריאת קובץ Word: {e}</p>'

# ══════════════════════════════════════════════════════════════════
# FILES — VIEW (IN-BROWSER PREVIEW)
# ══════════════════════════════════════════════════════════════════

@app.route('/api/files/<int:file_id>/view', methods=['GET'])
def view_file(file_id):
    """
    Returns file content in a format the browser can preview inline.
    
    Response JSON shape depends on the file type:
    
    { previewable: true, preview_type: 'base64', mime_type, data, filename }
        — for PDF and images: the file is base64-encoded so it can be embedded
          as a data URI in an <iframe> or <img> tag.
    
    { previewable: true, preview_type: 'text', content, filename }
        — for .txt files: raw text content.
    
    { previewable: true, preview_type: 'html_table', html, filename }
        — for .csv, .xlsx, .xls: converted to an HTML table string.
    
    { previewable: true, preview_type: 'html_doc', html, filename }
        — for .docx: paragraphs and tables converted to HTML.
    
    { previewable: false, filename, reason? }
        — for .doc (old format) or unsupported types: suggests downloading instead.
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT original_filename, file_path FROM event_files WHERE id = ?', (file_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'File not found'}), 404

    filename  = row[0]
    file_path = resolve_file_path(row[1])
    if not os.path.exists(file_path):
        return jsonify({'error': f'הקובץ לא נמצא בדיסק. נתיב: {row[1]}'}), 404

    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    # map extensions to their MIME types for base64 embedding
    b64_types = {
        'pdf':  'application/pdf',
        'png':  'image/png',
        'jpg':  'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif':  'image/gif',
        'webp': 'image/webp',
        'svg':  'image/svg+xml',
    }

    try:
        if ext in b64_types:
            # read binary, encode as base64 string for JSON transport
            with open(file_path, 'rb') as f:
                data_b64 = base64.b64encode(f.read()).decode('utf-8')
            return jsonify({'previewable': True, 'preview_type': 'base64', 'filename': filename,
                            'mime_type': b64_types[ext], 'data': data_b64})
        if ext == 'txt':
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return jsonify({'previewable': True, 'preview_type': 'text', 'filename': filename, 'content': content})
        if ext == 'csv':
            return jsonify({'previewable': True, 'preview_type': 'html_table', 'filename': filename, 'html': _csv_to_html(file_path)})
        if ext == 'xlsx':
            return jsonify({'previewable': True, 'preview_type': 'html_table', 'filename': filename, 'html': _xlsx_to_html(file_path)})
        if ext == 'xls':
            return jsonify({'previewable': True, 'preview_type': 'html_table', 'filename': filename, 'html': _xls_to_html(file_path)})
        if ext == 'docx':
            return jsonify({'previewable': True, 'preview_type': 'html_doc', 'filename': filename, 'html': _docx_to_html(file_path)})
        if ext == 'doc':
            # old .doc format — python-docx cannot read it; suggest converting to .docx
            return jsonify({'previewable': False, 'filename': filename, 'reason': 'doc_old'})
        # all other types (msg, shp, zip, etc.) — not previewable
        return jsonify({'previewable': False, 'filename': filename})
    except Exception as e:
        return jsonify({'error': f'שגיאה בעיבוד הקובץ: {str(e)}'}), 500

@app.route('/api/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    """
    Deletes a file record from the database AND removes the physical file from disk.
    If the DB delete succeeds but the disk delete fails, logs the error silently
    (the DB record is already gone so re-trying would be harmless).
    Response: { success, message }
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT file_path FROM event_files WHERE id = ?', (file_id,))
        row = cursor.fetchone()
        if row:
            cursor.execute('DELETE FROM event_files WHERE id = ?', (file_id,))
            conn.commit()
            file_path = resolve_file_path(row[0])
            if os.path.exists(file_path):
                os.remove(file_path)
        conn.close()
        return jsonify({'success': True, 'message': 'הקובץ נמחק בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════
# EMAIL DISTRIBUTION LIST
# ══════════════════════════════════════════════════════════════════

@app.route('/api/email-list', methods=['GET'])
def get_email_list():
    """
    Returns all entries in the email distribution list, ordered by name.
    This list is used by email_notifications.py to find recipients.
    Response: [ { id, email, name, added_by, added_at }, ... ]
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, name, added_by, added_at FROM email_list ORDER BY name')
    emails = [{'id': r[0], 'email': r[1], 'name': r[2], 'added_by': r[3], 'added_at': r[4]}
              for r in cursor.fetchall()]
    conn.close()
    return jsonify(emails)

@app.route('/api/email-list', methods=['POST'])
def add_email():
    """
    Manually adds an email address to the distribution list.
    Used for external recipients who are not system users.
    Request body: { email, name?, added_by? }
    Response: { success, message }
    """
    data = request.json
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO email_list (email, name, added_by) VALUES (?, ?, ?)',
                       (data['email'], data.get('name', ''), data.get('added_by', 'System')))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'האימייל נוסף בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/email-list/<int:email_id>', methods=['DELETE'])
def delete_email(email_id):
    """
    Removes an email address from the distribution list.
    Response: { success, message }
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM email_list WHERE id = ?', (email_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'האימייל נמחק בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════
# STATISTICS
# ══════════════════════════════════════════════════════════════════

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    Returns summary counts for the four stat cards on the dashboard.
    
    Response:
    {
      total_events: int,   — active (not completed/frozen, not deleted)
      overdue: int,        — past deadline and not closed
      critical: int,       — urgency = 'קריטית' (not deleted)
      by_status: { status: count }  — breakdown of all events by status
    }
    
    The 'in progress' count is calculated client-side from by_status.
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM events
        WHERE is_deleted = 0 AND id > 0 AND status NOT IN ('הושלם הטיפול', 'בהקפאה')
    """)
    total_events = cursor.fetchone()[0]
    today = datetime.now().strftime('%Y-%m-%d')
    # build the IN clause dynamically so CLOSED_STATUSES can be changed without rewriting the query
    placeholders = ','.join('?' for _ in CLOSED_STATUSES)
    cursor.execute(f'''
        SELECT COUNT(*) FROM events
        WHERE status_deadline < ? AND status NOT IN ({placeholders}) AND is_deleted = 0 AND id > 0
    ''', (today, *CLOSED_STATUSES))
    overdue = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM events WHERE urgency = 'קריטית' AND is_deleted = 0 AND id > 0")
    critical = cursor.fetchone()[0]
    cursor.execute('SELECT status, COUNT(*) FROM events WHERE is_deleted = 0 AND id > 0 GROUP BY status')
    by_status = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return jsonify({'total_events': total_events, 'overdue': overdue,
                    'critical': critical, 'by_status': by_status})

# ══════════════════════════════════════════════════════════════════
# EMAIL NOTIFICATION PREFERENCES
# ══════════════════════════════════════════════════════════════════

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    """
    Returns every user's notification preferences joined with their user info.
    Uses COALESCE to return 0 for any preference that hasn't been set yet.
    Response: [ { user_id, user_name, email, notify_* fields }, ... ]
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.name, u.email,
               COALESCE(n.notify_status_change, 0), COALESCE(n.notify_weekly_report, 0),
               COALESCE(n.notify_new_event, 0), COALESCE(n.notify_responsible, 0),
               COALESCE(n.notify_overdue, 0)
        FROM users u LEFT JOIN email_notifications n ON u.id = n.user_id ORDER BY u.name
    ''')
    result = [{'user_id': r[0], 'user_name': r[1], 'email': r[2],
               'notify_status_change': r[3], 'notify_weekly_report': r[4],
               'notify_new_event': r[5], 'notify_responsible': r[6], 'notify_overdue': r[7]}
              for r in cursor.fetchall()]
    conn.close()
    return jsonify(result)

@app.route('/api/notifications/<int:user_id>', methods=['PUT'])
def update_notification(user_id):
    """
    Updates a single notification preference for one user.
    Uses INSERT OR IGNORE + ON CONFLICT UPDATE (upsert) so this works
    whether or not the user already has a notifications row.
    
    Request body: { field: 'notify_xxx', value: 0 | 1 }
    Response: { success }
    """
    data  = request.json
    field = data.get('field')
    value = data.get('value')
    # whitelist to prevent SQL injection via the field name
    allowed_fields = ['notify_status_change', 'notify_weekly_report',
                      'notify_new_event', 'notify_responsible', 'notify_overdue']
    if field not in allowed_fields:
        return jsonify({'success': False, 'error': 'Invalid field'}), 400
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        # f-string is safe here because field is validated against the whitelist above
        cursor.execute(f'''
            INSERT INTO email_notifications (user_id, {field}) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET {field} = ?, updated_at = CURRENT_TIMESTAMP
        ''', (user_id, value, value))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notifications/<int:user_id>/all', methods=['PUT'])
def update_all_notifications(user_id):
    """
    Sets all five notification preferences for a user to the same value at once.
    Used by the "All" convenience checkbox in the admin panel.
    Request body: { value: 0 | 1 }
    Response: { success }
    """
    data  = request.json
    value = data.get('value', 0)
    conn  = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO email_notifications
                (user_id, notify_status_change, notify_weekly_report,
                 notify_new_event, notify_responsible, notify_overdue)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                notify_status_change = ?, notify_weekly_report = ?,
                notify_new_event = ?, notify_responsible = ?,
                notify_overdue = ?, updated_at = CURRENT_TIMESTAMP
        ''', (user_id, value, value, value, value, value,
              value, value, value, value, value))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════
# EXCEL REPORT
# ══════════════════════════════════════════════════════════════════

@app.route('/api/reports/excel', methods=['GET'])
def generate_excel_report():
    """
    Generates and streams an Excel report of ALL events (all time).
    Optional ?status= query param filters to a specific status (all time).
    The 7-day window was removed — on-demand reports always cover all time.
    The automated weekly email uses a separate code path in email_notifications.py.
    """
    from reports import generate_excel_report as build_report
    now    = datetime.now()
    status = request.args.get('status', '').strip()

    conn   = db.get_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute('''
            SELECT * FROM events
            WHERE is_deleted = 0 AND id > 0 AND status = ?
            ORDER BY id ASC
        ''', (status,))
        report_type = status
    else:
        cursor.execute('''
            SELECT * FROM events
            WHERE is_deleted = 0 AND id > 0
            ORDER BY id ASC
        ''')
        report_type = 'all'

    events = [row_to_event(row) for row in cursor.fetchall()]
    conn.close()

    file_stream = build_report(events, report_date=now, report_type=report_type)
    safe_status = status.replace(' ', '_') if status else 'כל_הזמנים'
    return send_file(
        file_stream,
        as_attachment=True,
        download_name=f'דוח_אירועים_{safe_status}_{now.strftime("%Y%m%d")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ══════════════════════════════════════════════════════════════════
# COMMENTS
# ══════════════════════════════════════════════════════════════════

@app.route('/api/events/<int:event_id>/comments', methods=['GET'])
def get_comments(event_id):
    """
    Returns all comments for an event, oldest first (chronological order).
    Response: [ { id, comment_text, author, created_at }, ... ]
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, comment_text, author, created_at
        FROM event_comments WHERE event_id = ? ORDER BY created_at ASC
    ''', (event_id,))
    comments = [
        {'id': r[0], 'comment_text': r[1], 'author': r[2], 'created_at': r[3]}
        for r in cursor.fetchall()
    ]
    conn.close()
    return jsonify(comments)

@app.route('/api/events/<int:event_id>/comments', methods=['POST'])
def add_comment(event_id):
    """
    Adds a new comment to an event.
    Also writes an 'updated' audit_log entry with field_name='comment'
    so the comment appears in the history timeline.
    
    Request body: { comment_text, author }
    Response: { success, comment_id }
    """
    data   = request.json
    text   = (data.get('comment_text') or '').strip()
    author = (data.get('author') or '').strip()
    if not text:
        return jsonify({'success': False, 'error': 'תוכן ההערה אינו יכול להיות ריק'}), 400
    if not author:
        return jsonify({'success': False, 'error': 'יש לבחור משתמש לפני הוספת הערה'}), 400
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO event_comments (event_id, comment_text, author) VALUES (?, ?, ?)
        ''', (event_id, text, author))
        comment_id = cursor.lastrowid
        # record in audit_log using 'comment' field key — old value is empty, new value is the text
        log_audit(cursor, event_id, 'updated', author, changes={'comment': ('', text)})
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'comment_id': comment_id})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    """
    Deletes a comment.
    Authorization: the requester must be either the comment's author or an admin.
    The server enforces this even though the frontend also hides the delete button.
    
    Request body: { requester, requester_role }
    Response: { success }
    """
    data           = request.json or {}
    requester      = data.get('requester', '')
    requester_role = data.get('requester_role', '')
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT author, event_id FROM event_comments WHERE id = ?', (comment_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'הערה לא נמצאה'}), 404
        author = row[0]
        # server-side permission check
        if requester_role != 'admin' and requester != author:
            conn.close()
            return jsonify({'success': False, 'error': 'אין הרשאה למחוק הערה זו'}), 403
        cursor.execute('DELETE FROM event_comments WHERE id = ?', (comment_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════
# PERMISSIONS — ROLE LEVEL
# ══════════════════════════════════════════════════════════════════

@app.route('/api/permissions/all', methods=['GET'])
def get_all_permissions():
    """
    Returns the full role-level permission matrix as a nested dict:
    { role: { field_name: can_edit (0|1) } }
    Used to render the permissions matrix table in the admin panel.
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT role, field_name, can_edit FROM field_permissions ORDER BY role, field_name')
    matrix = {}
    for role, field, can_edit in cursor.fetchall():
        if role not in matrix:
            matrix[role] = {}
        matrix[role][field] = can_edit
    conn.close()
    return jsonify(matrix)

@app.route('/api/permissions/<string:role>', methods=['GET'])
def get_permissions(role):
    """
    Returns permissions for a specific role.
    Response: { role, permissions: { field_name: can_edit } }
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT field_name, can_edit FROM field_permissions WHERE role = ?', (role,))
    perms = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()
    return jsonify({'role': role, 'permissions': perms})

@app.route('/api/permissions/<string:role>', methods=['PUT'])
def update_permission(role):
    """
    Updates a single field permission for a role.
    Admin permissions cannot be changed (always full access).
    Uses INSERT OR IGNORE + ON CONFLICT to upsert cleanly.
    
    Request body: { field_name, can_edit: 0 | 1 }
    Response: { success }
    """
    if role == 'admin':
        return jsonify({'success': False, 'error': 'לא ניתן לשנות הרשאות אדמין'}), 400
    data       = request.json
    field_name = data.get('field_name')
    can_edit   = data.get('can_edit')
    if field_name is None or can_edit is None:
        return jsonify({'success': False, 'error': 'field_name and can_edit are required'}), 400
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO field_permissions (role, field_name, can_edit) VALUES (?, ?, ?)
            ON CONFLICT(role, field_name) DO UPDATE SET can_edit = ?
        ''', (role, field_name, can_edit, can_edit))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════
# PERMISSIONS — USER LEVEL
# ══════════════════════════════════════════════════════════════════

@app.route('/api/user-permissions/all', methods=['GET'])
def get_all_user_permissions():
    """
    Returns the per-user permission matrix alongside the user list.
    Response: { users: [ { id, name, role } ], matrix: { user_id: { field_name: can_edit } } }
    The frontend uses this to render the per-user permissions table in the admin panel.
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, role FROM users ORDER BY name')
    users = [{'id': r[0], 'name': r[1], 'role': r[2]} for r in cursor.fetchall()]
    cursor.execute(
        'SELECT user_id, field_name, can_edit FROM user_field_permissions ORDER BY user_id, field_name'
    )
    matrix = {}
    for uid, field, can_edit in cursor.fetchall():
        if uid not in matrix:
            matrix[uid] = {}
        matrix[uid][field] = can_edit
    conn.close()
    return jsonify({'users': users, 'matrix': matrix})

@app.route('/api/user-permissions/<int:user_id>', methods=['GET'])
def get_user_permissions(user_id):
    """
    Returns the effective field permissions for a specific user.
    
    Permission resolution order:
    1. Admin → always full access (all fields = 1), no DB lookup needed.
    2. Per-user overrides exist in user_field_permissions → use those.
    3. No per-user overrides → fall back to the user's role defaults from field_permissions.
    
    This is the endpoint called by the frontend when a user logs in
    to determine which form fields to enable/disable.
    Response: { user_id, permissions: { field_name: can_edit } }
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'permissions': {}}), 404
    role = row[0]
    if role == 'admin':
        # return all fields as editable without hitting the permissions tables
        cursor.execute('SELECT DISTINCT field_name FROM field_permissions')
        perms = {r[0]: 1 for r in cursor.fetchall()}
        conn.close()
        return jsonify({'user_id': user_id, 'permissions': perms})
    cursor.execute(
        'SELECT field_name, can_edit FROM user_field_permissions WHERE user_id = ?', (user_id,)
    )
    rows = cursor.fetchall()
    if rows:
        perms = {r[0]: r[1] for r in rows}  # per-user overrides exist — use them
    else:
        # no per-user rows — fall back to role defaults
        cursor.execute('SELECT field_name, can_edit FROM field_permissions WHERE role = ?', (role,))
        perms = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()
    return jsonify({'user_id': user_id, 'permissions': perms})

@app.route('/api/user-permissions/<int:user_id>', methods=['PUT'])
def update_user_permission(user_id):
    """
    Updates a single per-user field permission.
    Admin users cannot have their permissions changed.
    Uses INSERT OR IGNORE + ON CONFLICT to upsert cleanly.
    
    Request body: { field_name, can_edit: 0 | 1 }
    Response: { success }
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': 'משתמש לא נמצא'}), 404
    if row[0] == 'admin':
        conn.close()
        return jsonify({'success': False, 'error': 'לא ניתן לשנות הרשאות אדמין'}), 400
    data       = request.json
    field_name = data.get('field_name')
    can_edit   = data.get('can_edit')
    if field_name is None or can_edit is None:
        conn.close()
        return jsonify({'success': False, 'error': 'field_name and can_edit are required'}), 400
    try:
        cursor.execute('''
            INSERT INTO user_field_permissions (user_id, field_name, can_edit) VALUES (?, ?, ?)
            ON CONFLICT(user_id, field_name) DO UPDATE SET can_edit = ?
        ''', (user_id, field_name, can_edit, can_edit))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════
# ENTRY POINT (direct execution only)
# ══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # This block only runs when you execute `python app.py` directly.
    # In production (via main.py / Run_App.bat) Flask is started by
    # start_flask_server() in main.py with host='0.0.0.0' and threaded=True.
    print("✅ Database initialized successfully!")
    print("🚀 Starting Event Management System...")
    print("🌐 Server running at: http://localhost:5000")
    app.run(debug=True, port=5000)