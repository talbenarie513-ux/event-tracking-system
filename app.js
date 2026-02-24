// Configuration
const API_URL = 'http://localhost:5000/api';
let currentUser = null;
let currentUserRole = null;
let allEvents = [];
let currentEventId = null;
let userPermissions = [];
let columnFilters = {};
let currentSort = '';
let analysisCharts = {};

const CLOSED_STATUSES = ['הושלם הטיפול', 'טופל חלקית', 'בהקפאה'];

// ============= CACHE BUSTING =============
function fetchNoCache(url, options = {}) {
    const timestamp = new Date().getTime();
    const separator = url.includes('?') ? '&' : '?';
    const nocacheUrl = `${url}${separator}_t=${timestamp}`;
    const headers = options.headers || {};
    headers['Cache-Control'] = 'no-cache, no-store, must-revalidate';
    headers['Pragma'] = 'no-cache';
    headers['Expires'] = '0';
    return fetch(nocacheUrl, { ...options, headers });
}

// ============= INIT =============
document.addEventListener('DOMContentLoaded', function() {
    loadUsers();
    setTodayDate();
    loadEventsReadOnly();

    document.getElementById('userSelect').addEventListener('change', handleUserLogin);
    document.getElementById('searchBox').addEventListener('input', filterEvents);
    document.getElementById('eventForm').addEventListener('submit', handleEventSubmit);
    document.getElementById('addUserForm').addEventListener('submit', handleAddUser);

    document.getElementById('status').addEventListener('change', function() {
        const completionDateGroup = document.getElementById('completionDateGroup');
        const completionDate = document.getElementById('completionDate');
        if (this.value === 'הושלם הטיפול') {
            completionDateGroup.style.display = 'block';
            if (!completionDate.value) completionDate.value = new Date().toISOString().split('T')[0];
        } else {
            completionDateGroup.style.display = 'none';
            completionDate.value = '';
        }
    });

    setupColumnFilters();

    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) closeAllModals();
        });
    });
});

function closeAllModals() {
    closeEventModal();
    closeDetailModal();
    closeAdminModal();
    closeAnalysisModal();
    closeHistoryModal();
    closeHelpModal();
    closeFilePreviewModal();
}

let myEventsActive = false;

function toggleMyEvents() {
    const btn = document.getElementById('myEventsBtn');
    myEventsActive = !myEventsActive;
    if (myEventsActive) {
        const myEvents = allEvents.filter(e =>
            e.responsible_person && e.responsible_person === currentUser
        );
        btn.textContent = '✖ כל האירועים';
        btn.style.background = '#e53e3e';
        displayEvents(myEvents);
    } else {
        btn.textContent = '📋 האירועים שלי';
        btn.style.background = '';
        displayEvents(allEvents);
    }
}

// ============= HELP MODAL =============
function showHelpModal() { document.getElementById('helpModal').classList.add('active'); }
function closeHelpModal() { document.getElementById('helpModal').classList.remove('active'); }

// ============= FILE PREVIEW MODAL =============

async function openFile(fileId) {
    try {
        const res = await fetchNoCache(`${API_URL}/files/${fileId}/view`);

        // Handle HTTP errors (4xx / 5xx)
        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: `שגיאת שרת ${res.status}` }));
            if (confirm(`שגיאה בפתיחת הקובץ:\n${err.error}\n\nהאם להוריד את הקובץ במקום?`)) {
                downloadFile(fileId);
            }
            return;
        }

        const data = await res.json();

        if (!data.previewable) {
            const reason = data.reason === 'doc_old'
                ? 'קבצי .doc ישנים אינם נתמכים לתצוגה מקדימה.\nניתן להמיר ל-.docx ולהעלות מחדש.'
                : 'סוג קובץ זה אינו נתמך לתצוגה מקדימה.';
            if (confirm(`${reason}\n\nהאם להוריד את הקובץ?`)) {
                downloadFile(fileId);
            }
            return;
        }

        const modal = document.getElementById('filePreviewModal');
        const title = document.getElementById('filePreviewTitle');
        const body  = document.getElementById('filePreviewBody');
        const dlBtn = document.getElementById('filePreviewDownloadBtn');

        title.textContent = data.filename;
        dlBtn.onclick = () => downloadFile(fileId);
        body.innerHTML = '';

        switch (data.preview_type) {
            case 'base64': {
                const src = `data:${data.mime_type};base64,${data.data}`;
                if (data.mime_type === 'application/pdf') {
                    body.innerHTML =
                        `<iframe src="${src}" style="width:100%;height:75vh;border:none;border-radius:8px;"></iframe>`;
                } else {
                    body.innerHTML =
                        `<img src="${src}" style="max-width:100%;max-height:75vh;display:block;`
                        + `margin:auto;border-radius:8px;object-fit:contain;">`;
                }
                break;
            }
            case 'text': {
                body.innerHTML =
                    `<pre style="white-space:pre-wrap;word-break:break-word;font-size:14px;`
                    + `line-height:1.6;padding:10px;background:#f7fafc;border-radius:8px;`
                    + `max-height:75vh;overflow-y:auto;direction:ltr;text-align:left;">`
                    + escapeHtml(data.content) + `</pre>`;
                break;
            }
            case 'html_table': {
                body.innerHTML =
                    `<div style="max-height:75vh;overflow:auto;border-radius:8px;">`
                    + data.html + `</div>`;
                break;
            }
            case 'html_doc': {
                body.innerHTML =
                    `<div style="max-height:75vh;overflow-y:auto;padding:20px;`
                    + `background:#fff;border-radius:8px;border:1px solid #e2e8f0;">`
                    + data.html + `</div>`;
                break;
            }
            default:
                body.innerHTML = `<p style="color:#999;text-align:center;">אין תצוגה מקדימה זמינה</p>`;
        }

        modal.classList.add('active');

    } catch (err) {
        console.error('Error opening file:', err);
        if (confirm(`שגיאה בפתיחת הקובץ: ${err.message}\n\nהאם להוריד את הקובץ במקום?`)) {
            downloadFile(fileId);
        }
    }
}

