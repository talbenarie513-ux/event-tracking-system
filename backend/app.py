from flask import Flask, request, jsonify, send_file, send_from_directory, make_response
# Flask — the web framework. request=reads incoming data, jsonify=turns dicts to JSON,
# send_file=sends a file download, send_from_directory=serves static files, make_response=builds custom responses
from flask_cors import CORS          # allows the browser frontend to call this API without being blocked
from database import Database        # our own database manager class
import os                            # built-in — file/folder path operations
import mimetypes                     # built-in — detects file type from filename (e.g. image/png)
import base64                        # built-in — encodes binary files to text for sending through JSON
from datetime import datetime, timedelta  # built-in — all date/time logic
from werkzeug.utils import secure_filename  # sanitizes uploaded filenames to prevent path attacks

from email_notifications import (
    trigger_new_event,           # fires when a new event is created
    trigger_status_change,       # fires when an event's status changes
    trigger_responsible_assigned, # fires when a responsible person is assigned
)

app = Flask(__name__)  # creates the Flask application
CORS(app)              # enables cross-origin requests so the frontend can call the API freely

@app.after_request
def add_header(response):
    # runs after every single response — tells the browser never to cache anything so data is always fresh
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # disables Flask's own file caching as well

# statuses that mean an event is "closed" — used throughout the file to exclude finished events
CLOSED_STATUSES = ('הושלם הטיפול', 'טופל חלקית', 'בהקפאה')

# absolute path to the folder where app.py lives — used as a base for all file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_next_available_id(cursor):
    # finds the highest existing event ID and returns +1. Returns 1 if table is empty
    # ⚠️ could cause duplicate ID collisions if two users create events at the exact same time
    cursor.execute('SELECT MAX(id) FROM events')
    max_id = cursor.fetchone()[0]
    return (max_id + 1) if max_id else 1

db = Database()  # creates the single shared database instance used by all routes

# folder where uploaded files are saved — created automatically if it doesn't exist
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
# whitelist of allowed upload extensions — anything not in this list is rejected
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'doc', 'docx', 'pdf', 'png', 'jpg', 'jpeg',
                      'msg', 'shp', 'zip', 'eml', 'csv', 'txt', 'gif', 'webp', 'svg'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)  # creates the uploads folder on first run

def allowed_file(filename):
    # checks if the file extension is in the allowed list
    # rsplit('.', 1) splits from the right so 'report.final.xlsx' correctly returns 'xlsx'
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def resolve_file_path(stored_path):
    """
    Tries multiple strategies to find a file on disk.
    Exists because older versions stored paths differently (absolute vs relative, different separators).
    Tries 5 combinations before giving up and returning the original path.
    """
    # 1. Try as-is (already absolute or cwd-relative)
    if os.path.exists(stored_path):
        return stored_path

    # 2. Try relative to BASE_DIR (where app.py lives)
    candidate = os.path.join(BASE_DIR, stored_path)
    if os.path.exists(candidate):
        return candidate

    # 3. Normalise separators and try again relative to BASE_DIR
    normalised = stored_path.replace('\\', '/').lstrip('/')
    candidate2 = os.path.join(BASE_DIR, normalised)
    if os.path.exists(candidate2):
        return candidate2

    # 4. Try relative to cwd
    candidate3 = os.path.join(os.getcwd(), normalised)
    if os.path.exists(candidate3):
        return candidate3

    # 5. Strip everything before 'uploads' and try relative to BASE_DIR
    parts = normalised.replace('\\', '/').split('uploads/', 1)
    if len(parts) == 2:
        candidate4 = os.path.join(UPLOAD_FOLDER, parts[1])
        if os.path.exists(candidate4):
            return candidate4

    return stored_path  # not found — return original so caller can report the error

def row_to_event(row):
    # converts a raw database tuple into a named dictionary so code is readable
    # e.g. event['status'] instead of row[9]
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

