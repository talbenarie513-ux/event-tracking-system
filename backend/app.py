from flask import Flask, request, jsonify, send_file, send_from_directory, make_response
from flask_cors import CORS
from database import Database
import os
import mimetypes
import base64
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

from email_notifications import (
    trigger_new_event,
    trigger_status_change,
    trigger_responsible_assigned,
)

app = Flask(__name__)
CORS(app)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

CLOSED_STATUSES = ('הושלם הטיפול', 'טופל חלקית', 'בהקפאה')

# Base directory = folder where app.py lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_next_available_id(cursor):
    cursor.execute('SELECT MAX(id) FROM events')
    max_id = cursor.fetchone()[0]
    return (max_id + 1) if max_id else 1

db = Database()

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'doc', 'docx', 'pdf', 'png', 'jpg', 'jpeg',
                      'msg', 'shp', 'zip', 'eml', 'csv', 'txt', 'gif', 'webp', 'svg'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def resolve_file_path(stored_path):
    """
    Try to find the actual file on disk given a stored path.
    Handles absolute paths, relative paths, and mixed separators.
    Returns the resolved path if found, or the original stored_path if not.
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

    return stored_path  # not found — return original so caller can report it

def row_to_event(row):
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

@app.route('/')
def serve_index():
    return send_from_directory('..', 'index.html')

@app.route('/app.js')
def serve_js():
    return send_from_directory('..', 'app.js')

# ============= USERS =============

@app.route('/api/users', methods=['GET'])
def get_users():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, role, email FROM users ORDER BY name')
    users = [{'id': r[0], 'name': r[1], 'role': r[2], 'email': r[3]} for r in cursor.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.json
    if not data.get('email'):
        return jsonify({'success': False, 'error': 'אימייל הוא שדה חובה'}), 400
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (name, role, email) VALUES (?, ?, ?)',
                       (data['name'], data['role'], data['email']))
        user_id = cursor.lastrowid
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
    data = request.json
    if not data.get('email'):
        return jsonify({'success': False, 'error': 'אימייל הוא שדה חובה'}), 400
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT email FROM users WHERE id = ?', (user_id,))
        old = cursor.fetchone()
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
    conn = db.get_connection()
    cursor = conn.cursor()
    show_deleted = request.args.get('show_deleted', 'false').lower() == 'true'
    status_filter = request.args.get('status')
    urgency_filter = request.args.get('urgency')
    search = request.args.get('search', '').strip()

    query = 'SELECT * FROM events WHERE 1=1'
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
        query += ' AND (event_summary LIKE ? OR system LIKE ? OR event_details LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])

    query += ' ORDER BY id DESC'
    cursor.execute(query, params)
    events = [row_to_event(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(events)

@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
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
        ORDER BY changed_at ASC
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
        'created_by': created_by,
        'created_at': created_at,
        'entries':    entries,
    })

# ============= CREATE EVENT =============

@app.route('/api/events', methods=['POST'])
def create_event():
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
            event_id = get_next_available_id(cursor)

        if user_role == 'admin':
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
            registration_date  = data['registration_date']
            system             = data['system']
            event_summary      = data['event_summary']
            event_details      = data['event_details']
            affected_customers = data['affected_customers']
            urgency            = data['urgency']
            priority           = data['priority']
            status             = data['status']
            status_deadline    = data['status_deadline']

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

        cursor.execute('INSERT INTO status_history (event_id, status, changed_by) VALUES (?, ?, ?)',
                       (event_id, status, data['created_by']))
        log_audit(cursor, event_id, 'created', data['created_by'])
        conn.commit()
        conn.close()

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
            trigger_responsible_assigned(full_event, "", data["created_by"])

        return jsonify({'success': True, 'message': 'האירוע נוצר בהצלחה', 'event_id': event_id})

    except KeyError as e:
        conn.close()
        return jsonify({'success': False, 'error': f'שדה חובה חסר: {str(e)}'}), 400
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============= UPDATE EVENT =============

@app.route('/api/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    data = request.json
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        old_row = cursor.fetchone()
        if not old_row:
            conn.close()
            return jsonify({'success': False, 'error': 'Event not found'}), 404

        old = row_to_event(old_row)
        old_status      = old['status']
        old_id          = old['id']
        old_responsible = old['responsible_person']

        new_id = data.get('event_id', old_id)
        if new_id is None:
            new_id = old_id
        new_id = int(new_id)

        if new_id != old_id:
            cursor.execute('SELECT id FROM events WHERE id = ? AND id != ?', (new_id, old_id))
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': f'מספר אירוע {new_id} כבר קיים במערכת'}), 400

        new_status      = data.get('status', old_status)
        completion_date = data.get('completion_date')

        if new_status == 'הושלם הטיפול' and not completion_date:
            completion_date = datetime.now().strftime('%Y-%m-%d')
        elif new_status != 'הושלם הטיפול':
            completion_date = None

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

        if new_status != old_status:
            cursor.execute('INSERT INTO status_history (event_id, status, changed_by) VALUES (?, ?, ?)',
                           (event_id, new_status, data.get('updated_by', 'Unknown')))

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
                changes[field] = (old_val, new_val_str)

        if changes:
            log_audit(cursor, new_id, 'updated', data.get('updated_by', 'Unknown'), changes)

        conn.commit()

        conn2 = db.get_connection()
        cur2  = conn2.cursor()
        cur2.execute("SELECT * FROM events WHERE id = ?", (new_id,))
        updated_row = cur2.fetchone()
        conn2.close()

        if updated_row:
            updated_event = row_to_event(updated_row)
            if new_status != old_status:
                trigger_status_change(updated_event, old_status, data.get("updated_by", ""))
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
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'File type not allowed'}), 400

    event_folder = os.path.join(UPLOAD_FOLDER, str(event_id))
    if not os.path.exists(event_folder):
        os.makedirs(event_folder)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = secure_filename(file.filename)
    # Store path relative to BASE_DIR so it resolves correctly regardless of cwd
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
            os.remove(abs_path)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events/<int:event_id>/files', methods=['GET'])
def get_event_files(event_id):
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
    """Legacy endpoint — kept for compatibility."""
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
    """Returns file as plain binary — works correctly inside pywebview."""
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
        mime = 'application/octet-stream'

    with open(file_path, 'rb') as f:
        data = f.read()

    response = make_response(data)
    response.headers['Content-Type'] = mime
    response.headers['Content-Disposition'] = f'attachment; filename="{row[0]}"'
    response.headers['Content-Length'] = len(data)
    return response


# ============= FILE VIEW HELPERS =============

def _xlsx_to_html(file_path):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        html_parts = []
        for sheet in wb.worksheets:
            html_parts.append(f'<h3 style="color:#667eea;margin:16px 0 8px;">גיליון: {sheet.title}</h3>')
            html_parts.append(
                '<div style="overflow-x:auto;">'
                '<table style="border-collapse:collapse;width:100%;font-size:13px;direction:ltr;">'
            )
            for r_idx, row in enumerate(sheet.iter_rows(values_only=True)):
                tag = 'th' if r_idx == 0 else 'td'
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
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception:
                with open(file_path, 'rb') as f:
                    content = f.read().decode('utf-8', errors='replace')
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
            return jsonify({'previewable': False, 'filename': filename, 'reason': 'doc_old'})

        return jsonify({'previewable': False, 'filename': filename})

    except Exception as e:
        print(f"[view_file] Error processing file {file_id}: {e}")
        return jsonify({'error': f'שגיאה בעיבוד הקובץ: {str(e)}'}), 500


@app.route('/api/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
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

# ============= EMAIL LIST =============

@app.route('/api/email-list', methods=['GET'])
def get_email_list():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, name, added_by, added_at FROM email_list ORDER BY name')
    emails = [{'id': r[0], 'email': r[1], 'name': r[2], 'added_by': r[3], 'added_at': r[4]}
              for r in cursor.fetchall()]
    conn.close()
    return jsonify(emails)

@app.route('/api/email-list', methods=['POST'])
def add_email():
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
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM events
        WHERE is_deleted = 0 AND status NOT IN ('הושלם הטיפול', 'בהקפאה')
    """)
    total_events = cursor.fetchone()[0]
    today = datetime.now().strftime('%Y-%m-%d')
    placeholders = ','.join('?' for _ in CLOSED_STATUSES)
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