function escapeHtml(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function closeFilePreviewModal() {
    const modal = document.getElementById('filePreviewModal');
    modal.classList.remove('active');
    document.getElementById('filePreviewBody').innerHTML = '';
}

// ============= USER MANAGEMENT =============

async function loadUsers() {
    try {
        const response = await fetchNoCache(`${API_URL}/users`);
        const users = await response.json();
        const userSelect = document.getElementById('userSelect');
        userSelect.innerHTML = '<option value="">בחר משתמש...</option>';
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user.name;
            option.dataset.role = user.role;
            option.textContent = `${user.name} (${getRoleLabel(user.role)})`;
            userSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

async function handleUserLogin() {
    const userSelect = document.getElementById('userSelect');
    const selectedOption = userSelect.options[userSelect.selectedIndex];
    if (selectedOption.value) {
        currentUser = selectedOption.value;
        currentUserRole = selectedOption.dataset.role;
        if (currentUserRole === 'admin') {
            document.getElementById('adminBtn').classList.remove('hidden');
            document.getElementById('analysisBtn').classList.remove('hidden');
        } else {
            document.getElementById('adminBtn').classList.add('hidden');
            document.getElementById('analysisBtn').classList.add('hidden');
        }
        document.getElementById('myEventsBtn').classList.remove('hidden');
        await loadPermissions(currentUserRole);
        updateNewEventButton();
        loadEvents();
        loadStats();
    } else {
        currentUser = null;
        currentUserRole = null;
        userPermissions = [];
        document.getElementById('adminBtn').classList.add('hidden');
        document.getElementById('analysisBtn').classList.add('hidden');
        document.getElementById('newEventBtn').classList.add('hidden');
        document.getElementById('myEventsBtn').classList.add('hidden');
        loadEventsReadOnly();
    }
}

function updateNewEventButton() {
    const newEventBtn = document.getElementById('newEventBtn');
    if (currentUserRole === 'development') {
        newEventBtn.classList.add('hidden');
    } else if (currentUser) {
        newEventBtn.classList.remove('hidden');
    } else {
        newEventBtn.classList.add('hidden');
    }
}

async function loadPermissions(role) {
    try {
        const response = await fetchNoCache(`${API_URL}/permissions/${role}`);
        const data = await response.json();
        userPermissions = data.permissions;
    } catch (error) {
        console.error('Error loading permissions:', error);
    }
}

function getRoleLabel(role) {
    const roles = { 'admin': 'אדמין', 'planning': 'תכנון', 'development': 'פיתוח' };
    return roles[role] || role;
}

// ============= COLUMN FILTERS =============

function setupColumnFilters() {
    document.querySelectorAll('.column-filter').forEach(filter => {
        filter.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleColumnFilter(this.dataset.column, this);
        });
    });
    document.addEventListener('click', function() {
        document.querySelectorAll('.filter-dropdown').forEach(d => d.remove());
    });
}

function toggleColumnFilter(column, element) {
    document.querySelectorAll('.filter-dropdown').forEach(d => d.remove());
    const uniqueValues = [...new Set(allEvents.map(e => e[column]))].filter(v => v);
    if (uniqueValues.length === 0) return;

    const dropdown = document.createElement('div');
    dropdown.className = 'filter-dropdown';
    dropdown.style.position = 'fixed';

    const rect = element.getBoundingClientRect();
    dropdown.style.top = (rect.bottom + 5) + 'px';

    const dropdownWidth = 180;
    let leftPos = rect.left;
    if (leftPos + dropdownWidth > window.innerWidth - 5) leftPos = window.innerWidth - dropdownWidth - 5;
    if (leftPos < 5) leftPos = 5;
    dropdown.style.left = leftPos + 'px';

    const clearOption = document.createElement('label');
    clearOption.innerHTML = `<input type="checkbox" ${!columnFilters[column] ? 'checked' : ''} onchange="clearColumnFilter('${column}')"><strong>הצג הכל</strong>`;
    dropdown.appendChild(clearOption);

    uniqueValues.forEach(value => {
        const label = document.createElement('label');
        const isChecked = !columnFilters[column] || columnFilters[column].includes(value);
        label.innerHTML = `<input type="checkbox" ${isChecked ? 'checked' : ''} onchange="updateColumnFilter('${column}', '${value}', this.checked)">${value}`;
        dropdown.appendChild(label);
    });

    document.body.appendChild(dropdown);
    dropdown.addEventListener('click', e => e.stopPropagation());
}

function updateColumnFilter(column, value, checked) {
    if (!columnFilters[column]) columnFilters[column] = [];
    if (checked) {
        if (!columnFilters[column].includes(value)) columnFilters[column].push(value);
    } else {
        columnFilters[column] = columnFilters[column].filter(v => v !== value);
    }
    filterEvents();
}

function clearColumnFilter(column) {
    delete columnFilters[column];
    filterEvents();
    document.querySelectorAll('.filter-dropdown').forEach(d => d.remove());
}

function filterByStat(type) {
    const cards = document.querySelectorAll('.stat-card');
    const isActive = document.querySelector(`.stat-card.active-filter[data-stat="${type}"]`);
    cards.forEach(c => { c.classList.remove('active-filter'); c.removeAttribute('data-stat'); });
    if (isActive) { displayEvents(allEvents); return; }

    const idx = ['total', 'overdue', 'critical', 'inprogress'];
    cards[idx.indexOf(type)].classList.add('active-filter');
    cards[idx.indexOf(type)].setAttribute('data-stat', type);

    const today = new Date(); today.setHours(0, 0, 0, 0);
    let filtered;
    switch(type) {
        case 'total':
            filtered = allEvents.filter(e => e.status !== 'הושלם הטיפול' && e.status !== 'בהקפאה'); break;
        case 'overdue':
            filtered = allEvents.filter(e =>
                new Date(e.status_deadline) < today && !CLOSED_STATUSES.includes(e.status)); break;
        case 'critical':
            filtered = allEvents.filter(e => e.urgency === 'קריטית'); break;
        case 'inprogress':
            filtered = allEvents.filter(e => !['בהקפאה','הושלם הטיפול','טופל חלקית','אירוע חדש'].includes(e.status)); break;
        default:
            filtered = allEvents;
    }
    displayEvents(filtered);
}

function filterByStatus(status) {
    columnFilters = { status: [status] };
    filterEvents();
}

// ============= SEARCH AND FILTER =============

function filterEvents() {
    const searchTerm = document.getElementById('searchBox').value.toLowerCase();
    let filtered = allEvents.filter(event => {
        const matchesSearch = !searchTerm ||
            event.event_summary.toLowerCase().includes(searchTerm) ||
            event.system.toLowerCase().includes(searchTerm) ||
            event.event_details.toLowerCase().includes(searchTerm) ||
            event.affected_customers.toLowerCase().includes(searchTerm);
        let matchesFilters = true;
        for (const [column, values] of Object.entries(columnFilters)) {
            if (values.length > 0 && !values.includes(event[column])) { matchesFilters = false; break; }
        }
        return matchesSearch && matchesFilters;
    });
    displayEvents(filtered);
}

function sortEvents() {
    const sortValue = document.getElementById('sortSelect').value;
    if (!sortValue) { filterEvents(); return; }
    let sorted = [...allEvents];
    switch(sortValue) {
        case 'id_asc':        sorted.sort((a, b) => a.id - b.id); break;
        case 'id_desc':       sorted.sort((a, b) => b.id - a.id); break;
        case 'date_asc':      sorted.sort((a, b) => new Date(a.registration_date) - new Date(b.registration_date)); break;
        case 'date_desc':     sorted.sort((a, b) => new Date(b.registration_date) - new Date(a.registration_date)); break;
        case 'deadline_asc':  sorted.sort((a, b) => new Date(a.status_deadline) - new Date(b.status_deadline)); break;
        case 'deadline_desc': sorted.sort((a, b) => new Date(b.status_deadline) - new Date(a.status_deadline)); break;
        case 'priority_asc':  sorted.sort((a, b) => a.priority - b.priority); break;
        case 'priority_desc': sorted.sort((a, b) => b.priority - a.priority); break;
    }
    allEvents = sorted;
    filterEvents();
}

// ============= SHOW COMPLETED TOGGLE =============

let rawEvents = [];

function toggleCompleted() {
    if (document.getElementById('showDeleted').checked) return;
    applyCompletedFilter();
}

function applyCompletedFilter() {
    const showCompleted = document.getElementById('showCompleted').checked;
    columnFilters = {};
    if (showCompleted) {
        allEvents = rawEvents.filter(e => e.status === 'הושלם הטיפול');
    } else {
        allEvents = rawEvents.filter(e => e.status !== 'הושלם הטיפול' && e.status !== 'בהקפאה');
    }
    displayEvents(allEvents);
}

function showAllEvents() {
    document.getElementById('showCompleted').checked = false;
    document.getElementById('showDeleted').checked = false;
    document.getElementById('showCompleted').disabled = false;
    document.getElementById('deletedBanner').classList.remove('active');
    columnFilters = {};
    allEvents = rawEvents;
    displayEvents(allEvents);
}

// ============= DELETED EVENTS TOGGLE =============

function toggleDeleted() {
    const showDeleted = document.getElementById('showDeleted').checked;
    const showCompleted = document.getElementById('showCompleted');
    const banner = document.getElementById('deletedBanner');
    if (showDeleted) {
        showCompleted.disabled = true;
        banner.classList.add('active');
        loadDeletedEvents();
    } else {
        showCompleted.disabled = false;
        banner.classList.remove('active');
        loadEvents();
    }
}

async function loadDeletedEvents() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.classList.remove('hidden');
    try {
        const response = await fetchNoCache(`${API_URL}/events?show_deleted=true`);
        const allFetched = await response.json();
        const deleted = allFetched.filter(e => e.is_deleted === 1);
        displayDeletedEvents(deleted);
    } catch (error) {
        console.error('Error loading deleted events:', error);
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

function displayDeletedEvents(events) {
    const tbody = document.getElementById('eventsTableBody');
    tbody.innerHTML = '';
    if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; color:#999;">אין אירועים שנמחקו לאחרונה</td></tr>';
        return;
    }
    events.forEach(event => {
        const row = document.createElement('tr');
        row.style.opacity = '0.6';
        row.style.background = '#f9f9f9';

        let urgencyClass = 'urgency-low';
        if (event.urgency === 'קריטית') urgencyClass = 'urgency-critical';
        else if (event.urgency === 'גבוהה') urgencyClass = 'urgency-high';
        else if (event.urgency === 'בינונית') urgencyClass = 'urgency-medium';

        row.innerHTML = `
            <td>${event.id}</td>
            <td>${formatDate(event.registration_date)}</td>
            <td>${event.system}</td>
            <td class="col-summary">${event.event_summary}</td>
            <td>${event.affected_customers}</td>
            <td><span class="urgency-badge ${urgencyClass}">${event.urgency}</span></td>
            <td>${event.priority}</td>
            <td><span style="color:#999;">${event.status} 🗑️</span></td>
            <td>${formatDate(event.status_deadline)}</td>
            <td>${event.responsible_person || '-'}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-restore" onclick="restoreEvent(${event.id})">♻️ שחזר</button>
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });
}

async function restoreEvent(eventId) {
    if (!confirm('האם לשחזר אירוע זה?')) return;
    try {
        const response = await fetch(`${API_URL}/events/${eventId}/restore`, { method: 'PUT' });
        const result = await response.json();
        if (result.success) {
            alert('האירוע שוחזר בהצלחה');
            loadDeletedEvents();
            loadStats();
        } else {
            alert('שגיאה: ' + result.error);
        }
    } catch (error) {
        alert('שגיאה בשחזור האירוע');
    }
}

// ============= EVENTS MANAGEMENT =============

async function loadEventsReadOnly() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.classList.remove('hidden');
    try {
        const response = await fetchNoCache(`${API_URL}/events`);
        rawEvents = await response.json();
        allEvents = rawEvents.filter(e => e.status !== 'הושלם הטיפול');
        displayEvents(allEvents);
        const statsResponse = await fetchNoCache(`${API_URL}/stats`);
        const stats = await statsResponse.json();
        document.getElementById('totalEvents').textContent = stats.total_events || 0;
        document.getElementById('overdueEvents').textContent = stats.overdue || 0;
        document.getElementById('criticalEvents').textContent = stats.critical || 0;
        document.getElementById('inProgressEvents').textContent = Object.entries(stats.by_status)
            .filter(([s]) => !['בהקפאה','הושלם הטיפול','טופל חלקית','אירוע חדש'].includes(s))
            .reduce((a,[,v]) => a+v, 0);
    } catch (error) {
        console.error('Error loading events:', error);
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

async function loadEvents() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.classList.remove('hidden');
    try {
        const response = await fetchNoCache(`${API_URL}/events`);
        rawEvents = await response.json();
        applyCompletedFilter();
    } catch (error) {
        console.error('Error loading events:', error);
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

function displayEvents(events) {
    const tbody = document.getElementById('eventsTableBody');
    tbody.innerHTML = '';
    if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align: center;">אין אירועים להצגה</td></tr>';
        return;
    }
    events.forEach(event => {
        const row = document.createElement('tr');
        row.onclick = () => showEventDetail(event.id);

        let urgencyClass = 'urgency-low';
        if (event.urgency === 'קריטית') urgencyClass = 'urgency-critical';
        else if (event.urgency === 'גבוהה') urgencyClass = 'urgency-high';
        else if (event.urgency === 'בינונית') urgencyClass = 'urgency-medium';

        const today = new Date(); today.setHours(0,0,0,0);
        const isOverdue = new Date(event.status_deadline) < today && !CLOSED_STATUSES.includes(event.status);
        if (isOverdue) row.classList.add('row-overdue');

        row.innerHTML = `
            <td>${event.id}</td>
            <td>${formatDate(event.registration_date)}</td>
            <td>${event.system}</td>
            <td class="col-summary">${event.event_summary}</td>
            <td>${event.affected_customers}</td>
            <td><span class="urgency-badge ${urgencyClass}">${event.urgency}</span></td>
            <td>${event.priority}</td>
            <td>${event.status}</td>
            <td>${formatDate(event.status_deadline)}</td>
            <td>${event.responsible_person || '-'}</td>
            <td>
                <div class="action-buttons">
                    ${currentUser ? `
                    <button class="btn btn-primary btn-small" onclick="event.stopPropagation(); editEvent(${event.id})">✏️</button>
                    ${currentUserRole !== 'development' ? `
                    <button class="btn btn-danger btn-small" onclick="event.stopPropagation(); deleteEvent(${event.id})">🗑️</button>
                    ` : ''}
                    ` : ''}
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });
}

async function showEventDetail(eventId) {
    try {
        const response = await fetchNoCache(`${API_URL}/events/${eventId}`);
        const event = await response.json();
        currentEventId = eventId;
        document.getElementById('detailEventId').textContent = event.id;

        let filesHtml = '';
        if (event.files && event.files.length > 0) {
            const fileRows = event.files.map(file => `
                <div class="file-item">
                    <span>📄 ${file.original_filename}</span>
                    <div style="display:flex;gap:6px;">
                        <button class="btn btn-primary btn-small" onclick="openFile(${file.id})">👁️ פתח</button>
                        <button class="btn btn-primary btn-small" onclick="downloadFile(${file.id}, '${file.original_filename.replace(/'/g,"\\'")}')">⬇️ הורד</button>
                    </div>
                </div>
            `).join('');
            filesHtml = `
            <div class="detail-section">
                <h3>📎 קבצים מצורפים (${event.files.length})</h3>
                ${fileRows}
            </div>`;
        }

        const detailContent = document.getElementById('detailContent');
        detailContent.innerHTML = `
            <div class="detail-section">
                <h3>פרטים בסיסיים</h3>
                <div class="detail-row"><div class="detail-label">תאריך רישום:</div><div class="detail-value">${formatDate(event.registration_date)}</div></div>
                <div class="detail-row"><div class="detail-label">תאריך פנייה ראשונה:</div><div class="detail-value">${event.first_contact_date ? formatDate(event.first_contact_date) : '-'}</div></div>
                <div class="detail-row"><div class="detail-label">מערכת:</div><div class="detail-value">${event.system}</div></div>
                <div class="detail-row"><div class="detail-label">לקוחות מושפעים:</div><div class="detail-value">${event.affected_customers}</div></div>
            </div>
            <div class="detail-section">
                <h3>תיאור האירוע</h3>
                <div class="detail-row"><div class="detail-label">תמצית:</div><div class="detail-value">${event.event_summary}</div></div>
                <div class="detail-row"><div class="detail-label">פירוט:</div><div class="detail-value">${event.event_details}</div></div>
            </div>
            <div class="detail-section">
                <h3>סטטוס וטיפול</h3>
                <div class="detail-row"><div class="detail-label">דחיפות:</div><div class="detail-value"><span class="urgency-badge ${
                    event.urgency === 'קריטית' ? 'urgency-critical' :
                    event.urgency === 'גבוהה'  ? 'urgency-high' :
                    event.urgency === 'בינונית' ? 'urgency-medium' : 'urgency-low'
                }">${event.urgency}</span></div></div>
                <div class="detail-row"><div class="detail-label">עדיפות:</div><div class="detail-value">${event.priority}</div></div>
                <div class="detail-row"><div class="detail-label">סטטוס:</div><div class="detail-value">${event.status}</div></div>
                <div class="detail-row"><div class="detail-label">פירוט סטטוס:</div><div class="detail-value">${event.status_details || '-'}</div></div>
                <div class="detail-row"><div class="detail-label">סיווג:</div><div class="detail-value">${event.event_classification || '-'}</div></div>
                <div class="detail-row"><div class="detail-label">לו"ז:</div><div class="detail-value">${formatDate(event.status_deadline)}</div></div>
                ${event.completion_date ? `<div class="detail-row"><div class="detail-label">תאריך השלמה:</div><div class="detail-value">${formatDate(event.completion_date)}</div></div>` : ''}
                <div class="detail-row"><div class="detail-label">גורם אחראי:</div><div class="detail-value">${event.responsible_person || '-'}</div></div>
            </div>
            <div class="detail-section">
                <h3>מידע נוסף</h3>
                <div class="detail-row"><div class="detail-label">הצעת מחיר:</div><div class="detail-value">${event.price_quote ? event.price_quote + ' ₪' : '-'}</div></div>
                <div class="detail-row"><div class="detail-label">הערות:</div><div class="detail-value">${event.additional_notes || '-'}</div></div>
                <div class="detail-row"><div class="detail-label">נוצר על ידי:</div><div class="detail-value">${event.created_by}</div></div>
                <div class="detail-row"><div class="detail-label">תאריך יצירה:</div><div class="detail-value">${formatDateTime(event.created_at)}</div></div>
                <div class="detail-row"><div class="detail-label">עודכן לאחרונה:</div><div class="detail-value">${formatDateTime(event.updated_at)}</div></div>
            </div>
            ${filesHtml}
        `;

        const canEdit = currentUser && currentUserRole !== 'development';
        document.getElementById('detailEditBtn').classList.toggle('hidden', !canEdit);
        document.getElementById('detailDeleteBtn').classList.toggle('hidden', !canEdit);
        document.getElementById('detailModal').classList.add('active');
    } catch (error) {
        console.error('Error loading event details:', error);
        alert('שגיאה בטעינת פרטי האירוע');
    }
}

function closeDetailModal() {
    document.getElementById('detailModal').classList.remove('active');
    currentEventId = null;
}

function handleDetailEdit() {
    const id = currentEventId;
    closeDetailModal();
    if (id) editEvent(id);
}

function handleDetailDelete() {
    const id = currentEventId;
    if (id) { closeDetailModal(); deleteEvent(id); }
}

// ============= HISTORY MODAL =============

async function showHistoryModal() {
    const eventId = currentEventId;
    if (!eventId) return;

    const modal = document.getElementById('historyModal');
    const content = document.getElementById('historyContent');
    content.innerHTML = '<div style="text-align:center;padding:30px;color:#667eea;">⏳ טוען היסטוריה...</div>';
    modal.classList.add('active');

    try {
        const response = await fetchNoCache(`${API_URL}/events/${eventId}/history`);
        const data = await response.json();

        const actionLabels = {
            'created':  { icon: '🟢', text: 'אירוע נוצר' },
            'updated':  { icon: '✏️',  text: 'עדכון שדה'  },
            'deleted':  { icon: '🗑️', text: 'אירוע נמחק' },
            'restored': { icon: '♻️', text: 'אירוע שוחזר'},
        };

        let html = `
        <div class="history-item history-created">
            <div class="history-icon">🟢</div>
            <div class="history-body">
                <div class="history-action">אירוע נוצר</div>
                <div class="history-meta">
                    <span class="history-user">👤 ${data.created_by || '—'}</span>
                    <span class="history-date">🕐 ${formatDateTime(data.created_at)}</span>
                </div>
            </div>
        </div>`;

        if (data.entries.length === 0) {
            html += `<div style="text-align:center;padding:20px;color:#999;">אין שינויים נוספים מאז יצירת האירוע</div>`;
        } else {
            const groups = [];
            for (const entry of data.entries) {
                if (entry.action === 'created') continue;
                const last = groups[groups.length - 1];
                if (last && last.action === 'updated' && entry.action === 'updated' &&
                    last.changed_by === entry.changed_by && last.changed_at === entry.changed_at) {
                    last.fields.push(entry);
                } else {
                    groups.push({
                        action: entry.action,
                        changed_by: entry.changed_by,
                        changed_at: entry.changed_at,
                        fields: [entry],
                    });
                }
            }
            for (const grp of groups) {
                const lbl = actionLabels[grp.action] || { icon: '🔵', text: grp.action };
                if (grp.action === 'updated') {
                    const fieldsHtml = grp.fields.map(f => `
                        <div class="history-field-row">
                            <span class="history-field-name">${f.field_label || f.field_name}</span>
                            <span class="history-arrow">←</span>
                            <span class="history-old">${f.old_value || '—'}</span>
                            <span class="history-arrow">→</span>
                            <span class="history-new">${f.new_value || '—'}</span>
                        </div>`).join('');
                    html += `
                    <div class="history-item history-updated">
                        <div class="history-icon">${lbl.icon}</div>
                        <div class="history-body">
                            <div class="history-action">${lbl.text}</div>
                            <div class="history-fields">${fieldsHtml}</div>
                            <div class="history-meta">
                                <span class="history-user">👤 ${grp.changed_by || '—'}</span>
                                <span class="history-date">🕐 ${formatDateTime(grp.changed_at)}</span>
                            </div>
                        </div>
                    </div>`;
                } else {
                    html += `
                    <div class="history-item history-${grp.action}">
                        <div class="history-icon">${lbl.icon}</div>
                        <div class="history-body">
                            <div class="history-action">${lbl.text}</div>
                            <div class="history-meta">
                                <span class="history-user">👤 ${grp.changed_by || '—'}</span>
                                <span class="history-date">🕐 ${formatDateTime(grp.changed_at)}</span>
                            </div>
                        </div>
                    </div>`;
                }
            }
        }
        content.innerHTML = html;
    } catch (error) {
        content.innerHTML = '<div style="text-align:center;padding:30px;color:#f56565;">שגיאה בטעינת ההיסטוריה</div>';
        console.error('Error loading history:', error);
    }
}

function closeHistoryModal() {
    document.getElementById('historyModal').classList.remove('active');
}

// ============= STATS =============

async function loadStats() {
    try {
        const response = await fetchNoCache(`${API_URL}/stats`);
        const stats = await response.json();
        document.getElementById('totalEvents').textContent = stats.total_events || 0;
        document.getElementById('overdueEvents').textContent = stats.overdue || 0;
        document.getElementById('criticalEvents').textContent = stats.critical || 0;
        document.getElementById('inProgressEvents').textContent = Object.entries(stats.by_status)
            .filter(([s]) => !['בהקפאה','הושלם הטיפול','טופל חלקית','אירוע חדש'].includes(s))
            .reduce((a,[,v]) => a+v, 0);
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ============= EVENT FORM =============

function showNewEventForm() {
    if (!currentUser) { alert('יש לבחור משתמש תחילה'); return; }
    if (currentUserRole === 'development') { alert('משתמשי פיתוח אינם יכולים ליצור אירועים חדשים'); return; }

    document.getElementById('modalTitle').textContent = 'אירוע חדש';
    document.getElementById('eventForm').reset();
    document.getElementById('eventId').value = '';
    document.getElementById('eventIdInput').value = '';
    document.getElementById('filesList').innerHTML = '';
    document.getElementById('fileNameDisplay').textContent = 'לא נבחרו קבצים';
    setTodayDate();
    setDefaultDeadline();
    document.getElementById('completionDateGroup').style.display = 'none';
    document.getElementById('completionDate').value = '';
    document.getElementById('systemOtherGroup').classList.add('hidden');
    document.getElementById('systemOther').required = false;
    document.getElementById('systemOther').value = '';
    document.getElementById('responsiblePersonOther').classList.add('hidden');
    document.getElementById('responsiblePersonOther').value = '';
    populateResponsibleDropdown('');
    enableAllFormFields();
    applyFieldRestrictions();
    document.getElementById('eventModal').classList.add('active');
}

async function editEvent(eventId) {
    if (!currentUser) { alert('יש לבחור משתמש תחילה'); return; }
    try {
        const response = await fetchNoCache(`${API_URL}/events/${eventId}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const event = await response.json();

        document.getElementById('modalTitle').textContent = `עריכת אירוע #${event.id}`;
        document.getElementById('eventId').value = event.id;
        document.getElementById('eventIdInput').value = event.id;
        document.getElementById('registrationDate').value = event.registration_date;
        document.getElementById('firstContactDate').value = event.first_contact_date || '';

        const systemSelect = document.getElementById('system');
        const systems = event.system.split(',').map(s => s.trim());
        const standardOptions = ['ספיר', 'שמיר', 'גאודאטה', 'אחר'];
        Array.from(systemSelect.options).forEach(opt => { opt.selected = systems.includes(opt.value); });
        const nonStandard = systems.filter(s => !standardOptions.includes(s));
        if (nonStandard.length > 0) {
            Array.from(systemSelect.options).forEach(opt => { if (opt.value === 'אחר') opt.selected = true; });
            document.getElementById('systemOtherGroup').classList.remove('hidden');
            document.getElementById('systemOther').value = nonStandard.join(', ');
            document.getElementById('systemOther').required = true;
        } else if (systems.includes('אחר')) {
            document.getElementById('systemOtherGroup').classList.remove('hidden');
            document.getElementById('systemOther').required = true;
        } else {
            document.getElementById('systemOtherGroup').classList.add('hidden');
            document.getElementById('systemOther').required = false;
            document.getElementById('systemOther').value = '';
        }

        document.getElementById('eventSummary').value = event.event_summary;
        document.getElementById('eventDetails').value = event.event_details;
        document.getElementById('affectedCustomers').value = event.affected_customers;
        document.getElementById('urgency').value = event.urgency;
        document.getElementById('priority').value = event.priority;
        document.getElementById('status').value = event.status;
        document.getElementById('statusDetails').value = event.status_details || '';
        document.getElementById('eventClassification').value = event.event_classification || '';
        document.getElementById('statusDeadline').value = event.status_deadline;
        document.getElementById('completionDate').value = event.completion_date || '';
        document.getElementById('priceQuote').value = event.price_quote || '';
        document.getElementById('additionalNotes').value = event.additional_notes || '';
        document.getElementById('fileNameDisplay').textContent = 'לא נבחרו קבצים';

        document.getElementById('completionDateGroup').style.display =
            event.status === 'הושלם הטיפול' ? 'block' : 'none';

        populateResponsibleDropdown(event.responsible_person || '', () => {
            enableAllFormFields();
            applyFieldRestrictions();
        });
        displayEventFiles(event.files || []);
        document.getElementById('eventModal').classList.add('active');
    } catch (error) {
        console.error('Error loading event:', error);
        alert('שגיאה בטעינת האירוע: ' + error.message);
    }
}

function enableAllFormFields() {
    document.querySelectorAll('#eventForm input, #eventForm select, #eventForm textarea')
        .forEach(input => { input.disabled = false; });
}

// ============= FIELD RESTRICTIONS =============

function applyFieldRestrictions() {
    if (currentUserRole === 'admin') {
        document.querySelectorAll('#eventForm input, #eventForm select, #eventForm textarea')
            .forEach(input => { input.required = false; input.disabled = false; });
        return;
    }
    if (currentUserRole === 'development') {
        document.querySelectorAll('#eventForm input, #eventForm select, #eventForm textarea')
            .forEach(input => {
                const allowedFields = ['status','statusDetails','completionDate','responsiblePerson','responsiblePersonOther','statusDeadline','priceQuote','additionalNotes','eventClassification'];
                if (!allowedFields.includes(input.id)) input.disabled = true;
            });
    }
    if (currentUserRole === 'planning') {
        const blockedFields = ['responsiblePerson','responsiblePersonOther','status','statusDetails','completionDate','priceQuote'];
        document.querySelectorAll('#eventForm input, #eventForm select, #eventForm textarea')
            .forEach(input => { if (blockedFields.includes(input.id)) input.disabled = true; });
    }
}

function setTodayDate() {
    document.getElementById('registrationDate').value = new Date().toISOString().split('T')[0];
}

function setDefaultDeadline() {
    const d = new Date();
    d.setDate(d.getDate() + 3);
    document.getElementById('statusDeadline').value = d.toISOString().split('T')[0];
}

function updateFileNameDisplay() {
    const input = document.getElementById('fileInput');
    const display = document.getElementById('fileNameDisplay');
    if (input.files.length === 0) {
        display.textContent = 'לא נבחרו קבצים';
    } else if (input.files.length === 1) {
        display.textContent = input.files[0].name;
    } else {
        display.textContent = `${input.files.length} קבצים נבחרו`;
    }
}

// ============= RESPONSIBLE PERSON DROPDOWN =============

function toggleResponsibleOther() {
    const select = document.getElementById('responsiblePerson');
    const otherInput = document.getElementById('responsiblePersonOther');
    if (select.value === 'אחר') {
        otherInput.classList.remove('hidden');
        otherInput.focus();
    } else {
        otherInput.classList.add('hidden');
        otherInput.value = '';
    }
}

function populateResponsibleDropdown(selectedValue, callback) {
    fetchNoCache(`${API_URL}/users`).then(r => r.json()).then(users => {
        const select = document.getElementById('responsiblePerson');
        select.innerHTML = '<option value="">-- בחר גורם אחראי --</option>';
        users.forEach(u => {
            const opt = document.createElement('option');
            opt.value = u.name;
            opt.textContent = u.name;
            select.appendChild(opt);
        });
        const otherOpt = document.createElement('option');
        otherOpt.value = 'אחר';
        otherOpt.textContent = 'אחר (הקלדה ידנית)';
        select.appendChild(otherOpt);

        if (selectedValue) {
            const match = Array.from(select.options).find(o => o.value === selectedValue);
            if (match) {
                select.value = selectedValue;
            } else {
                select.value = 'אחר';
                const otherInput = document.getElementById('responsiblePersonOther');
                otherInput.classList.remove('hidden');
                otherInput.value = selectedValue;
            }
        }
        if (callback) callback();
    });
}

function toggleSystemOtherInput() {
    const systemSelect = document.getElementById('system');
    const otherGroup   = document.getElementById('systemOtherGroup');
    const otherInput   = document.getElementById('systemOther');
    const selected     = Array.from(systemSelect.selectedOptions).map(o => o.value);
    if (selected.includes('אחר')) {
        otherGroup.classList.remove('hidden');
        otherInput.required = true;
    } else {
        otherGroup.classList.add('hidden');
        otherInput.required = false;
        otherInput.value    = '';
    }
}

// ============= HANDLE SUBMIT =============

async function handleEventSubmit(e) {
    e.preventDefault();
    const eventId = document.getElementById('eventId').value;
    const isEdit = eventId !== '';

    const systemSelect = document.getElementById('system');
    const selectedSystems = Array.from(systemSelect.selectedOptions).map(o => o.value);
    const systemOtherValue = document.getElementById('systemOther').value.trim();
    const finalSystems = selectedSystems.map(s => (s === 'אחר' && systemOtherValue) ? systemOtherValue : s);
    const systemValue = finalSystems.join(', ');

    const responsibleSelect = document.getElementById('responsiblePerson');
    const responsibleOther = document.getElementById('responsiblePersonOther').value.trim();
    const responsibleValue = responsibleSelect.options[responsibleSelect.selectedIndex]?.value || responsibleSelect.value;
    const responsible = responsibleValue === 'אחר' ? responsibleOther : responsibleValue;

    const customEventId = document.getElementById('eventIdInput').value;

    const eventData = {
        registration_date:    document.getElementById('registrationDate').value,
        first_contact_date:   document.getElementById('firstContactDate').value,
        system:               systemValue,
        event_summary:        document.getElementById('eventSummary').value,
        event_details:        document.getElementById('eventDetails').value,
        affected_customers:   document.getElementById('affectedCustomers').value,
        urgency:              document.getElementById('urgency').value,
        priority:             parseInt(document.getElementById('priority').value),
        status:               document.getElementById('status').value,
        status_details:       document.getElementById('statusDetails').value,
        event_classification: document.getElementById('eventClassification').value,
        status_deadline:      document.getElementById('statusDeadline').value,
        completion_date:      document.getElementById('completionDate').value || null,
        responsible_person:   responsible,
        price_quote:          parseFloat(document.getElementById('priceQuote').value) || null,
        additional_notes:     document.getElementById('additionalNotes').value,
        created_by:           currentUser,
        updated_by:           currentUser,
        user_role:            currentUserRole
    };

    if (!isEdit && customEventId) eventData.event_id = customEventId;
    if (isEdit) eventData.event_id = parseInt(eventId);

    try {
        const url    = isEdit ? `${API_URL}/events/${eventId}` : `${API_URL}/events`;
        const method = isEdit ? 'PUT' : 'POST';
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(eventData)
        });
        const result = await response.json();
        if (result.success) {
            alert(result.message);
            closeEventModal();
            loadEvents();
            loadStats();
        } else {
            alert('שגיאה: ' + result.error);
        }
    } catch (error) {
        console.error('Error saving event:', error);
        alert('שגיאה בשמירת האירוע');
    }
}

async function deleteEvent(eventId) {
    if (!confirm('האם אתה בטוח שברצונך למחוק אירוע זה?')) return;
    try {
        const response = await fetch(`${API_URL}/events/${eventId}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) { alert(result.message); loadEvents(); loadStats(); }
        else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה במחיקת האירוע');
    }
}

function closeEventModal() {
    document.getElementById('eventModal').classList.remove('active');
}

// ============= FILE MANAGEMENT =============

async function uploadFiles() {
    const eventId = document.getElementById('eventId').value;
    if (!eventId) { alert('יש לשמור את האירוע תחילה לפני העלאת קבצים'); return; }
    const fileInput = document.getElementById('fileInput');
    if (fileInput.files.length === 0) { alert('לא נבחרו קבצים'); return; }

    for (let i = 0; i < fileInput.files.length; i++) {
        const formData = new FormData();
        formData.append('file', fileInput.files[i]);
        formData.append('uploaded_by', currentUser);
        try {
            const response = await fetch(`${API_URL}/events/${eventId}/files`, { method: 'POST', body: formData });
            const result = await response.json();
            if (!result.success) alert(`שגיאה בהעלאת ${fileInput.files[i].name}: ${result.error}`);
        } catch (error) {
            alert(`שגיאה בהעלאת ${fileInput.files[i].name}`);
        }
    }
    const response = await fetchNoCache(`${API_URL}/events/${eventId}`);
    const event = await response.json();
    displayEventFiles(event.files || []);
    fileInput.value = '';
    document.getElementById('fileNameDisplay').textContent = 'לא נבחרו קבצים';
    alert('הקבצים הועלו בהצלחה');
}

function displayEventFiles(files) {
    const filesList = document.getElementById('filesList');
    filesList.innerHTML = '';
    if (files.length === 0) {
        filesList.innerHTML = '<p style="color:#666;margin-top:8px;">אין קבצים מצורפים</p>';
        return;
    }
    files.forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <span>📄 ${file.original_filename}</span>
            <div style="display:flex;gap:5px;">
                <button type="button" class="btn btn-primary btn-small" onclick="openFile(${file.id})">👁️ פתח</button>
                <button type="button" class="btn btn-primary btn-small" onclick="downloadFile(${file.id}, '${file.original_filename.replace(/'/g,"\\'")}')">⬇️ הורד</button>
                <button type="button" class="btn btn-danger btn-small" onclick="deleteFile(${file.id})">🗑️</button>
            </div>
        `;
        filesList.appendChild(fileItem);
    });
}

// ── Download: fetch as blob then save via hidden <a> tag ──────────────────────
async function downloadFile(fileId, filename) {
    try {
        const response = await fetch(`${API_URL}/files/${fileId}/download`);
        if (!response.ok) throw new Error('שגיאת שרת: ' + response.status);
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = filename || 'download';
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(blobUrl); }, 500);
    } catch (err) {
        console.error('Download error:', err);
        alert('שגיאה בהורדת הקובץ: ' + err.message);
    }
}