# maps database column names to Hebrew display labels — used in the audit log history modal
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
}

def log_audit(cursor, event_id, action, changed_by, changes=None):
    # writes to the audit_log table — called after every create, update, delete, or restore
    # for simple actions (created/deleted/restored) just logs the action with no field details
    # for updates, logs each changed field separately with old and new values
    if action in ('created', 'deleted', 'restored') or not changes:
        cursor.execute('''
            INSERT INTO audit_log (event_id, action, changed_by)
            VALUES (?, ?, ?)
        ''', (event_id, action, changed_by))
    else:
        for field, (old_val, new_val) in changes.items():
            cursor.execute('''
                INSERT INTO audit_log (event_id, action, field_name, old_value, new_value, changed_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (event_id, action, field, str(old_val) if old_val is not None else '',
                  str(new_val) if new_val is not None else '', changed_by))

# ── serves the main HTML page when someone visits the root URL
@app.route('/')
def serve_index():
    return send_from_directory('..', 'index.html')

# ── serves the main JavaScript file
@app.route('/app.js')
def serve_js():
    return send_from_directory('..', 'app.js')

# ============= USERS =============

@app.route('/api/users', methods=['GET'])
def get_users():
    # returns all users as JSON — used to populate the user dropdown and responsible person dropdown
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, role, email FROM users ORDER BY name')
    users = [{'id': r[0], 'name': r[1], 'role': r[2], 'email': r[3]} for r in cursor.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
def add_user():
    # creates a new user and automatically adds them to email_list and notification preferences
    # three things happen in one request — user row, email list entry, and notification row
    data = request.json
    if not data.get('email'):
        return jsonify({'success': False, 'error': 'אימייל הוא שדה חובה'}), 400
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (name, role, email) VALUES (?, ?, ?)',
                       (data['name'], data['role'], data['email']))
        user_id = cursor.lastrowid  # gets the auto-assigned ID of the just-inserted user
        cursor.execute('INSERT OR IGNORE INTO email_list (email, name, added_by) VALUES (?, ?, ?)',
                       (data['email'], data['name'], 'System'))
        cursor.execute('INSERT OR IGNORE INTO email_notifications (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'המשתמש נוסף בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    # updates a user's name, role, and email — also updates their email in email_list to stay in sync
    data = request.json
    if not data.get('email'):
        return jsonify({'success': False, 'error': 'אימייל הוא שדה חובה'}), 400
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT email FROM users WHERE id = ?', (user_id,))
        old = cursor.fetchone()  # get old email so we can update it in email_list too
        cursor.execute('UPDATE users SET name = ?, role = ?, email = ? WHERE id = ?',
                       (data['name'], data['role'], data['email'], user_id))
        if old:
            cursor.execute('UPDATE email_list SET email = ?, name = ? WHERE email = ?',
                           (data['email'], data['name'], old[0]))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'המשתמש עודכן בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    # permanently deletes a user — no soft delete here unlike events
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

# ============= EVENTS =============

@app.route('/api/events', methods=['GET'])
def get_events():
    # returns events as JSON with optional filtering by status, urgency, search text, and deleted flag
    # builds a dynamic SQL query using WHERE 1=1 so AND conditions can be added freely
    conn = db.get_connection()
    cursor = conn.cursor()
    show_deleted = request.args.get('show_deleted', 'false').lower() == 'true'
    status_filter = request.args.get('status')
    urgency_filter = request.args.get('urgency')
    search = request.args.get('search', '').strip()

    query = 'SELECT * FROM events WHERE 1=1'  # WHERE 1=1 is a trick to make adding AND conditions easier
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
        # searches across three fields at once using LIKE with % wildcards
        query += ' AND (event_summary LIKE ? OR system LIKE ? OR event_details LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])

    query += ' ORDER BY id DESC'
    cursor.execute(query, params)  # ? placeholders prevent SQL injection
    events = [row_to_event(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(events)

@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    # returns a single event by ID, including its attached files
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Event not found'}), 404
    event = row_to_event(row)
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

# ============= HISTORY ENDPOINT =============

@app.route('/api/events/<int:event_id>/history', methods=['GET'])
def get_event_history(event_id):
    # returns the full audit log for an event — powers the history modal in the frontend
    # includes creation info plus every field change grouped by timestamp
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT created_by, created_at FROM events WHERE id = ?', (event_id,))
    event_row = cursor.fetchone()
    if not event_row:
        conn.close()
        return jsonify({'error': 'Event not found'}), 404

    created_by = event_row[0]
    created_at = event_row[1]

    cursor.execute('''
        SELECT action, field_name, old_value, new_value, changed_by, changed_at
        FROM audit_log
        WHERE event_id = ?
        ORDER BY changed_at ASC  -- oldest changes first
    ''', (event_id,))

    entries = []
    for r in cursor.fetchall():
        entries.append({
            'action':      r[0],
            'field_name':  r[1],
            'field_label': FIELD_LABELS.get(r[1], r[1]) if r[1] else None,  # Hebrew label if available
            'old_value':   r[2],
            'new_value':   r[3],
            'changed_by':  r[4],
            'changed_at':  r[5],
        })

    conn.close()
    return jsonify({
        'event_id':   event_id,
        'created_by': created_by,
        'created_at': created_at,
        'entries':    entries,
    })

# ============= CREATE EVENT =============

@app.route('/api/events', methods=['POST'])
def create_event():
    # creates a new event. Admin gets relaxed validation (missing fields get defaults),
    # other roles get strict validation (missing required fields raise KeyError)
    data = request.json
    user_role = data.get('user_role', '')
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        event_id = data.get('event_id')
        if event_id:
            event_id = int(event_id)
            cursor.execute('SELECT id FROM events WHERE id = ?', (event_id,))
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': f'מספר אירוע {event_id} כבר קיים במערכת'}), 400
        else:
            event_id = get_next_available_id(cursor)  # auto-assign next available ID

        if user_role == 'admin':
            # admin — all fields optional, missing ones get sensible defaults
            registration_date  = data.get('registration_date') or datetime.now().strftime('%Y-%m-%d')
            system             = data.get('system') or 'לא צוין'
            event_summary      = data.get('event_summary') or f'אירוע #{event_id}'
            event_details      = data.get('event_details') or ''
            affected_customers = data.get('affected_customers') or 'לא צוין'
            urgency            = data.get('urgency') or 'בינונית'
            priority           = data.get('priority') or 5
            status             = data.get('status') or 'אירוע חדש'
            status_deadline    = data.get('status_deadline') or (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        else:
            # non-admin — fields are required. Missing ones will raise KeyError caught below
            registration_date  = data['registration_date']
            system             = data['system']
            event_summary      = data['event_summary']
            event_details      = data['event_details']
            affected_customers = data['affected_customers']
            urgency            = data['urgency']
            priority           = data['priority']
            status             = data['status']
            status_deadline    = data['status_deadline']

        # auto-set completion date if status is already "completed" at creation time
        completion_date = None
        if status == 'הושלם הטיפול':
            completion_date = data.get('completion_date') or datetime.now().strftime('%Y-%m-%d')

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
            data.get('responsible_person', ''), data.get('price_quote'),
            data.get('additional_notes', ''), data['created_by']
        ))

        # record the initial status in status_history
        cursor.execute('INSERT INTO status_history (event_id, status, changed_by) VALUES (?, ?, ?)',
                       (event_id, status, data['created_by']))
        log_audit(cursor, event_id, 'created', data['created_by'])  # log the creation action
        conn.commit()
        conn.close()

        # fire email notifications after successful save
        full_event = {
            "id":                 event_id,
            "system":             system,
            "event_summary":      event_summary,
            "event_details":      event_details,
            "affected_customers": affected_customers,
            "urgency":            urgency,
            "priority":           priority,
            "status":             status,
            "status_deadline":    status_deadline,
            "registration_date":  registration_date,
            "responsible_person": data.get("responsible_person", ""),
            "status_details":     data.get("status_details", ""),
        }
        trigger_new_event(full_event, data["created_by"])
        if data.get("responsible_person"):
            # also fire responsible assignment email if one was set at creation
            trigger_responsible_assigned(full_event, "", data["created_by"])

        return jsonify({'success': True, 'message': 'האירוע נוצר בהצלחה', 'event_id': event_id})

    except KeyError as e:
        # missing required field — only happens for non-admin users
        conn.close()
        return jsonify({'success': False, 'error': f'שדה חובה חסר: {str(e)}'}), 400
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============= UPDATE EVENT =============

@app.route('/api/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    # updates an existing event. Compares every field before and after to log only what actually changed
    data = request.json
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        old_row = cursor.fetchone()
        if not old_row:
            conn.close()
            return jsonify({'success': False, 'error': 'Event not found'}), 404

        old = row_to_event(old_row)  # snapshot of the event before the update
        old_status      = old['status']
        old_id          = old['id']
        old_responsible = old['responsible_person']

        new_id = data.get('event_id', old_id)
        if new_id is None:
            new_id = old_id
        new_id = int(new_id)

        # check if the new ID is already taken by a different event
        if new_id != old_id:
            cursor.execute('SELECT id FROM events WHERE id = ? AND id != ?', (new_id, old_id))
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': f'מספר אירוע {new_id} כבר קיים במערכת'}), 400

        new_status      = data.get('status', old_status)
        completion_date = data.get('completion_date')

        # auto-set or clear completion_date based on status
        if new_status == 'הושלם הטיפול' and not completion_date:
            completion_date = datetime.now().strftime('%Y-%m-%d')
        elif new_status != 'הושלם הטיפול':
            completion_date = None  # clear it if status is no longer "completed"

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
            new_id, data.get('registration_date'), data.get('first_contact_date'),
            data.get('system'), data.get('event_summary'), data.get('event_details'),
            data.get('affected_customers'), data.get('urgency'), data.get('priority'),
            new_status, data.get('status_details', ''), data.get('event_classification', ''),
            data.get('status_deadline'), completion_date, data.get('responsible_person', ''),
            data.get('price_quote'), data.get('additional_notes', ''), event_id
        ))

        # if status changed, record it in status_history
        if new_status != old_status:
            cursor.execute('INSERT INTO status_history (event_id, status, changed_by) VALUES (?, ?, ?)',
                           (event_id, new_status, data.get('updated_by', 'Unknown')))

        # compare old vs new values for every field to find what actually changed
        new_data = {
            'registration_date':    data.get('registration_date'),
            'first_contact_date':   data.get('first_contact_date'),
            'system':               data.get('system'),
            'event_summary':        data.get('event_summary'),
            'event_details':        data.get('event_details'),
            'affected_customers':   data.get('affected_customers'),
            'urgency':              data.get('urgency'),
            'priority':             str(data.get('priority')) if data.get('priority') is not None else None,
            'status':               new_status,
            'status_details':       data.get('status_details', ''),
            'event_classification': data.get('event_classification', ''),
            'status_deadline':      data.get('status_deadline'),
            'completion_date':      completion_date,
            'responsible_person':   data.get('responsible_person', ''),
            'price_quote':          str(data.get('price_quote')) if data.get('price_quote') is not None else '',
            'additional_notes':     data.get('additional_notes', ''),
        }
        changes = {}
        for field, new_val in new_data.items():
            old_val = str(old.get(field)) if old.get(field) is not None else ''
            new_val_str = str(new_val) if new_val is not None else ''
            if old_val != new_val_str:
                changes[field] = (old_val, new_val_str)  # only log fields that actually changed

        if changes:
            log_audit(cursor, new_id, 'updated', data.get('updated_by', 'Unknown'), changes)

        conn.commit()

        # re-fetch the updated event to pass accurate data to email triggers
        conn2 = db.get_connection()
        cur2  = conn2.cursor()
        cur2.execute("SELECT * FROM events WHERE id = ?", (new_id,))
        updated_row = cur2.fetchone()
        conn2.close()

        if updated_row:
            updated_event = row_to_event(updated_row)
            # only fire status change email if status actually changed
            if new_status != old_status:
                trigger_status_change(updated_event, old_status, data.get("updated_by", ""))
            # only fire responsible email if responsible person actually changed
            new_responsible = data.get("responsible_person", "")
            if new_responsible != (old_responsible or ""):
                trigger_responsible_assigned(updated_event, old_responsible or "", data.get("updated_by", ""))

        conn.close()
        return jsonify({'success': True, 'message': 'האירוע עודכן בהצלחה'})

    except Exception as e:
        conn.close()
        print(f"Error updating event {event_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    # soft delete — sets is_deleted=1 instead of actually removing the row
    # event can be restored later via the restore endpoint
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE events SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (event_id,))
        log_audit(cursor, event_id, 'deleted', 'System')
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'האירוע נמחק בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============= RESTORE =============

@app.route('/api/events/<int:event_id>/restore', methods=['PUT'])
def restore_event(event_id):
    # reverses a soft delete by setting is_deleted back to 0
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE events SET is_deleted = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (event_id,))
        log_audit(cursor, event_id, 'restored', 'System')
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'האירוע שוחזר בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============= FILES =============

@app.route('/api/events/<int:event_id>/files', methods=['POST'])
def upload_file(event_id):
    # saves an uploaded file to disk in /uploads/{event_id}/ and records its metadata in the db
    # timestamp prefix on filename prevents two files with the same name overwriting each other
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'File type not allowed'}), 400

    event_folder = os.path.join(UPLOAD_FOLDER, str(event_id))
    if not os.path.exists(event_folder):
        os.makedirs(event_folder)  # create event-specific subfolder if it doesn't exist

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = secure_filename(file.filename)  # sanitize filename to prevent path attacks
    # store relative path so it works regardless of where the app is installed
    rel_path = os.path.join('uploads', str(event_id), f"{timestamp}_{filename}")
    abs_path = os.path.join(BASE_DIR, rel_path)
    file.save(abs_path)

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO event_files (event_id, original_filename, file_path, uploaded_by)
            VALUES (?, ?, ?, ?)
        ''', (event_id, filename, rel_path, request.form.get('uploaded_by', 'Unknown')))
        conn.commit()
        file_id = cursor.lastrowid
        conn.close()
        return jsonify({'success': True, 'message': 'הקובץ הועלה בהצלחה', 'file_id': file_id, 'filename': filename})
    except Exception as e:
        conn.close()
        if os.path.exists(abs_path):
            os.remove(abs_path)  # clean up the file from disk if the db insert failed
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events/<int:event_id>/files', methods=['GET'])
def get_event_files(event_id):
    # returns all files attached to a specific event, newest first
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

