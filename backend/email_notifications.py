import smtplib  # built-in — handles the actual SMTP connection and email sending
from email.mime.text import MIMEText          # built-in — creates plain text or HTML email body parts
from email.mime.multipart import MIMEMultipart # built-in — container that holds body + attachments together
from email.mime.base import MIMEBase          # built-in — base class for file attachments
from email import encoders                    # built-in — encodes attachments as base64 for safe email transport
from datetime import datetime, timedelta      # built-in — date calculations for overdue checks and report ranges
from io import BytesIO                        # built-in — in-memory file buffer, used to attach Excel without saving to disk
from database import Database                 # our own db manager


"""
HOW TO ACTIVATE EMAILS — READ THIS FIRST:
──────────────────────────────────────────
When you are ready to send real emails, scroll down to the SMTP_CONFIG
block (about 30 lines below) and fill in:
  1. "host"       — your mail server address
  2. "from_email" — the sender email address (e.g. noreply@geoda.co.il)
  3. "username"   — login for the mail server (usually same as from_email)
  4. "password"   — your SMTP password or app-password

Until those 4 fields are filled, the system runs in STUB MODE:
every email is printed to the console instead of being sent.
No crashes, no errors — just logs.

WHERE EACH EMAIL GOES:
──────────────────────
Every user in the system has an email address stored in the `users` table.
The email_notifications table stores their preferences (0 = off, 1 = on).
This module always looks up the user's email from the database before sending,
so as long as the user has a valid email saved, they will receive notifications
for whichever notification types are enabled for them in the admin panel.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# ▼▼▼  FILL IN YOUR EMAIL DETAILS HERE WHEN READY  ▼▼▼
# ═══════════════════════════════════════════════════════════════════════════════

SMTP_CONFIG = {
    # all fields empty = stub mode (emails printed to console, not sent)
    # ⚠️ storing passwords here in plain text is not ideal — use environment variables in production

    "host":       "",     # your mail server e.g. "smtp.gmail.com" or "mail.geoda.co.il"
    "from_email": "",     # the address emails are sent FROM e.g. "noreply@geoda.co.il"
    "username":   "",     # login username — usually same as from_email
    "password":   "",     # SMTP password or app-password (Gmail: generate at myaccount.google.com/apppasswords)

    "port":       587,    # 587 = STARTTLS (most common), 465 = SSL, 25 = plain
    "use_tls":    True,   # True for port 587 (STARTTLS) — upgrades connection to encrypted after connecting
    "use_ssl":    False,  # True for port 465 (SSL) — encrypted from the start. Set use_tls=False if using this
    "from_name":  "מערכת ניהול בעיות — גאודה",  # display name shown in the From field of the email
}

# ═══════════════════════════════════════════════════════════════════════════════

# statuses that mean an event is "done" — used to exclude closed events from overdue checks
CLOSED_STATUSES = ('הושלם הטיפול', 'טופל חלקית', 'בהקפאה')

db = Database()  # single shared db instance for this whole file


# ═══════════════════════════════════════════════════════════════════════════════
# CORE SEND FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def send_email(to_email: str, subject: str, html_body: str,
               text_body: str = "", attachment: tuple | None = None) -> bool:

    # if SMTP not configured — print to console instead of sending (stub mode)
    if not SMTP_CONFIG["host"] or not SMTP_CONFIG["from_email"]:
        print(f"\n[EMAIL STUB] {'─'*60}")
        print(f"  To      : {to_email}")
        print(f"  Subject : {subject}")
        print(f"  Preview : {text_body[:300] if text_body else '(html only)'}")
        if attachment:
            print(f"  Attach  : {attachment[0]}")
        print(f"{'─'*62}\n")
        return True

    try:
        # MIMEMultipart("mixed") = outer container that can hold both content and file attachments
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"]    = f"{SMTP_CONFIG['from_name']} <{SMTP_CONFIG['from_email']}>"
        msg["To"]      = to_email

        # MIMEMultipart("alternative") = inner container with both plain text and HTML versions
        # email clients pick whichever they support — always including plain text is good practice
        alt = MIMEMultipart("alternative")
        if text_body:
            alt.attach(MIMEText(text_body, "plain", "utf-8"))
        alt.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt)

        if attachment:
            # attach a file (e.g. the Excel report) to the email
            fname, fdata = attachment
            part = MIMEBase("application", "octet-stream")  # generic binary type works for any file
            part.set_payload(fdata.read())
            encoders.encode_base64(part)  # converts binary to base64 text for safe email transport
            part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
            msg.attach(part)

        # connect to mail server — two options depending on config
        if SMTP_CONFIG["use_ssl"]:
            server = smtplib.SMTP_SSL(SMTP_CONFIG["host"], SMTP_CONFIG["port"])  # encrypted from start (port 465)
        else:
            server = smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"])      # plain connection first
            if SMTP_CONFIG["use_tls"]:
                server.starttls()  # upgrade to encrypted (port 587)

        if SMTP_CONFIG["username"] and SMTP_CONFIG["password"]:
            server.login(SMTP_CONFIG["username"], SMTP_CONFIG["password"])

        server.sendmail(SMTP_CONFIG["from_email"], to_email, msg.as_string())
        server.quit()  # always close the connection after sending
        # ⚠️ connection is opened/closed per email — inefficient for bulk sending
        print(f"[EMAIL] ✅ Sent → {to_email} | {subject}")
        return True

    except Exception as e:
        print(f"[EMAIL] ❌ Failed → {to_email}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# HTML EMAIL WRAPPER
# ═══════════════════════════════════════════════════════════════════════════════

def _html_wrap(title: str, body_html: str) -> str:
    # wraps any email content in a consistent styled layout — purple header, table styles, footer
    # {{ double braces in the CSS are needed because this is an f-string — single { would be Python variables
    return f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
  body       {{ font-family:Arial,sans-serif; background:#f0f4ff; margin:0; padding:20px; direction:rtl; }}
  .wrapper   {{ max-width:700px; margin:auto; background:#fff; border-radius:12px;
                box-shadow:0 4px 20px rgba(0,0,0,.1); overflow:hidden; }}
  .header    {{ background:linear-gradient(135deg,#667eea,#764ba2); padding:26px 32px; }}
  .header h1 {{ color:#fff; margin:0; font-size:19px; }}
  .header p  {{ color:#e2e8f0; margin:5px 0 0; font-size:12px; }}
  .content   {{ padding:26px 32px; color:#2d3748; line-height:1.7; }}
  .content h2{{ color:#667eea; font-size:16px; margin-top:0; }}
  table.ev   {{ width:100%; border-collapse:collapse; margin:16px 0; font-size:13px; }}
  table.ev th{{ background:#667eea; color:#fff; padding:9px 13px; text-align:right; }}
  table.ev td{{ padding:8px 13px; border-bottom:1px solid #e2e8f0; vertical-align:top; }}
  table.ev tr:nth-child(even) td {{ background:#f7fafc; }}
  .badge     {{ display:inline-block; padding:2px 9px; border-radius:12px; font-size:12px; font-weight:bold; }}
  .critical  {{ background:#fed7d7; color:#c53030; }}
  .high      {{ background:#feebc8; color:#c05621; }}
  .medium    {{ background:#fefcbf; color:#744210; }}
  .low       {{ background:#c6f6d5; color:#276749; }}
  .footer    {{ background:#f7fafc; padding:16px 32px; font-size:11px; color:#718096;
                border-top:1px solid #e2e8f0; text-align:center; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>🛠️ מערכת מעקב ופיתוח — גאודה</h1>
    <p>{title}</p>
  </div>
  <div class="content">{body_html}</div>
  <div class="footer">
    הודעה אוטומטית | {datetime.now().strftime('%d/%m/%Y %H:%M')} | לא להשיב למייל זה
  </div>
</div>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_users_with_pref(notify_field: str) -> list[dict]:
    # returns all users who have a specific notification type turned ON
    # the same function works for all 5 notification types by passing the field name
    # ⚠️ notify_field is injected directly into SQL — safe here because it always comes from our own code, not user input
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT u.id, u.name, u.email
        FROM users u
        JOIN email_notifications n ON u.id = n.user_id
        WHERE n.{notify_field} = 1
          AND u.email IS NOT NULL
          AND trim(u.email) != ''
    """)
    rows = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "name": r[1], "email": r[2]} for r in rows]