async function deleteFile(fileId) {
    if (!confirm('האם אתה בטוח שברצונך למחוק קובץ זה?')) return;
    try {
        const response = await fetch(`${API_URL}/files/${fileId}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) {
            const eventId = document.getElementById('eventId').value;
            const eventResponse = await fetchNoCache(`${API_URL}/events/${eventId}`);
            const event = await eventResponse.json();
            displayEventFiles(event.files || []);
        } else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה במחיקת הקובץ');
    }
}

// ============= ADMIN PANEL =============

function showAdminPanel() {
    if (currentUserRole !== 'admin') { alert('אין לך הרשאה לפעולה זו'); return; }
    loadUsersList();
    loadEmailList();
    document.getElementById('adminModal').classList.add('active');
}

function closeAdminModal() { document.getElementById('adminModal').classList.remove('active'); }

async function loadUsersList() {
    try {
        const response = await fetchNoCache(`${API_URL}/users`);
        const users = await response.json();
        const usersList = document.getElementById('usersList');
        usersList.innerHTML = '';
        users.forEach(user => {
            const wrapper = document.createElement('div');
            wrapper.innerHTML = `
                <div class="user-item">
                    <div>
                        <strong>${user.name}</strong> - ${getRoleLabel(user.role)}
                        ${user.email ? `<br><small>${user.email}</small>` : ''}
                    </div>
                    <div class="action-buttons">
                        <button class="btn btn-primary btn-small" onclick="toggleEditUser(${user.id})">✏️ עריכה</button>
                        <button class="btn btn-danger btn-small" onclick="deleteUser(${user.id}, '${user.name}')">🗑️ מחק</button>
                    </div>
                </div>
                <div class="edit-user-form" id="editForm_${user.id}">
                    <div class="form-grid">
                        <div class="form-group">
                            <label>שם</label>
                            <input type="text" id="editName_${user.id}" value="${user.name}">
                        </div>
                        <div class="form-group">
                            <label>תפקיד</label>
                            <select id="editRole_${user.id}">
                                <option value="admin"       ${user.role === 'admin'       ? 'selected' : ''}>אדמין</option>
                                <option value="planning"    ${user.role === 'planning'    ? 'selected' : ''}>תכנון</option>
                                <option value="development" ${user.role === 'development' ? 'selected' : ''}>פיתוח</option>
                            </select>
                        </div>
                        <div class="form-group full-width">
                            <label>אימייל</label>
                            <input type="email" id="editEmail_${user.id}" value="${user.email || ''}">
                        </div>
                    </div>
                    <div class="form-actions" style="margin-top:10px;">
                        <button class="btn btn-small" onclick="toggleEditUser(${user.id})">ביטול</button>
                        <button class="btn btn-success btn-small" onclick="saveUser(${user.id})">💾 שמור</button>
                    </div>
                </div>
            `;
            usersList.appendChild(wrapper);
        });
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

function toggleEditUser(userId) {
    document.getElementById(`editForm_${userId}`).classList.toggle('open');
}

async function saveUser(userId) {
    const name  = document.getElementById(`editName_${userId}`).value.trim();
    const role  = document.getElementById(`editRole_${userId}`).value;
    const email = document.getElementById(`editEmail_${userId}`).value.trim();
    if (!name || !email) { alert('שם ואימייל הם שדות חובה'); return; }
    try {
        const response = await fetch(`${API_URL}/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, role, email })
        });
        const result = await response.json();
        if (result.success) { loadUsersList(); loadUsers(); }
        else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה בשמירת המשתמש');
    }
}