@app.route('/api/files/<int:file_id>', methods=['GET'])
def download_file(file_id):
    # legacy download endpoint — kept for backwards compatibility with older frontend calls
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
    # preferred download endpoint — reads file as binary and returns it directly
    # works correctly inside pywebview where the legacy endpoint sometimes fails
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

    mime, _ = mimetypes.guess_type(row[0])  # detect the correct MIME type from the filename
    if not mime:
        mime = 'application/octet-stream'  # fallback generic binary type

    with open(file_path, 'rb') as f:
        data = f.read()

    response = make_response(data)
    response.headers['Content-Type'] = mime
    response.headers['Content-Disposition'] = f'attachment; filename="{row[0]}"'
    response.headers['Content-Length'] = len(data)
    return response


# ============= FILE VIEW HELPERS =============
# Each helper converts a specific file type into HTML for browser preview

def _xlsx_to_html(file_path):
    # converts an .xlsx file into an HTML table using openpyxl — one table per sheet
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)  # data_only=True reads cell values not formulas
        html_parts = []
        for sheet in wb.worksheets:
            html_parts.append(f'<h3 style="color:#667eea;margin:16px 0 8px;">גיליון: {sheet.title}</h3>')
            html_parts.append(
                '<div style="overflow-x:auto;">'
                '<table style="border-collapse:collapse;width:100%;font-size:13px;direction:ltr;">'
            )
            for r_idx, row in enumerate(sheet.iter_rows(values_only=True)):
                tag = 'th' if r_idx == 0 else 'td'  # first row becomes header cells
                bg  = 'background:#667eea;color:#fff;' if r_idx == 0 else (
                      'background:#f7fafc;' if r_idx % 2 == 0 else 'background:#fff;')
                html_parts.append('<tr>')
                for cell in row:
                    val = '' if cell is None else str(cell)
                    html_parts.append(
                        f'<{tag} style="border:1px solid #e2e8f0;padding:6px 10px;{bg}'
                        f'text-align:right;">{val}</{tag}>'
                    )
                html_parts.append('</tr>')
            html_parts.append('</table></div>')
        return ''.join(html_parts)
    except Exception as e:
        return f'<p style="color:red;">שגיאה בקריאת קובץ Excel: {e}</p>'


