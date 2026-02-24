import xlsxwriter
from io import BytesIO
from datetime import datetime, timedelta
from database import Database


def generate_excel_report(events, filename=None, report_date=None):
    """Generate Excel report - shows events active/created/updated in last 7 days"""

    if report_date is None:
        report_date = datetime.now()

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('אירועים')
    worksheet.right_to_left()

    # ── FORMATS ──────────────────────────────────────────────────────────────

    title_fmt = workbook.add_format({
        'bold': True, 'font_size': 13,
        'font_color': '#FFFFFF', 'bg_color': '#4C51BF',
        'align': 'right', 'valign': 'vcenter',
        'border': 0
    })

    date_label_fmt = workbook.add_format({
        'bold': True, 'font_size': 11,
        'font_color': '#4C51BF', 'bg_color': '#EBF4FF',
        'align': 'right', 'valign': 'vcenter',
        'border': 1, 'border_color': '#C3DAFE'
    })

    date_value_fmt = workbook.add_format({
        'font_size': 11, 'bold': True,
        'font_color': '#2D3748', 'bg_color': '#EBF4FF',
        'align': 'right', 'valign': 'vcenter',
        'border': 1, 'border_color': '#C3DAFE'
    })

    range_fmt = workbook.add_format({
        'font_size': 10, 'italic': True,
        'font_color': '#718096', 'bg_color': '#EBF4FF',
        'align': 'right', 'valign': 'vcenter',
        'border': 1, 'border_color': '#C3DAFE'
    })

    header_fmt = workbook.add_format({
        'bold': True, 'font_size': 11,
        'font_color': '#FFFFFF', 'bg_color': '#667EEA',
        'border': 1, 'border_color': '#5A67D8',
        'align': 'center', 'valign': 'vcenter',
        'text_wrap': True
    })

    cell_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E2E8F0',
        'align': 'right', 'valign': 'top', 'text_wrap': True,
        'bg_color': '#FFFFFF'
    })

    cell_alt_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E2E8F0',
        'align': 'right', 'valign': 'top', 'text_wrap': True,
        'bg_color': '#F7FAFC'
    })

    # ── BRIGHTER RED for overdue rows ─────────────────────────────────────────
    overdue_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#F56565',
        'align': 'right', 'valign': 'top', 'text_wrap': True,
        'bg_color': '#FED7D7'  # was #FFF5F5
    })

    # ── BRIGHTER RED + BOLD for critical urgency cells ────────────────────────
    critical_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E53E3E',
        'align': 'right', 'valign': 'top', 'text_wrap': True,
        'bg_color': '#FC8181', 'font_color': '#63171B', 'bold': True  # was #FED7D7 / #C53030
    })

    # ── BRIGHTER GREEN for completed rows ─────────────────────────────────────
    completed_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#48BB78',
        'align': 'right', 'valign': 'top', 'text_wrap': True,
        'bg_color': '#9AE6B4', 'font_color': '#1C4532'  # was #F0FFF4 / #276749
    })

    number_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E2E8F0',
        'align': 'center', 'valign': 'top',
        'bg_color': '#FFFFFF'
    })

    number_alt_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E2E8F0',
        'align': 'center', 'valign': 'top',
        'bg_color': '#F7FAFC'
    })

    summary_header_fmt = workbook.add_format({
        'bold': True, 'font_size': 11,
        'font_color': '#FFFFFF', 'bg_color': '#4C51BF',
        'border': 1, 'align': 'right', 'valign': 'vcenter'
    })

    summary_cell_fmt = workbook.add_format({
        'font_size': 10, 'border': 1, 'border_color': '#E2E8F0',
        'align': 'right', 'valign': 'vcenter',
        'bg_color': '#EBF4FF'
    })

    summary_num_fmt = workbook.add_format({
        'font_size': 11, 'bold': True, 'border': 1, 'border_color': '#C3DAFE',
        'align': 'center', 'valign': 'vcenter',
        'bg_color': '#FFFFFF', 'font_color': '#4C51BF'
    })

    # ── COLUMN WIDTHS ────────────────────────────────────────────────────────
    col_widths = [7, 13, 15, 28, 38, 22, 13, 12, 9, 20, 25, 13, 13, 16, 12, 28]
    for i, w in enumerate(col_widths):
        worksheet.set_column(i, i, w)

    # ── ROW 1 - TITLE BAR ────────────────────────────────────────────────────
    worksheet.set_row(0, 30)
    worksheet.merge_range(0, 0, 0, len(col_widths) - 1,
                          '📋  דוח אירועים שבועי — מערכת מעקב ופיתוח', title_fmt)

    # ── ROW 2 - DATE INFO ────────────────────────────────────────────────────
    worksheet.set_row(1, 22)
    seven_days_ago = report_date - timedelta(days=7)
    date_str = report_date.strftime('%d/%m/%Y  %H:%M')
    range_str = (
        f'תקופת הדוח:  {seven_days_ago.strftime("%d/%m/%Y")}'
        f'  ←  {report_date.strftime("%d/%m/%Y")}'
    )

    worksheet.write(1, 0, 'תאריך הפקת הדוח:', date_label_fmt)
    worksheet.write(1, 1, date_str, date_value_fmt)
    worksheet.merge_range(1, 2, 1, 7, range_str, range_fmt)
    worksheet.merge_range(1, 8, 1, len(col_widths) - 1,
                          f'סה"כ אירועים בדוח: {len(events)}', range_fmt)

    # ── ROW 3 - EMPTY SPACER ─────────────────────────────────────────────────
    worksheet.set_row(2, 6)

    # ── ROW 4 - COLUMN HEADERS (row index 3) ─────────────────────────────────
    worksheet.set_row(3, 36)
    headers = [
        'מס"ד', 'תאריך רישום', 'מערכת', 'תמצית האירוע',
        'פירוט האירוע', 'לקוחות מושפעים', 'פנייה ראשונה',
        'דחיפות', 'עדיפות', 'סטטוס', 'פירוט סטטוס',
        'סיווג האירוע', 'לו"ז', 'גורם אחראי', 'הצעת מחיר', 'הערות נוספות'
    ]
    for col, hdr in enumerate(headers):
        worksheet.write(3, col, hdr, header_fmt)

    # ── AUTOFILTER on header row ──────────────────────────────────────────────
    worksheet.autofilter(3, 0, 3 + len(events), len(col_widths) - 1)

    # ── FREEZE top 4 rows + first column ─────────────────────────────────────
    worksheet.freeze_panes(4, 1)

    # ── DATA ROWS (start at row index 4) ─────────────────────────────────────
    today = datetime.now().date()

    for idx, event in enumerate(events):
        row = idx + 4
        alt = idx % 2 == 1

        is_completed = event.get('status') == 'הושלם הטיפול'
        is_overdue = False
        if event.get('status_deadline') and not is_completed:
            try:
                dl = datetime.strptime(event['status_deadline'], '%Y-%m-%d').date()
                is_overdue = dl < today
            except Exception:
                pass

        if is_completed:
            base = completed_fmt
            num_base = completed_fmt
        elif is_overdue:
            base = overdue_fmt
            num_base = overdue_fmt
        else:
            base = cell_alt_fmt if alt else cell_fmt
            num_base = number_alt_fmt if alt else number_fmt

        urgency = event.get('urgency', '')
        urg_fmt = critical_fmt if urgency == 'קריטית' else base

        worksheet.set_row(row, 40)

        worksheet.write(row, 0,  event.get('id', ''),                        num_base)
        worksheet.write(row, 1,  event.get('registration_date', ''),         base)
        worksheet.write(row, 2,  event.get('system', ''),                    base)
        worksheet.write(row, 3,  event.get('event_summary', ''),             base)
        worksheet.write(row, 4,  event.get('event_details', ''),             base)
        worksheet.write(row, 5,  event.get('affected_customers', ''),        base)
        worksheet.write(row, 6,  event.get('first_contact_date', '') or '',  base)
        worksheet.write(row, 7,  urgency,                                    urg_fmt)
        worksheet.write(row, 8,  event.get('priority', ''),                  num_base)
        worksheet.write(row, 9,  event.get('status', ''),                    base)
        worksheet.write(row, 10, event.get('status_details', '') or '',      base)
        worksheet.write(row, 11, event.get('event_classification', '') or '', base)
        worksheet.write(row, 12, event.get('status_deadline', ''),           base)
        responsible = event.get('responsible_person', '') or ''
        if responsible.strip().lower() == 'import':
            responsible = ''
        worksheet.write(row, 13, responsible, base)
        price = event.get('price_quote')
        price_val = f"{price} ₪" if price and str(price).strip().lower() != 'import' else ''
        worksheet.write(row, 14, price_val,                                   base)
        notes = event.get('additional_notes', '') or ''
        if notes.strip().lower() == 'import':
            notes = ''
        worksheet.write(row, 15, notes,                                       base)


    # ── SUMMARY SECTION ───────────────────────────────────────────────────────
    summary_start = len(events) + 6
    worksheet.set_row(summary_start - 1, 8)  # spacer row
    worksheet.merge_range(summary_start, 0, summary_start, 3,
                          '📊  סיכום דוח', summary_header_fmt)
    worksheet.set_row(summary_start, 24)

    status_counts = {}
    overdue_count = 0
    critical_count = 0
    completed_count = 0

    for e in events:
        s = e.get('status', 'לא ידוע')
        status_counts[s] = status_counts.get(s, 0) + 1
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

    status_row = summary_start + 1
    worksheet.write(status_row, 3, 'פילוח לפי סטטוס:', summary_header_fmt)
    for j, (status, count) in enumerate(status_counts.items()):
        r = status_row + j
        worksheet.set_row(r, 22)
        worksheet.write(r, 3, status, summary_cell_fmt)
        worksheet.write(r, 4, count,  summary_num_fmt)

    workbook.close()
    output.seek(0)
    return output


def get_weekly_report_data():
    """Get all active events for weekly report"""
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