async function handleAddUser(e) {
    e.preventDefault();
    const userData = {
        name: document.getElementById('newUserName').value,
        role: document.getElementById('newUserRole').value,
        email: document.getElementById('newUserEmail').value
    };
    try {
        const response = await fetch(`${API_URL}/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        const result = await response.json();
        if (result.success) {
            alert(result.message);
            document.getElementById('addUserForm').reset();
            loadUsersList();
            loadEmailList();
            loadUsers();
        } else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה בהוספת משתמש');
    }
}

async function deleteUser(userId, userName) {
    if (!confirm(`האם אתה בטוח שברצונך למחוק את ${userName}?`)) return;
    try {
        const response = await fetch(`${API_URL}/users/${userId}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) { alert(result.message); loadUsersList(); loadEmailList(); loadUsers(); }
        else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה במחיקת משתמש');
    }
}

// ============= EMAIL LIST =============

async function loadEmailList() {
    try {
        const response = await fetchNoCache(`${API_URL}/email-list`);
        const emails = await response.json();
        const emailsList = document.getElementById('emailsList');
        emailsList.innerHTML = '';
        emails.forEach(email => {
            const emailItem = document.createElement('div');
            emailItem.className = 'email-item';
            emailItem.innerHTML = `
                <div>
                    <strong>${email.email}</strong>
                    ${email.name ? `<br><small>${email.name}</small>` : ''}
                </div>
                <button class="btn btn-danger btn-small" onclick="deleteEmail(${email.id})">🗑️ מחק</button>
            `;
            emailsList.appendChild(emailItem);
        });
    } catch (error) {
        console.error('Error loading email list:', error);
    }
}