def _xls_to_html(file_path):
    # converts old .xls format files using xlrd — same output as _xlsx_to_html
    try:
        import xlrd
        wb = xlrd.open_workbook(file_path)
        html_parts = []
        for sheet in wb.sheets():
            html_parts.append(f'<h3 style="color:#667eea;margin:16px 0 8px;">גיליון: {sheet.name}</h3>')
            html_parts.append(
                '<div style="overflow-x:auto;">'
                '<table style="border-collapse:collapse;width:100%;font-size:13px;direction:ltr;">'
            )
            for r_idx in range(sheet.nrows):
                tag = 'th' if r_idx == 0 else 'td'
                bg  = 'background:#667eea;color:#fff;' if r_idx == 0 else (
                      'background:#f7fafc;' if r_idx % 2 == 0 else 'background:#fff;')
                html_parts.append('<tr>')
                for cell in sheet.row_values(r_idx):
                    val = '' if cell is None else str(cell)
                    html_parts.append(
                        f'<{tag} style="border:1px solid #e2e8f0;padding:6px 10px;{bg}'
                        f'text-align:right;">{val}</{tag}>'
                    )
                html_parts.append('</tr>')
            html_parts.append('</table></div>')
        return ''.join(html_parts)
    except ImportError:
        return '<p style="color:#c05621;">קובץ .xls ישן — נסה להמיר ל-.xlsx</p>'
    except Exception as e:
        return f'<p style="color:red;">שגיאה בקריאת קובץ XLS: {e}</p>'