def _get_user_email(user_name: str) -> str | None:
    # looks up a user's email by their name — returns None if not found or email is empty
    # used to send emails directly to the responsible person
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT email FROM users WHERE name = ? AND email IS NOT NULL AND trim(email) != ''",
        (user_name,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _urgency_badge(urgency: str) -> str:
    # returns a colored HTML badge span for the urgency level — used inside email tables
    cls = {"קריטית": "critical", "גבוהה": "high", "בינונית": "medium", "נמוכה": "low"}.get(urgency, "low")
    return f'<span class="badge {cls}">{urgency}</span>'

def _fmt_date(d) -> str:
    # converts database date format (2024-01-15) to display format (15/01/2024)
    if not d:
        return "—"
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(d)

def _ev(event: dict, key: str, fallback: str = "—") -> str:
    # safely gets a value from the event dict — returns fallback if missing/empty
    # prevents emails showing "None" or blank cells
    val = event.get(key)
    return str(val).strip() if val and str(val).strip() else fallback


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION 1 — שינוי סטטוס (Status Change)
# ═══════════════════════════════════════════════════════════════════════════════

def trigger_status_change(event: dict, old_status: str, changed_by: str):
    # fired from app.py whenever an event's status changes
    # sends to all subscribers + directly to the responsible person if not already subscribed
    recipients = _get_users_with_pref("notify_status_change")

    eid         = _ev(event, 'id')
    summary     = _ev(event, 'event_summary')
    status      = _ev(event, 'status')
    details     = _ev(event, 'status_details')
    urgency     = _ev(event, 'urgency')
    deadline    = _fmt_date(_ev(event, 'status_deadline', ''))
    responsible = _ev(event, 'responsible_person')
    system      = _ev(event, 'system')

    subject = f"[גאודה] עדכון סטטוס — אירוע #{eid} | {summary[:45]}"

    body_html = f"""
    <h2>🔄 עדכון סטטוס אירוע</h2>
    <p>לידיעתכם, אירוע מס' <strong>#{eid}</strong>
       בנושא <strong>{summary}</strong>
       שינה סטטוס ל<strong>{status}</strong>.</p>
    <table class="ev">
      <tr><th>שדה</th><th>ערך</th></tr>
      <tr><td><strong>מספר אירוע</strong></td> <td>#{eid}</td></tr>
      <tr><td><strong>נושא</strong></td>         <td>{summary}</td></tr>
      <tr><td><strong>מערכת</strong></td>         <td>{system}</td></tr>
      <tr><td><strong>סטטוס קודם</strong></td>   <td>{old_status}</td></tr>
      <tr><td><strong>סטטוס חדש</strong></td>    <td><strong>{status}</strong></td></tr>
      <tr><td><strong>פירוט סטטוס</strong></td>  <td>{details}</td></tr>
      <tr><td><strong>דחיפות</strong></td>         <td>{_urgency_badge(urgency)}</td></tr>
      <tr><td><strong>לו"ז</strong></td>            <td>{deadline}</td></tr>
      <tr><td><strong>גורם אחראי</strong></td>    <td>{responsible}</td></tr>
      <tr><td><strong>עודכן על ידי</strong></td>  <td>{changed_by}</td></tr>
      <tr><td><strong>תאריך עדכון</strong></td>   <td>{datetime.now().strftime('%d/%m/%Y %H:%M')}</td></tr>
    </table>"""

    text_body = (
        f"עדכון סטטוס אירוע: לידיעתכם, אירוע מס' #{eid} "
        f"בנושא {summary} שינה סטטוס ל{status}."
    )

    html = _html_wrap(f"עדכון סטטוס — אירוע #{eid}", body_html)

    # send to general subscribers first, track who already got it to avoid duplicates
    already_sent: set[str] = set()
    for user in recipients:
        send_email(user["email"], subject, html, text_body)
        already_sent.add(user["email"])

    # also notify the responsible person directly even if they're not a subscriber
    resp_name = _ev(event, 'responsible_person', '')
    if resp_name and resp_name != '—':
        resp_email = _get_user_email(resp_name)
        if resp_email and resp_email not in already_sent:
            send_email(resp_email, subject, html, text_body)


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION 2 — יצירת אירוע (New Event Created)
# ═══════════════════════════════════════════════════════════════════════════════

def trigger_new_event(event: dict, created_by: str):
    # fired from app.py when a new event is created
    # sends to all users subscribed to new event notifications
    recipients = _get_users_with_pref("notify_new_event")
    if not recipients:
        return  # exit early if nobody is subscribed — no point building the email

    eid         = _ev(event, 'id')
    summary     = _ev(event, 'event_summary')
    details     = _ev(event, 'event_details')
    system      = _ev(event, 'system')
    customers   = _ev(event, 'affected_customers')
    urgency     = _ev(event, 'urgency')
    priority    = _ev(event, 'priority')
    status      = _ev(event, 'status')
    deadline    = _fmt_date(_ev(event, 'status_deadline', ''))
    responsible = _ev(event, 'responsible_person')
    reg_date    = _fmt_date(_ev(event, 'registration_date', ''))

    subject = f"[גאודה] אירוע חדש #{eid} — {summary[:45]}"

    body_html = f"""
    <h2>🆕 יצירת אירוע חדש</h2>
    <p>לידיעתכם, נוצר אירוע חדש על ידי <strong>{created_by}</strong>
       בנושא <strong>{summary}</strong>,
       ברמת דחיפות <strong>{urgency}</strong>.</p>
    <table class="ev">
      <tr><th>שדה</th><th>ערך</th></tr>
      <tr><td><strong>מספר אירוע</strong></td>   <td>#{eid}</td></tr>
      <tr><td><strong>תאריך רישום</strong></td>  <td>{reg_date}</td></tr>
      <tr><td><strong>נושא</strong></td>           <td>{summary}</td></tr>
      <tr><td><strong>פירוט</strong></td>          <td>{details}</td></tr>
      <tr><td><strong>מערכת</strong></td>          <td>{system}</td></tr>
      <tr><td><strong>לקוחות מושפעים</strong></td><td>{customers}</td></tr>
      <tr><td><strong>דחיפות</strong></td>          <td>{_urgency_badge(urgency)}</td></tr>
      <tr><td><strong>עדיפות</strong></td>          <td>{priority}</td></tr>
      <tr><td><strong>סטטוס</strong></td>           <td>{status}</td></tr>
      <tr><td><strong>לו"ז</strong></td>             <td>{deadline}</td></tr>
      <tr><td><strong>גורם אחראי</strong></td>      <td>{responsible}</td></tr>
      <tr><td><strong>נוצר על ידי</strong></td>     <td>{created_by}</td></tr>
    </table>"""

    text_body = (
        f"יצירת אירוע חדש: לידיעתכם, נוצר אירוע חדש על ידי {created_by} "
        f"בנושא {summary}, ברמת דחיפות {urgency}."
    )

    html = _html_wrap(f"אירוע חדש #{eid}", body_html)

    for user in recipients:
        send_email(user["email"], subject, html, text_body)


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION 3 — משתמש אחראי (Responsible Person Assigned)
# ═══════════════════════════════════════════════════════════════════════════════

def trigger_responsible_assigned(event: dict, old_responsible: str, changed_by: str):
    # fired from app.py when a responsible person is assigned or changed
    # sends directly to the newly assigned person + all subscribers
    new_responsible = _ev(event, 'responsible_person', '')

    # exit early if nothing actually changed or no responsible person set
    if not new_responsible or new_responsible == '—' or new_responsible == old_responsible:
        return

    eid        = _ev(event, 'id')
    summary    = _ev(event, 'event_summary')
    details    = _ev(event, 'event_details')
    system     = _ev(event, 'system')
    customers  = _ev(event, 'affected_customers')
    urgency    = _ev(event, 'urgency')
    status     = _ev(event, 'status')
    deadline   = _fmt_date(_ev(event, 'status_deadline', ''))
    st_details = _ev(event, 'status_details')

    subject = f"[גאודה] משתמש אחראי — אירוע #{eid} | {summary[:40]}"

    def _build_html() -> str:
        # inner function builds the HTML — called separately for each recipient to keep it clean
        return _html_wrap(
            f"משתמש אחראי — אירוע #{eid}",
            f"""
            <h2>👤 משתמש אחראי</h2>
            <p>לידיעתכם, לאירוע בנושא <strong>{summary}</strong>
               הוזן משתמש אחראי בשם <strong>{new_responsible}</strong>.</p>
            <table class="ev">
              <tr><th>שדה</th><th>ערך</th></tr>
              <tr><td><strong>מספר אירוע</strong></td>    <td>#{eid}</td></tr>
              <tr><td><strong>נושא</strong></td>            <td>{summary}</td></tr>
              <tr><td><strong>פירוט</strong></td>           <td>{details}</td></tr>
              <tr><td><strong>מערכת</strong></td>           <td>{system}</td></tr>
              <tr><td><strong>לקוחות מושפעים</strong></td> <td>{customers}</td></tr>
              <tr><td><strong>דחיפות</strong></td>           <td>{_urgency_badge(urgency)}</td></tr>
              <tr><td><strong>סטטוס</strong></td>            <td>{status}</td></tr>
              <tr><td><strong>פירוט סטטוס</strong></td>    <td>{st_details}</td></tr>
              <tr><td><strong>לו"ז לטיפול</strong></td>    <td><strong>{deadline}</strong></td></tr>
              <tr><td><strong>גורם אחראי חדש</strong></td> <td><strong>{new_responsible}</strong></td></tr>
              {f'<tr><td><strong>אחראי קודם</strong></td><td>{old_responsible}</td></tr>' if old_responsible else ''}
            </table>
            <p style="color:#c05621;font-weight:bold;">
              ⚠️ יש לטפל באירוע זה בהתאם לעדיפות ולו"ז המוגדרים.
            </p>"""
        )

    text_body = (
        f"משתמש אחראי: לידיעתכם, לאירוע בנושא {summary} "
        f"הוזן משתמש אחראי בשם {new_responsible}."
    )

    # send directly to the newly assigned person first
    assigned_email = _get_user_email(new_responsible)
    if assigned_email:
        send_email(assigned_email, subject, _build_html(), text_body)

    # then send to all subscribers — skip the assigned person if they're already a subscriber
    for user in _get_users_with_pref("notify_responsible"):
        if user["email"] != assigned_email:
            send_email(user["email"], subject, _build_html(), text_body)


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION 4 — אירוע באיחור (Overdue Events — daily digest)
# ═══════════════════════════════════════════════════════════════════════════════

def send_overdue_notifications():
    # called daily at 08:00 by the scheduler
    # sends each responsible person a personalized list of only their overdue events
    # then sends the full overdue list to all general subscribers (e.g. managers)
    today     = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")

    conn   = db.get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in CLOSED_STATUSES)  # builds ?,?,? for the IN clause
    cursor.execute(f"""
        SELECT id, registration_date, system, event_summary, urgency,
               priority, status, status_deadline, responsible_person
        FROM events
        WHERE status_deadline < ?
          AND status NOT IN ({placeholders})
          AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY status_deadline ASC  -- oldest overdue events first
    """, (today_str, *CLOSED_STATUSES))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("[EMAIL] No overdue events today — skipping overdue notifications.")
        return  # nothing to send

    overdue = [
        {
            "id":                 r[0],
            "registration_date":  r[1],
            "system":             r[2],
            "event_summary":      r[3],
            "urgency":            r[4],
            "priority":           r[5],
            "status":             r[6],
            "status_deadline":    r[7],
            "responsible_person": r[8],
        }
        for r in rows
    ]

    # track already-notified emails to avoid sending duplicates in the general digest below
    already_notified: set[str] = set()

    # group overdue events by responsible person using defaultdict
    from collections import defaultdict
    events_by_responsible: dict = defaultdict(list)
    for ev in overdue:
        resp = (ev.get("responsible_person") or "").strip()
        if resp:
            events_by_responsible[resp].append(ev)

    # send each responsible person only their own overdue events
    for resp_name, resp_events in events_by_responsible.items():
        resp_email = _get_user_email(resp_name)
        if not resp_email:
            continue  # skip if no email found for this person

        count = len(resp_events)
        subj  = f"[גאודה] ⚠️ אירועים באיחור — {count} אירועים מחכים לטיפולך | {today.strftime('%d/%m/%Y')}"

        rows_html   = ""
        plain_lines = []
        for ev in resp_events:
            try:
                dl        = datetime.strptime(ev["status_deadline"], "%Y-%m-%d").date()
                days_late = (today - dl).days  # how many days past the deadline
            except Exception:
                days_late = "?"

            rows_html += f"""
            <tr>
              <td>#{ev['id']}</td>
              <td>{ev['event_summary'] or '—'}</td>
              <td>{ev['system'] or '—'}</td>
              <td>{_urgency_badge(ev['urgency'] or '—')}</td>
              <td>{ev['status'] or '—'}</td>
              <td style="color:#c53030;font-weight:bold;">{_fmt_date(ev['status_deadline'])}</td>
              <td style="color:#c53030;font-weight:bold;">+{days_late} ימים</td>
            </tr>"""
            plain_lines.append(
                f"לידיעתך, אירוע {ev['event_summary']} אינו עומד בלו\"ז שהוקצה לטיפולו."
            )

        body_html = f"""
        <h2>⚠️ אירועים שבאחריותך — חלף המועד</h2>
        <p>שלום <strong>{resp_name}</strong>,<br>
           להלן רשימת האירועים שבאחריותך שחלף מועד הטיפול בהם:</p>
        <table class="ev">
          <tr>
            <th>מס"ד</th><th>נושא</th><th>מערכת</th><th>דחיפות</th>
            <th>סטטוס</th><th>לו"ז</th><th>איחור</th>
          </tr>
          {rows_html}
        </table>
        <p style="color:#c53030;font-weight:bold;">סה"כ {count} אירועים באיחור הדורשים את טיפולך.</p>"""

        text_body = "חלף המועד:\n" + "\n".join(plain_lines)
        html = _html_wrap(f"אירועים באיחור — {today.strftime('%d/%m/%Y')}", body_html)
        send_email(resp_email, subj, html, text_body)
        already_notified.add(resp_email)

    # send the full overdue list to general subscribers (e.g. managers who want to see everything)
    recipients = _get_users_with_pref("notify_overdue")
    if not recipients:
        return

    subject = f"[גאודה] ⚠️ חלף המועד — {len(overdue)} אירועים באיחור | {today.strftime('%d/%m/%Y')}"

    rows_html   = ""
    plain_lines = []

    for ev in overdue:
        try:
            dl        = datetime.strptime(ev["status_deadline"], "%Y-%m-%d").date()
            days_late = (today - dl).days
        except Exception:
            days_late = "?"

        ev_id      = ev["id"]
        ev_summary = ev["event_summary"] or "—"
        ev_system  = ev["system"]        or "—"
        ev_urgency = ev["urgency"]       or "—"
        ev_status  = ev["status"]        or "—"
        ev_deadline= _fmt_date(ev["status_deadline"])
        ev_resp    = ev["responsible_person"] or "—"

        rows_html += f"""
        <tr>
          <td>#{ev_id}</td>
          <td>{ev_summary}</td>
          <td>{ev_system}</td>
          <td>{_urgency_badge(ev_urgency)}</td>
          <td>{ev_status}</td>
          <td style="color:#c53030;font-weight:bold;">{ev_deadline}</td>
          <td style="color:#c53030;font-weight:bold;">+{days_late} ימים</td>
          <td>{ev_resp}</td>
        </tr>"""

        plain_lines.append(
            f"לידיעתכם, אירוע {ev_summary} אינו עומד בלו\"ז שהוקצה לטיפולו."
        )

    body_html = f"""
    <h2>⚠️ חלף המועד</h2>
    <p>לידיעתכם, האירועים הבאים אינם עומדים בלו"ז שהוקצה לטיפולם:</p>
    <table class="ev">
      <tr>
        <th>מס"ד</th><th>נושא</th><th>מערכת</th><th>דחיפות</th>
        <th>סטטוס</th><th>לו"ז</th><th>איחור</th><th>אחראי</th>
      </tr>
      {rows_html}
    </table>
    <p style="color:#c53030;font-weight:bold;">סה"כ {len(overdue)} אירועים באיחור.</p>"""

    text_body = "חלף המועד:\n" + "\n".join(plain_lines)
    html = _html_wrap(f"חלף המועד — {today.strftime('%d/%m/%Y')}", body_html)

    for user in recipients:
        send_email(user["email"], subject, html, text_body)


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION 5 — דוח שבועי (Weekly Report)
# ═══════════════════════════════════════════════════════════════════════════════

