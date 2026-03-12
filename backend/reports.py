import xlsxwriter          # creates Excel .xlsx files with full formatting support
from io import BytesIO     # in-memory file buffer — lets us build the Excel file without saving to disk
from datetime import datetime, timedelta  # date calculations for the 7-day report window
from database import Database             # our own db manager — used only by get_weekly_report_data()


def generate_excel_report(events, filename=None, report_date=None):
    """
    Takes a list of event dicts and returns a formatted Excel file as a BytesIO stream.
    Called from two places:
      - app.py  → when user clicks the "generate report" button
      - email_notifications.py → when the weekly report email is sent
    ⚠️ filename parameter is accepted but never used — left over from an earlier version
    """

    if report_date is None:
        report_date = datetime.now()

    output = BytesIO()  # in-memory buffer — the Excel file is written here instead of to disk
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})  # in_memory=True keeps everything in RAM
    worksheet = workbook.add_worksheet('אירועים')
    worksheet.right_to_left()  # flips the whole sheet for Hebrew — columns start from the right

    # ── FORMATS ──────────────────────────────────────────────────────────────
    # in xlsxwriter all styles must be defined upfront as format objects, then applied to cells
    # you cannot style a cell after writing to it

    # purple title bar at the top of the report
    title_fmt = workbook.add_format({
        'bold': True, 'font_size': 13,
        'font_color': '#FFFFFF', 'bg_color': '#4C51BF',
        'align': 'right', 'valign': 'vcenter',
        'border': 0
    })

    # label cell in the date info row (e.g. "תאריך הפקת הדוח:")
    date_label_fmt = workbook.add_format({
        'bold': True, 'font_size': 11,
        'font_color': '#4C51BF', 'bg_color': '#EBF4FF',
        'align': 'right', 'valign': 'vcenter',
        'border': 1, 'border_color': '#C3DAFE'
    })

    # value cell in the date info row (the actual date value)
    date_value_fmt = workbook.add_format({
        'font_size': 11, 'bold': True,
        'font_color': '#2D3748', 'bg_color': '#EBF4FF',
        'align': 'right', 'valign': 'vcenter',
        'border': 1, 'border_color': '#C3DAFE'
    })

    # italic range info cell (shows the date range the report covers)
    range_fmt = workbook.add_format({
        'font_size': 10, 'italic': True,
        'font_color': '#718096', 'bg_color': '#EBF4FF',
        'align': 'right', 'valign': 'vcenter',
        'border': 1, 'border_color': '#C3DAFE'
    })

    # purple column header cells
    header_fmt = workbook.add_format({
        'bold': True, 'font_size': 11,
        'font_color': '#FFFFFF', 'bg_color': '#667EEA',
        'border': 1, 'border_color': '#5A67D8',
        'align': 'center', 'valign': 'vcenter',
        'text_wrap': True  # allows header text to wrap to multiple lines
    })

    # standard white data cell
    cell_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E2E8F0',
        'align': 'right', 'valign': 'top', 'text_wrap': True,
        'bg_color': '#FFFFFF'
    })

    # alternating light grey data cell — creates zebra stripe effect
    cell_alt_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E2E8F0',
        'align': 'right', 'valign': 'top', 'text_wrap': True,
        'bg_color': '#F7FAFC'
    })

    # red background for overdue event rows
    overdue_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#F56565',
        'align': 'right', 'valign': 'top', 'text_wrap': True,
        'bg_color': '#FED7D7'
    })

    # bright red + bold for critical urgency cells specifically
    critical_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E53E3E',
        'align': 'right', 'valign': 'top', 'text_wrap': True,
        'bg_color': '#FC8181', 'font_color': '#63171B', 'bold': True
    })

    # green background for completed event rows
    completed_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#48BB78',
        'align': 'right', 'valign': 'top', 'text_wrap': True,
        'bg_color': '#9AE6B4', 'font_color': '#1C4532'
    })

    # centered number cell (for ID and priority columns) — white background
    number_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E2E8F0',
        'align': 'center', 'valign': 'top',
        'bg_color': '#FFFFFF'
    })

    # centered number cell — alternating grey background
    number_alt_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E2E8F0',
        'align': 'center', 'valign': 'top',
        'bg_color': '#F7FAFC'
    })

    # dark purple header for the summary section at the bottom
    summary_header_fmt = workbook.add_format({
        'bold': True, 'font_size': 11,
        'font_color': '#FFFFFF', 'bg_color': '#4C51BF',
        'border': 1, 'align': 'right', 'valign': 'vcenter'
    })

    # light blue label cell in the summary section
    summary_cell_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E2E8F0',
        'align': 'right', 'valign': 'vcenter',
        'bg_color': '#EBF4FF'
    })

    # bold number cell in the summary section
    summary_num_fmt = workbook.add_format({
        'font_size': 11, 'bold': True, 'border': 1, 'border_color': '#C3DAFE',
        'align': 'center', 'valign': 'vcenter',
        'bg_color': '#FFFFFF', 'font_color': '#4C51BF'
    })

    # ── COLUMN WIDTHS ────────────────────────────────────────────────────────
    # manually tuned widths for each of the 16 columns
    # ⚠️ if you ever add or remove a column you must update this list too
    col_widths = [7, 13, 15, 28, 38, 22, 13, 12, 9, 20, 25, 13, 13, 16, 12, 28]
    for i, w in enumerate(col_widths):
        worksheet.set_column(i, i, w)

    # ── ROW 1 — TITLE BAR ────────────────────────────────────────────────────
    worksheet.set_row(0, 30)  # set row height to 30
    # merge_range merges all 16 columns into one wide title cell
    worksheet.merge_range(0, 0, 0, len(col_widths) - 1,
                          '📋  דוח אירועים שבועי — מערכת מעקב ופיתוח', title_fmt)

    # ── ROW 2 — DATE INFO ────────────────────────────────────────────────────
    worksheet.set_row(1, 22)
    seven_days_ago = report_date - timedelta(days=7)
    date_str = report_date.strftime('%d/%m/%Y  %H:%M')
    range_str = (
        f'תקופת הדוח:  {seven_days_ago.strftime("%d/%m/%Y")}'
        f'  ←  {report_date.strftime("%d/%m/%Y")}'  # ← arrow shows the date range direction
    )
    worksheet.write(1, 0, 'תאריך הפקת הדוח:', date_label_fmt)
    worksheet.write(1, 1, date_str, date_value_fmt)
    worksheet.merge_range(1, 2, 1, 7, range_str, range_fmt)   # columns 2-7 show the date range
    worksheet.merge_range(1, 8, 1, len(col_widths) - 1,
                          f'סה"כ אירועים בדוח: {len(events)}', range_fmt)  # columns 8-15 show event count

    # ── ROW 3 — EMPTY SPACER ─────────────────────────────────────────────────
    worksheet.set_row(2, 6)  # thin spacer row between date info and column headers

    # ── ROW 4 — COLUMN HEADERS (row index 3) ─────────────────────────────────
    worksheet.set_row(3, 36)  # taller row for headers
    headers = [
        'מס"ד', 'תאריך רישום', 'מערכת', 'תמצית האירוע',
        'פירוט האירוע', 'לקוחות מושפעים', 'פנייה ראשונה',
        'דחיפות', 'עדיפות', 'סטטוס', 'פירוט סטטוס',
        'סיווג האירוע', 'לו"ז', 'גורם אחראי', 'הצעת מחיר', 'הערות נוספות'
    ]
    for col, hdr in enumerate(headers):
        worksheet.write(3, col, hdr, header_fmt)

    # adds dropdown filter arrows to every column header so users can filter in Excel
    worksheet.autofilter(3, 0, 3 + len(events), len(col_widths) - 1)

    # freezes top 4 rows + first column so they stay visible when scrolling
    worksheet.freeze_panes(4, 1)

    # ── DATA ROWS (start at row index 4) ─────────────────────────────────────
    today = datetime.now().date()

    for idx, event in enumerate(events):
        row = idx + 4   # data starts at row 4 (after title, date info, spacer, headers)
        alt = idx % 2 == 1  # True for odd rows — used for zebra stripe alternating background

        # determine row color based on event state
        is_completed = event.get('status') == 'הושלם הטיפול'
        is_overdue = False
        if event.get('status_deadline') and not is_completed:
            try:
                dl = datetime.strptime(event['status_deadline'], '%Y-%m-%d').date()
                is_overdue = dl < today  # deadline in the past = overdue
            except Exception:
                pass  # badly formatted date — skip without crashing the whole report

        # pick the right base format for this row
        if is_completed:
            base = completed_fmt      # green
        elif is_overdue:
            base = overdue_fmt        # red
        else:
            base = cell_alt_fmt if alt else cell_fmt  # alternating white/grey

        urgency = event.get('urgency', '')
        # critical urgency cells get their own bright red format regardless of row color
        urg_fmt = critical_fmt if urgency == 'קריטית' else base

        worksheet.set_row(row, 40)  # set data row height to 40

        # write each cell — num_base used for ID and priority (centered), base for everything else
        worksheet.write(row, 0,  event.get('id', ''),                        base)
        worksheet.write(row, 1,  event.get('registration_date', ''),         base)
        worksheet.write(row, 2,  event.get('system', ''),                    base)
        worksheet.write(row, 3,  event.get('event_summary', ''),             base)
        worksheet.write(row, 4,  event.get('event_details', ''),             base)
        worksheet.write(row, 5,  event.get('affected_customers', ''),        base)
        worksheet.write(row, 6,  event.get('first_contact_date', '') or '',  base)
        worksheet.write(row, 7,  urgency,                                    urg_fmt)  # special critical format
        worksheet.write(row, 8,  event.get('priority', ''),                  base)
        worksheet.write(row, 9,  event.get('status', ''),                    base)
        worksheet.write(row, 10, event.get('status_details', '') or '',      base)
        worksheet.write(row, 11, event.get('event_classification', '') or '', base)
        worksheet.write(row, 12, event.get('status_deadline', ''),           base)

        # clean up "Import" placeholder values left over from the Excel import process
        responsible = event.get('responsible_person', '') or ''
        if responsible.strip().lower() == 'import':
            responsible = ''
        worksheet.write(row, 13, responsible, base)

        # format price with ₪ symbol — skip if it's the "Import" placeholder
        price = event.get('price_quote')
        price_val = f"{price} ₪" if price and str(price).strip().lower() != 'import' else ''
        worksheet.write(row, 14, price_val, base)

        # clean up "Import" placeholder in notes too
        notes = event.get('additional_notes', '') or ''
        if notes.strip().lower() == 'import':
            notes = ''
        worksheet.write(row, 15, notes, base)


    # ── SUMMARY SECTION ───────────────────────────────────────────────────────
    # placed below the data rows with a small gap
    summary_start = len(events) + 6  # leaves a few empty rows between data and summary
    worksheet.set_row(summary_start - 1, 8)  # thin spacer row above summary
    worksheet.merge_range(summary_start, 0, summary_start, 3,
                          '📊  סיכום דוח', summary_header_fmt)
    worksheet.set_row(summary_start, 24)

    # calculate summary counts by looping through the events once
    status_counts = {}
    overdue_count = 0
    critical_count = 0
    completed_count = 0

    for e in events:
        s = e.get('status', 'לא ידוע')
        status_counts[s] = status_counts.get(s, 0) + 1  # count events per status
        if e.get('status') == 'הושלם הטיפול':
            completed_count += 1
        if e.get('urgency') == 'קריטית':
            critical_count += 1
        if e.get('status_deadline') and e.get('status') != 'הושלם הטיפול':
            try:
                dl = datetime.strptime(e['status_deadline'], '%Y-%m-%d').date()
                if dl < today:
                    overdue_count += 1
            except Exception:
                pass

    # left side of summary — four key numbers
    summary_data = [
        ('סה"כ אירועים בדוח',  len(events)),
        ('אירועים שהושלמו',     completed_count),
        ('אירועים קריטיים',     critical_count),
        ('אירועים באיחור',      overdue_count),
    ]

    for i, (label, val) in enumerate(summary_data):
        r = summary_start + 1 + i
        worksheet.set_row(r, 22)
        worksheet.write(r, 0, label, summary_cell_fmt)
        worksheet.write(r, 1, val,   summary_num_fmt)

    # right side of summary — breakdown of every status and its count
    status_row = summary_start + 1
    worksheet.write(status_row, 3, 'פילוח לפי סטטוס:', summary_header_fmt)
    for j, (status, count) in enumerate(status_counts.items()):
        r = status_row + j
        worksheet.set_row(r, 22)
        worksheet.write(r, 3, status, summary_cell_fmt)
        worksheet.write(r, 4, count,  summary_num_fmt)

    # ⚠️ must call workbook.close() before reading output — finalizes the file into the buffer
    workbook.close()
    output.seek(0)  # rewind buffer to start so the caller reads the full file from the beginning
    return output   # returns the BytesIO stream — caller sends it to browser or attaches to email


def get_weekly_report_data():
    """
    ⚠️ This function is never called anywhere in the codebase — it is dead code.
    It was likely used in an earlier version before the report logic moved into app.py.
    Safe to remove if you want to clean up.
    """
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM events
        WHERE status != 'הושלם הטיפול'
        ORDER BY priority ASC, urgency DESC, registration_date DESC
    ''')

    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events