def _csv_to_html(file_path):
    # converts a CSV file into an HTML table — handles UTF-8 BOM encoding common in Excel exports
    try:
        import csv, codecs
        html_parts = [
            '<div style="overflow-x:auto;">'
            '<table style="border-collapse:collapse;width:100%;font-size:13px;direction:ltr;">'
        ]
        with codecs.open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.reader(f)
            for r_idx, row in enumerate(reader):
                tag = 'th' if r_idx == 0 else 'td'
                bg  = 'background:#667eea;color:#fff;' if r_idx == 0 else (
                      'background:#f7fafc;' if r_idx % 2 == 0 else 'background:#fff;')
                html_parts.append('<tr>')
                for cell in row:
                    html_parts.append(
                        f'<{tag} style="border:1px solid #e2e8f0;padding:6px 10px;{bg}'
                        f'text-align:right;">{cell}</{tag}>'
                    )
                html_parts.append('</tr>')
        html_parts.append('</table></div>')
        return ''.join(html_parts)
    except Exception as e:
        return f'<p style="color:red;">שגיאה בקריאת קובץ CSV: {e}</p>'


def _docx_to_html(file_path):
    # converts a .docx Word file into HTML — paragraphs become <p>, headings become <h>, tables become <table>
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
            html_parts.append(
                '<div style="overflow-x:auto;margin:10px 0;">'
                '<table style="border-collapse:collapse;width:100%;font-size:13px;">'
            )
            for r_idx, row in enumerate(table.rows):
                tag = 'th' if r_idx == 0 else 'td'
                bg  = 'background:#667eea;color:#fff;' if r_idx == 0 else (
                      'background:#f7fafc;' if r_idx % 2 == 0 else '')
                html_parts.append('<tr>')
                for cell in row.cells:
                    html_parts.append(
                        f'<{tag} style="border:1px solid #e2e8f0;padding:6px 10px;{bg}">'
                        f'{cell.text}</{tag}>'
                    )
                html_parts.append('</tr>')
            html_parts.append('</table></div>')
        html_parts.append('</div>')
        return ''.join(html_parts)
    except ImportError:
        return '<p style="color:#c05621;">ספריית python-docx לא מותקנת. הרץ: pip install python-docx</p>'
    except Exception as e:
        return f'<p style="color:red;">שגיאה בקריאת קובץ Word: {e}</p>'