async function addManualEmail() {
    const email = document.getElementById('newEmailAddress').value.trim();
    const name  = document.getElementById('newEmailName').value.trim();
    if (!email) { alert('יש להזין כתובת אימייל'); return; }
    try {
        const response = await fetch(`${API_URL}/email-list`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, name, added_by: currentUser || 'Admin' })
        });
        const result = await response.json();
        if (result.success) {
            document.getElementById('newEmailAddress').value = '';
            document.getElementById('newEmailName').value = '';
            loadEmailList();
        } else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה בהוספת אימייל');
    }
}

async function deleteEmail(emailId) {
    if (!confirm('האם אתה בטוח שברצונך למחוק כתובת זו?')) return;
    try {
        const response = await fetch(`${API_URL}/email-list/${emailId}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) loadEmailList();
        else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה במחיקת אימייל');
    }
}

// ============= TABS =============

function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById(tabName + 'Tab').classList.add('active');
    event.target.classList.add('active');
    if (tabName === 'notifications') loadNotificationsTable();
}

// ============= EMAIL NOTIFICATIONS =============

async function loadNotificationsTable() {
    try {
        const response = await fetchNoCache(`${API_URL}/notifications`);
        const data = await response.json();
        const tbody = document.getElementById('notificationsTableBody');
        tbody.innerHTML = '';
        data.forEach(row => {
            const tr = document.createElement('tr');
            const fields = ['notify_status_change','notify_weekly_report','notify_new_event','notify_responsible','notify_overdue'];
            const allChecked = fields.every(f => row[f] === 1);
            let cells = `<td><strong>${row.user_name}</strong><br><small style="color:#888">${row.email}</small></td>`;
            fields.forEach(field => {
                cells += `<td style="text-align:center;">
                    <input type="checkbox" ${row[field] ? 'checked' : ''}
                        onchange="updateNotification(${row.user_id}, '${field}', this.checked)"
                        ${currentUserRole !== 'admin' ? 'disabled' : ''}>
                </td>`;
            });
            cells += `<td style="text-align:center;">
                <input type="checkbox" ${allChecked ? 'checked' : ''}
                    onchange="toggleAllNotifications(${row.user_id}, this.checked)"
                    ${currentUserRole !== 'admin' ? 'disabled' : ''}>
            </td>`;
            tr.innerHTML = cells;
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error('Error loading notifications:', error);
    }
}

async function updateNotification(userId, field, value) {
    try {
        await fetch(`${API_URL}/notifications/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field, value: value ? 1 : 0 })
        });
        loadNotificationsTable();
    } catch (error) {
        console.error('Error updating notification:', error);
    }
}