def send_weekly_report():
    # called every Sunday at 08:00 by the scheduler
    # generates the Excel report and emails it to all weekly report subscribers
    from reports import generate_excel_report  # imported here to avoid circular imports at module level

    now          = datetime.now()
    today        = now.date()
    today_str    = today.strftime("%Y-%m-%d")
    week_ago_str = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    recipients = _get_users_with_pref("notify_weekly_report")
    if not recipients:
        return  # nobody subscribed — skip everything

    conn   = db.get_connection()
    cursor = conn.cursor()

    # fetch events active in the last 7 days — same logic as the manual report button
    cursor.execute("""
        SELECT * FROM events
        WHERE is_deleted = 0
          AND (
              registration_date >= ?
              OR DATE(updated_at)  >= ?
              OR completion_date   >= ?
          )
        ORDER BY id ASC
    """, (week_ago_str, week_ago_str, week_ago_str))

    def _row_to_event(row):
        # local helper — duplicated here to avoid importing from app.py (circular import risk)
        return {
            'id': row[0], 'registration_date': row[1], 'first_contact_date': row[2],
            'system': row[3], 'event_summary': row[4], 'event_details': row[5],
            'affected_customers': row[6], 'urgency': row[7], 'priority': row[8],
            'status': row[9], 'status_details': row[10], 'event_classification': row[11],
            'status_deadline': row[12], 'completion_date': row[13],
            'responsible_person': row[14], 'price_quote': row[15],
            'additional_notes': row[16], 'created_by': row[17],
            'created_at': row[18], 'updated_at': row[19], 'is_deleted': row[20],
        }

    report_events = [_row_to_event(r) for r in cursor.fetchall()]

    ph = ",".join("?" for _ in CLOSED_STATUSES)

    # gather summary stats for the email body
    cursor.execute(f"""
        SELECT COUNT(*) FROM events
        WHERE status NOT IN ({ph}) AND (is_deleted=0 OR is_deleted IS NULL)
    """, CLOSED_STATUSES)
    active_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM events
        WHERE registration_date >= ? AND (is_deleted=0 OR is_deleted IS NULL)
    """, (week_ago_str,))
    new_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM events
        WHERE status = 'הושלם הטיפול'
          AND completion_date >= ?
          AND (is_deleted=0 OR is_deleted IS NULL)
    """, (week_ago_str,))
    completed_count = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT COUNT(*) FROM events
        WHERE status_deadline < ?
          AND status NOT IN ({ph})
          AND (is_deleted=0 OR is_deleted IS NULL)
    """, (today_str, *CLOSED_STATUSES))
    overdue_count = cursor.fetchone()[0]

    conn.close()

    # generate Excel report once in memory as a BytesIO stream
    excel_stream: BytesIO = generate_excel_report(report_events, report_date=now)
    excel_filename = f"דוח_אירועים_שבועי_{now.strftime('%Y%m%d')}.xlsx"

    subject = (
        f"[גאודה] 📊 דוח אירועים שבועי — {today.strftime('%d/%m/%Y')} | "
        f"{active_count} אירועים פעילים"
    )

    body_html = f"""
    <h2>📊 דוח אירועים שבועי</h2>
    <p>מצורף בזאת דוח אירועים שבועי, מעודכן.</p>
    <table class="ev" style="max-width:400px;">
      <tr><th colspan="2">סיכום — {today.strftime('%d/%m/%Y')}</th></tr>
      <tr><td>אירועים פעילים</td>
          <td><strong>{active_count}</strong></td></tr>
      <tr><td>נפתחו השבוע</td>
          <td><strong style="color:#48bb78;">{new_count}</strong></td></tr>
      <tr><td>הושלמו השבוע</td>
          <td><strong style="color:#667eea;">{completed_count}</strong></td></tr>
      <tr><td>אירועים באיחור</td>
          <td><strong style="color:#c53030;">{overdue_count}</strong></td></tr>
      <tr><td>אירועים בדוח המצורף</td>
          <td><strong>{len(report_events)}</strong></td></tr>
    </table>
    <p style="color:#718096;font-size:13px;">
      הדוח המלא מצורף כקובץ Excel ומכסה את הפעילות בין
      <strong>{(today - timedelta(days=7)).strftime('%d/%m/%Y')}</strong>
      ל-<strong>{today.strftime('%d/%m/%Y')}</strong>.
    </p>"""

    text_body = "דוח אירועים שבועי: מצורף בזאת דוח אירועים שבועי, מעודכן."

    html = _html_wrap(f"דוח שבועי — {today.strftime('%d/%m/%Y')}", body_html)

    for user in recipients:
        excel_stream.seek(0)  # ⚠️ must rewind to start before each send — otherwise 2nd recipient gets empty file
        send_email(
            user["email"], subject, html, text_body,
            attachment=(excel_filename, excel_stream)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER — Timed Jobs
# ═══════════════════════════════════════════════════════════════════════════════

def start_scheduler():
    # starts a background scheduler that runs email jobs on a timer
    # called once from main.py when the app launches
    # ⚠️ if the app is shut down overnight, scheduled jobs won't run — no persistent job queue
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        # BackgroundScheduler runs in a separate thread — doesn't block the Flask server

        scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")  # all times in Israel timezone

        # daily overdue check — runs every day at 08:00
        scheduler.add_job(
            send_overdue_notifications,
            trigger="cron",
            hour=8, minute=0,
            id="overdue_daily",
            replace_existing=True  # prevents duplicate jobs if scheduler is restarted
        )

        # weekly report — runs every Sunday at 08:00
        scheduler.add_job(
            send_weekly_report,
            trigger="cron",
            day_of_week="sun",
            hour=8, minute=0,
            id="weekly_report",
            replace_existing=True
        )

        scheduler.start()
        print("[SCHEDULER] ✅ Started — overdue: daily 08:00 | weekly report: Sunday 08:00")
        return scheduler

    except ImportError:
        print("[SCHEDULER] ⚠️  APScheduler not installed. Run: pip install apscheduler")
        return None