# ============= FILE VIEW ENDPOINT =============

@app.route('/api/files/<int:file_id>/view', methods=['GET'])
def view_file(file_id):
    # returns file content in a format the frontend can preview in the browser
    # different strategies per file type: base64 for images/pdf, html for office files, plain text for txt
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
        print(f"[view_file] File not found on disk. stored='{row[1]}' resolved='{file_path}'")
        return jsonify({'error': f'הקובץ לא נמצא בדיסק. נתיב: {row[1]}'}), 404

    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    # file types that can be displayed directly via base64 encoding
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
            # encode file as base64 string so it can be sent through JSON and displayed in browser
            with open(file_path, 'rb') as f:
                data_b64 = base64.b64encode(f.read()).decode('utf-8')
            return jsonify({
                'previewable':  True,
                'preview_type': 'base64',
                'filename':     filename,
                'mime_type':    b64_types[ext],
                'data':         data_b64,
            })

        if ext == 'txt':
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return jsonify({
                'previewable':  True,
                'preview_type': 'text',
                'filename':     filename,
                'content':      content,
            })

        if ext == 'csv':
            return jsonify({
                'previewable':  True,
                'preview_type': 'html_table',
                'filename':     filename,
                'html':         _csv_to_html(file_path),
            })

        if ext == 'xlsx':
            return jsonify({
                'previewable':  True,
                'preview_type': 'html_table',
                'filename':     filename,
                'html':         _xlsx_to_html(file_path),
            })

        if ext == 'xls':
            return jsonify({
                'previewable':  True,
                'preview_type': 'html_table',
                'filename':     filename,
                'html':         _xls_to_html(file_path),
            })

        if ext == 'docx':
            return jsonify({
                'previewable':  True,
                'preview_type': 'html_doc',
                'filename':     filename,
                'html':         _docx_to_html(file_path),
            })

        if ext == 'doc':
            # old .doc format not supported for preview — user must download
            return jsonify({'previewable': False, 'filename': filename, 'reason': 'doc_old'})

        # any other file type — not previewable, frontend will offer download instead
        return jsonify({'previewable': False, 'filename': filename})

    except Exception as e:
        print(f"[view_file] Error processing file {file_id}: {e}")
        return jsonify({'error': f'שגיאה בעיבוד הקובץ: {str(e)}'}), 500