async function toggleAllNotifications(userId, checked) {
    try {
        await fetch(`${API_URL}/notifications/${userId}/all`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: checked ? 1 : 0 })
        });
        loadNotificationsTable();
    } catch (error) {
        console.error('Error toggling all notifications:', error);
    }
}

// ============= REPORTS =============

async function generateReport() {
    try {
        const response = await fetch(`${API_URL}/reports/excel`);
        if (!response.ok) throw new Error('Report generation failed');
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `דוח_אירועים_${new Date().toISOString().split('T')[0]}.xlsx`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(blobUrl); }, 500);
    } catch (err) {
        console.error('Report error:', err);
        alert('שגיאה בהפקת הדוח');
    }
}

// ============= ANALYSIS MODAL =============

const CHART_PALETTE = [
    '#6cffa9','#fff59d','#ff65a5','#a6bbff',
    '#ffb192','#D4ADFF','#91ffff','#ffc9ed',
    '#EAFF93','#ff94c9','#78ff69','#caffcb'
];

function destroyChart(id) {
    if (analysisCharts[id]) { analysisCharts[id].destroy(); delete analysisCharts[id]; }
}

function buildDonut(canvasId, labels, data) {
    destroyChart(canvasId);
    const ctx = document.getElementById(canvasId).getContext('2d');
    analysisCharts[canvasId] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{ data, backgroundColor: CHART_PALETTE.slice(0, labels.length), borderWidth: 2, borderColor: '#fff', hoverOffset: 8 }]
        },
        options: {
            responsive: true, cutout: '62%',
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 13 }, padding: 12, boxWidth: 14 } },
                tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed} (${Math.round(ctx.parsed / ctx.dataset.data.reduce((a,b) => a+b, 0) * 100)}%)` } }
            }
        }
    });
}

function buildBar(canvasId, labels, data, label, color) {
    destroyChart(canvasId);
    const ctx = document.getElementById(canvasId).getContext('2d');
    const bgColors = Array.isArray(color) ? color : labels.map((_, i) => CHART_PALETTE[i % CHART_PALETTE.length]);
    analysisCharts[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ label, data, backgroundColor: bgColors, borderRadius: 6, borderSkipped: false }] },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: '#e2e8f0' } },
                x: { grid: { display: false }, ticks: { font: { size: 12 } } }
            }
        }
    });
}

let _analysisEvents = [];

async function showAnalysisModal() {
    if (currentUserRole !== 'admin') { alert('אין לך הרשאה לפעולה זו'); return; }
    let events = rawEvents.length ? rawEvents : allEvents;
    try {
        const r = await fetchNoCache(`${API_URL}/events`);
        const all = await r.json();
        events = all.filter(e => e.is_deleted !== 1 && e.status !== 'הושלם הטיפול');
    } catch(e) {}
    _analysisEvents = events;
    document.getElementById('analysisModal').classList.add('active');

    document.querySelectorAll('.chart-filter-btn').forEach(b => b.classList.remove('active'));
    const allBtn = document.querySelector('#userChartFilters .chart-filter-btn');
    if (allBtn) allBtn.classList.add('active');

    setTimeout(() => {
        renderUserChart(events);
        const byStatus = {};
        events.forEach(e => { byStatus[e.status] = (byStatus[e.status] || 0) + 1; });
        buildDonut('chartByStatus', Object.keys(byStatus), Object.values(byStatus));
        const byUrgency = {};
        events.forEach(e => { byUrgency[e.urgency] = (byUrgency[e.urgency] || 0) + 1; });
        buildDonut('chartByUrgency', Object.keys(byUrgency), Object.values(byUrgency));
    }, 100);
}

function renderUserChart(events) {
    const byUser = {};
    events.forEach(e => { const n = e.responsible_person || 'לא שויך'; byUser[n] = (byUser[n] || 0) + 1; });
    if (Object.keys(byUser).length === 0) {
        destroyChart('chartByUser');
        const canvas = document.getElementById('chartByUser');
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = '16px Segoe UI'; ctx.fillStyle = '#999'; ctx.textAlign = 'center';
        ctx.fillText('אין נתונים', canvas.width / 2, canvas.height / 2);
        return;
    }
    buildBar('chartByUser', Object.keys(byUser), Object.values(byUser), 'אירועים לפי גורם אחראי', '#FF70AB');
}

function setUserChartFilter(type, btn) {
    document.querySelectorAll('.chart-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const today = new Date(); today.setHours(0,0,0,0);
    let filtered = _analysisEvents;
    if (type === 'overdue') {
        filtered = _analysisEvents.filter(e => e.status_deadline && new Date(e.status_deadline) < today && !CLOSED_STATUSES.includes(e.status));
    } else if (type === 'critical') {
        filtered = _analysisEvents.filter(e => e.urgency === 'קריטית');
    } else if (type === 'inprogress') {
        filtered = _analysisEvents.filter(e => e.status === 'בטיפול' || e.status === 'אירוע חדש');
    }
    renderUserChart(filtered);
}

function closeAnalysisModal() {
    document.getElementById('analysisModal').classList.remove('active');
}

// ============= UTILITY FUNCTIONS =============

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString.replace(' ', 'T'));
    return isNaN(date) ? dateString : date.toLocaleDateString('he-IL');
}

function formatDateTime(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString.replace(' ', 'T'));
    return isNaN(date) ? dateString : date.toLocaleString('he-IL');
}