@app.route('/api/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    # deletes the file record from db AND removes the physical file from disk
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
                os.remove(file_path)  # remove physical file from disk
        conn.close()
        return jsonify({'success': True, 'message': 'הקובץ נמחק בהצלחה'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============= EMAIL LIST =============

@app.route('/api/email-list', methods=['GET'])
def get_email_list():
    # returns all emails in the notification list — shown in the admin panel
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, name, added_by, added_at FROM email_list ORDER BY name')
    emails = [{'id': r[0], 'email': r[1], 'name': r[2], 'added_by': r[3], 'added_at': r[4]}
              for r in cursor.fetchall()]
    conn.close()
    return jsonify(emails)

@app.route('/api/email-list', methods=['POST'])
def add_email():
    # manually adds an email address to the notification list
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
    # removes an email from the notification list
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

# ============= STATS =============

@app.route('/api/stats', methods=['GET'])
def get_stats():
    # powers the four stat cards at the top of the page
    # runs four separate SQL queries — total active, overdue, critical, and by status
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM events
        WHERE is_deleted = 0 AND status NOT IN ('הושלם הטיפול', 'בהקפאה')
    """)
    total_events = cursor.fetchone()[0]
    today = datetime.now().strftime('%Y-%m-%d')
    placeholders = ','.join('?' for _ in CLOSED_STATUSES)  # builds ?,?,? dynamically for the IN clause
    cursor.execute(f'''
        SELECT COUNT(*) FROM events
        WHERE status_deadline < ? AND status NOT IN ({placeholders}) AND is_deleted = 0
    ''', (today, *CLOSED_STATUSES))
    overdue = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM events WHERE urgency = 'קריטית' AND is_deleted = 0")
    critical = cursor.fetchone()[0]
    cursor.execute('SELECT status, COUNT(*) FROM events WHERE is_deleted = 0 GROUP BY status')
    by_status = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return jsonify({'total_events': total_events, 'overdue': overdue,
                    'critical': critical, 'by_status': by_status})

# ============= NOTIFICATIONS =============

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    # returns all users with their notification preferences — used to render the notifications table in admin panel
    # LEFT JOIN means users with no notification row still appear (with 0 defaults via COALESCE)
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
    # toggles a single notification type on or off for a user
    # INSERT OR UPDATE pattern — creates the row if it doesn't exist, updates it if it does
    data = request.json
    field = data.get('field')
    value = data.get('value')
    allowed_fields = ['notify_status_change', 'notify_weekly_report',
                      'notify_new_event', 'notify_responsible', 'notify_overdue']
    if field not in allowed_fields:
        return jsonify({'success': False, 'error': 'Invalid field'}), 400
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
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
    # turns all notification types on or off at once for a user — used by the "select all" checkbox
    data = request.json
    value = data.get('value', 0)
    conn = db.get_connection()
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

# ============= REPORTS =============

@app.route('/api/reports/excel', methods=['GET'])
def generate_excel_report():
    # generates and streams the weekly Excel report directly to the browser as a download
    # fetches events active/created/updated in the last 7 days — file never saved to disk
    from reports import generate_excel_report as build_report
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    cutoff = seven_days_ago.strftime('%Y-%m-%d')
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM events
        WHERE is_deleted = 0
          AND (registration_date >= ? OR DATE(updated_at) >= ? OR completion_date >= ?)
        ORDER BY id ASC
    ''', (cutoff, cutoff, cutoff))
    events = [row_to_event(row) for row in cursor.fetchall()]
    conn.close()
    file_stream = build_report(events, report_date=now)
    return send_file(
        file_stream,
        as_attachment=True,
        download_name=f'דוח_אירועים_שבועי_{now.strftime("%Y%m%d")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

if __name__ == '__main__':
    print("✅ Database initialized successfully!")
    print("🚀 Starting Event Management System...")
    print("🌐 Server running at: http://localhost:5000")
    print("🛑 Press Ctrl+C to stop the server")
    app.run(debug=True, port=5000)