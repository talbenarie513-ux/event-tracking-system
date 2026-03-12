// Configuration
const API_URL = 'http://localhost:5000/api'; // base URL for all API calls — change this to the server IP when deploying on a network
let currentUser = null;        // stores the name of the logged-in user — null means nobody is logged in
let currentUserRole = null;    // stores the role ('admin'/'planning'/'development') of the logged-in user
let allEvents = [];            // the current list of events being displayed in the table
let currentEventId = null;     // tracks which event's detail/history modal is currently open
let userPermissions = [];      // holds the permission list for the current role (loaded from server)
let columnFilters = {};        // object mapping column names to active filter values e.g. { status: ['בטיפול'] }
let currentSort = '';          // currently active sort key — not heavily used since sorting rewrites allEvents
let analysisCharts = {};       // stores Chart.js chart instances so they can be destroyed before re-rendering

const CLOSED_STATUSES = ['הושלם הטיפול', 'טופל חלקית', 'בהקפאה']; // statuses treated as "done" — excluded from active event counts

// ============= CACHE BUSTING =============
function fetchNoCache(url, options = {}) {
    // wraps fetch() to always bypass browser/server caching by adding a timestamp query param
    const timestamp = new Date().getTime();
    const separator = url.includes('?') ? '&' : '?'; // adds & if URL already has params, ? if not
    const nocacheUrl = `${url}${separator}_t=${timestamp}`;
    const headers = options.headers || {};
    headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'; // tells server not to serve cached response
    headers['Pragma'] = 'no-cache';   // older HTTP/1.0 cache control header — still sent for compatibility
    headers['Expires'] = '0';         // tells proxy/browser the content is already expired
    return fetch(nocacheUrl, { ...options, headers });
}

// ============= INIT =============
document.addEventListener('DOMContentLoaded', function() {
    // runs once the HTML is fully loaded — sets up all event listeners and loads initial data
    loadUsers();           // populates the user dropdown at the top of the page
    setTodayDate();        // sets the registration date field to today's date
    loadEventsReadOnly();  // loads events without requiring a logged-in user

    document.getElementById('userSelect').addEventListener('change', handleUserLogin);  // fires when user picks a name from the dropdown
    document.getElementById('searchBox').addEventListener('input', filterEvents);       // fires on every keystroke in the search box
    document.getElementById('eventForm').addEventListener('submit', handleEventSubmit); // fires when the event form's Save button is clicked
    document.getElementById('addUserForm').addEventListener('submit', handleAddUser);   // fires when the Add User form is submitted in admin panel

    document.getElementById('status').addEventListener('change', function() {
        // shows or hides the completion date field depending on whether the status is "הושלם הטיפול"
        const completionDateGroup = document.getElementById('completionDateGroup');
        const completionDate = document.getElementById('completionDate');
        if (this.value === 'הושלם הטיפול') {
            completionDateGroup.style.display = 'block';
            if (!completionDate.value) completionDate.value = new Date().toISOString().split('T')[0]; // auto-fills today's date
        } else {
            completionDateGroup.style.display = 'none';
            completionDate.value = ''; // clears the date if status is changed away from completed
        }
    });

    setupColumnFilters(); // attaches click listeners to all ▼ column header filter buttons

    document.querySelectorAll('.modal').forEach(modal => {
        // clicking outside any modal (on the dark overlay) closes all modals
        modal.addEventListener('click', function(e) {
            if (e.target === modal) closeAllModals(); // only triggers if the click was on the backdrop, not the modal content
        });
    });
});

function closeAllModals() {
    // closes every modal at once — called when clicking the backdrop overlay
    closeEventModal();
    closeDetailModal();
    closeAdminModal();
    closeAnalysisModal();
    closeHistoryModal();
    closeHelpModal();
    closeFilePreviewModal();
}

let myEventsActive = false; // tracks whether the "My Events" filter is currently active

function toggleMyEvents() {
    // toggles between showing all events and only events where the current user is the responsible person
    const btn = document.getElementById('myEventsBtn');
    myEventsActive = !myEventsActive;
    if (myEventsActive) {
        const myEvents = allEvents.filter(e =>
            e.responsible_person && e.responsible_person === currentUser // only events assigned to current user
        );
        btn.textContent = '✖ כל האירועים';
        btn.style.background = '#e53e3e'; // red button signals the filter is active
        displayEvents(myEvents);
    } else {
        btn.textContent = '📋 האירועים שלי';
        btn.style.background = ''; // resets to default color
        displayEvents(allEvents);
    }
}

// ============= HELP MODAL =============
function showHelpModal() { document.getElementById('helpModal').classList.add('active'); }  // shows the help modal by adding the 'active' CSS class
function closeHelpModal() { document.getElementById('helpModal').classList.remove('active'); } // hides the help modal

// ============= FILE PREVIEW MODAL =============

async function openFile(fileId) {
    // fetches preview data for a file from the server and renders it in the preview modal
    try {
        const res = await fetchNoCache(`${API_URL}/files/${fileId}/view`);

        // Handle HTTP errors (4xx / 5xx)
        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: `שגיאת שרת ${res.status}` }));
            if (confirm(`שגיאה בפתיחת הקובץ:\n${err.error}\n\nהאם להוריד את הקובץ במקום?`)) {
                downloadFile(fileId); // falls back to downloading if preview fails
            }
            return;
        }

        const data = await res.json();

        if (!data.previewable) {
            // server said this file type can't be previewed — offer to download instead
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
        dlBtn.onclick = () => downloadFile(fileId); // wires up the download button inside the preview modal
        body.innerHTML = '';

        switch (data.preview_type) {
            case 'base64': {
                // images and PDFs come back as base64 — decode into a data URI for display
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
                // plain text files — wrapped in <pre> to preserve whitespace and line breaks
                body.innerHTML =
                    `<pre style="white-space:pre-wrap;word-break:break-word;font-size:14px;`
                    + `line-height:1.6;padding:10px;background:#f7fafc;border-radius:8px;`
                    + `max-height:75vh;overflow-y:auto;direction:ltr;text-align:left;">`
                    + escapeHtml(data.content) + `</pre>`; // escapeHtml prevents XSS from file content
                break;
            }
            case 'html_table': {
                // Excel/CSV files — server converted them to an HTML table
                body.innerHTML =
                    `<div style="max-height:75vh;overflow:auto;border-radius:8px;">`
                    + data.html + `</div>`;
                break;
            }
            case 'html_doc': {
                // Word .docx files — server converted them to HTML
                body.innerHTML =
                    `<div style="max-height:75vh;overflow-y:auto;padding:20px;`
                    + `background:#fff;border-radius:8px;border:1px solid #e2e8f0;">`
                    + data.html + `</div>`;
                break;
            }
            default:
                body.innerHTML = `<p style="color:#999;text-align:center;">אין תצוגה מקדימה זמינה</p>`;
        }

        modal.classList.add('active'); // show the modal after content is ready

    } catch (err) {
        console.error('Error opening file:', err);
        if (confirm(`שגיאה בפתיחת הקובץ: ${err.message}\n\nהאם להוריד את הקובץ במקום?`)) {
            downloadFile(fileId);
        }
    }
}

function escapeHtml(str) {
    // converts special HTML characters to safe entities — prevents XSS when displaying file content
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function closeFilePreviewModal() {
    // hides the file preview modal and clears its content to free memory
    const modal = document.getElementById('filePreviewModal');
    modal.classList.remove('active');
    document.getElementById('filePreviewBody').innerHTML = ''; // clear content so stale data doesn't flash on next open
}

// ============= USER MANAGEMENT =============

async function loadUsers() {
    // fetches all users from the server and populates the user-select dropdown at the top
    try {
        const response = await fetchNoCache(`${API_URL}/users`);
        const users = await response.json();
        const userSelect = document.getElementById('userSelect');
        userSelect.innerHTML = '<option value="">בחר משתמש...</option>'; // reset dropdown before repopulating
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user.name;
            option.dataset.role = user.role; // stores role in a data attribute so handleUserLogin can read it without another API call
            option.textContent = `${user.name} (${getRoleLabel(user.role)})`;
            userSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

async function handleUserLogin() {
    // fires when the user selects their name from the dropdown — sets up permissions and reloads data
    const userSelect = document.getElementById('userSelect');
    const selectedOption = userSelect.options[userSelect.selectedIndex];
    if (selectedOption.value) {
        currentUser = selectedOption.value;
        currentUserRole = selectedOption.dataset.role; // role was stored in data attribute by loadUsers()
        if (currentUserRole === 'admin') {
            document.getElementById('adminBtn').classList.remove('hidden');    // only admins see admin panel button
            document.getElementById('analysisBtn').classList.remove('hidden'); // only admins see analysis charts button
        } else {
            document.getElementById('adminBtn').classList.add('hidden');
            document.getElementById('analysisBtn').classList.add('hidden');
        }
        document.getElementById('myEventsBtn').classList.remove('hidden'); // shown for all logged-in users
        await loadPermissions(currentUserRole); // fetch the permission list for this role
        updateNewEventButton(); // shows/hides the "New Event" button based on role
        loadEvents();  // reload events now that we know the user (to show edit/delete buttons)
        loadStats();   // reload stats counters
    } else {
        // user deselected — reset everything back to read-only state
        currentUser = null;
        currentUserRole = null;
        userPermissions = [];
        document.getElementById('adminBtn').classList.add('hidden');
        document.getElementById('analysisBtn').classList.add('hidden');
        document.getElementById('newEventBtn').classList.add('hidden');
        document.getElementById('myEventsBtn').classList.add('hidden');
        loadEventsReadOnly(); // show events without edit/delete buttons
    }
}

function updateNewEventButton() {
    // shows or hides the "New Event" button — development role cannot create events
    const newEventBtn = document.getElementById('newEventBtn');
    if (currentUserRole === 'development') {
        newEventBtn.classList.add('hidden'); // development users are not allowed to create events
    } else if (currentUser) {
        newEventBtn.classList.remove('hidden');
    } else {
        newEventBtn.classList.add('hidden');
    }
}

async function loadPermissions(role) {
    // fetches the permission list for the given role from the server and stores it in userPermissions
    try {
        const response = await fetchNoCache(`${API_URL}/permissions/${role}`);
        const data = await response.json();
        userPermissions = data.permissions;
    } catch (error) {
        console.error('Error loading permissions:', error);
    }
}

function getRoleLabel(role) {
    // converts an English role key to its Hebrew display name
    const roles = { 'admin': 'אדמין', 'planning': 'תכנון', 'development': 'פיתוח' };
    return roles[role] || role; // falls back to the raw value if role is unknown
}

// ============= COLUMN FILTERS =============

function setupColumnFilters() {
    // attaches click listeners to every ▼ column header button
    document.querySelectorAll('.column-filter').forEach(filter => {
        filter.addEventListener('click', function(e) {
            e.stopPropagation(); // prevents the document click listener from immediately closing the dropdown
            toggleColumnFilter(this.dataset.column, this);
        });
    });
    document.addEventListener('click', function() {
        // clicking anywhere outside a dropdown closes all open filter dropdowns
        document.querySelectorAll('.filter-dropdown').forEach(d => d.remove());
    });
}

function toggleColumnFilter(column, element) {
    // builds and shows (or closes) a filter dropdown for the clicked column
    document.querySelectorAll('.filter-dropdown').forEach(d => d.remove()); // close any already-open dropdown first
    const uniqueValues = [...new Set(allEvents.map(e => e[column]))].filter(v => v); // get distinct non-empty values for this column
    if (uniqueValues.length === 0) return; // nothing to filter — don't show an empty dropdown

    const dropdown = document.createElement('div');
    dropdown.className = 'filter-dropdown';
    dropdown.style.position = 'fixed'; // fixed so it doesn't get clipped by table overflow

    const rect = element.getBoundingClientRect(); // position the dropdown below the clicked column header
    dropdown.style.top = (rect.bottom + 5) + 'px';

    const dropdownWidth = 180;
    let leftPos = rect.left;
    if (leftPos + dropdownWidth > window.innerWidth - 5) leftPos = window.innerWidth - dropdownWidth - 5; // prevent overflow off right edge
    if (leftPos < 5) leftPos = 5; // prevent overflow off left edge
    dropdown.style.left = leftPos + 'px';

    const clearOption = document.createElement('label');
    clearOption.innerHTML = `<input type="checkbox" ${!columnFilters[column] ? 'checked' : ''} onchange="clearColumnFilter('${column}')"><strong>הצג הכל</strong>`;
    dropdown.appendChild(clearOption);

    uniqueValues.forEach(value => {
        // add a checkbox for each unique value — checked if it's currently in the active filter
        const label = document.createElement('label');
        const isChecked = !columnFilters[column] || columnFilters[column].includes(value);
        label.innerHTML = `<input type="checkbox" ${isChecked ? 'checked' : ''} onchange="updateColumnFilter('${column}', '${value}', this.checked)">${value}`;
        dropdown.appendChild(label);
    });

    document.body.appendChild(dropdown);
    dropdown.addEventListener('click', e => e.stopPropagation()); // prevent clicks inside dropdown from bubbling to document and closing it
}

function updateColumnFilter(column, value, checked) {
    // adds or removes a specific value from the active filter for a column then re-filters the table
    if (!columnFilters[column]) columnFilters[column] = [];
    if (checked) {
        if (!columnFilters[column].includes(value)) columnFilters[column].push(value);
    } else {
        columnFilters[column] = columnFilters[column].filter(v => v !== value);
    }
    filterEvents();
}

function clearColumnFilter(column) {
    // removes all filters for a column (shows all values) and closes the dropdown
    delete columnFilters[column];
    filterEvents();
    document.querySelectorAll('.filter-dropdown').forEach(d => d.remove());
}

function filterByStat(type) {
    // filters the table when a stat card is clicked — second click on the same card clears the filter
    const cards = document.querySelectorAll('.stat-card');
    const isActive = document.querySelector(`.stat-card.active-filter[data-stat="${type}"]`);
    cards.forEach(c => { c.classList.remove('active-filter'); c.removeAttribute('data-stat'); }); // clear all card highlights
    if (isActive) { displayEvents(allEvents); return; } // clicking active card again resets the filter

    const idx = ['total', 'overdue', 'critical', 'inprogress'];
    cards[idx.indexOf(type)].classList.add('active-filter'); // highlight the clicked card
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
    // filters the table to show only events with the given status — used from elsewhere in the UI
    columnFilters = { status: [status] };
    filterEvents();
}

// ============= SEARCH AND FILTER =============

function filterEvents() {
    // combines the text search box and all active column filters to produce the displayed event list
    const searchTerm = document.getElementById('searchBox').value.toLowerCase();
    let filtered = allEvents.filter(event => {
        const matchesSearch = !searchTerm ||
            event.event_summary.toLowerCase().includes(searchTerm) ||
            event.system.toLowerCase().includes(searchTerm) ||
            event.event_details.toLowerCase().includes(searchTerm) ||
            event.affected_customers.toLowerCase().includes(searchTerm);
        let matchesFilters = true;
        for (const [column, values] of Object.entries(columnFilters)) {
            if (values.length > 0 && !values.includes(event[column])) { matchesFilters = false; break; } // event must match ALL active column filters
        }
        return matchesSearch && matchesFilters;
    });
    displayEvents(filtered);
}

function sortEvents() {
    // re-orders allEvents based on the selected sort option then re-applies filters
    const sortValue = document.getElementById('sortSelect').value;
    if (!sortValue) { filterEvents(); return; } // no sort selected — just re-filter
    let sorted = [...allEvents]; // copy so we don't mutate allEvents while iterating
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
    allEvents = sorted; // overwrite allEvents with the sorted version so filters operate on the sorted data
    filterEvents();
}

// ============= SHOW COMPLETED TOGGLE =============

let rawEvents = []; // holds the complete unfiltered event list fetched from the server

function toggleCompleted() {
    // called when the "show completed" checkbox changes — ignores if deleted view is active
    if (document.getElementById('showDeleted').checked) return;
    applyCompletedFilter();
}

function applyCompletedFilter() {
    // filters rawEvents based on the "show completed" checkbox and updates allEvents and display
    const showCompleted = document.getElementById('showCompleted').checked;
    columnFilters = {}; // clear column filters when switching modes to avoid conflicting filters
    if (showCompleted) {
        allEvents = rawEvents.filter(e => e.status === 'הושלם הטיפול'); // only completed events
    } else {
        allEvents = rawEvents.filter(e => e.status !== 'הושלם הטיפול' && e.status !== 'בהקפאה'); // active events only
    }
    displayEvents(allEvents);
}

function showAllEvents() {
    // resets all filters and shows every non-deleted event — called by the "כל האירועים" button
    document.getElementById('showCompleted').checked = false;
    document.getElementById('showDeleted').checked = false;
    document.getElementById('showCompleted').disabled = false;
    document.getElementById('deletedBanner').classList.remove('active');
    columnFilters = {};
    allEvents = rawEvents; // restore full list
    displayEvents(allEvents);
}

// ============= DELETED EVENTS TOGGLE =============

function toggleDeleted() {
    // switches between the normal event view and the "recently deleted" view
    const showDeleted = document.getElementById('showDeleted').checked;
    const showCompleted = document.getElementById('showCompleted');
    const banner = document.getElementById('deletedBanner');
    if (showDeleted) {
        showCompleted.disabled = true;  // can't combine "show completed" and "show deleted" at the same time
        banner.classList.add('active'); // show the red warning banner at the top of the table
        loadDeletedEvents();
    } else {
        showCompleted.disabled = false;
        banner.classList.remove('active');
        loadEvents(); // go back to normal event view
    }
}

async function loadDeletedEvents() {
    // fetches all events including deleted ones and filters to only the soft-deleted rows
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.classList.remove('hidden');
    try {
        const response = await fetchNoCache(`${API_URL}/events?show_deleted=true`);
        const allFetched = await response.json();
        const deleted = allFetched.filter(e => e.is_deleted === 1); // keep only soft-deleted events
        displayDeletedEvents(deleted);
    } catch (error) {
        console.error('Error loading deleted events:', error);
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

function displayDeletedEvents(events) {
    // renders deleted events in the table with a greyed-out style and a restore button instead of edit/delete
    const tbody = document.getElementById('eventsTableBody');
    tbody.innerHTML = '';
    if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; color:#999;">אין אירועים שנמחקו לאחרונה</td></tr>';
        return;
    }
    events.forEach(event => {
        const row = document.createElement('tr');
        row.style.opacity = '0.6';      // visually dimmed to signal these are deleted
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
    // sends a PUT request to un-delete a soft-deleted event then refreshes the deleted events list
    if (!confirm('האם לשחזר אירוע זה?')) return;
    try {
        const response = await fetch(`${API_URL}/events/${eventId}/restore`, { method: 'PUT' });
        const result = await response.json();
        if (result.success) {
            alert('האירוע שוחזר בהצלחה');
            loadDeletedEvents(); // refresh the deleted events list
            loadStats();         // update the stat card numbers
        } else {
            alert('שגיאה: ' + result.error);
        }
    } catch (error) {
        alert('שגיאה בשחזור האירוע');
    }
}

// ============= EVENTS MANAGEMENT =============

async function loadEventsReadOnly() {
    // loads and displays events without requiring a logged-in user — no edit/delete buttons shown
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.classList.remove('hidden');
    try {
        const response = await fetchNoCache(`${API_URL}/events`);
        rawEvents = await response.json();
        allEvents = rawEvents.filter(e => e.status !== 'הושלם הטיפול'); // hide completed events by default
        displayEvents(allEvents);
        const statsResponse = await fetchNoCache(`${API_URL}/stats`);
        const stats = await statsResponse.json();
        document.getElementById('totalEvents').textContent = stats.total_events || 0;
        document.getElementById('overdueEvents').textContent = stats.overdue || 0;
        document.getElementById('criticalEvents').textContent = stats.critical || 0;
        document.getElementById('inProgressEvents').textContent = Object.entries(stats.by_status)
            .filter(([s]) => !['בהקפאה','הושלם הטיפול','טופל חלקית','אירוע חדש'].includes(s))
            .reduce((a,[,v]) => a+v, 0); // sum up all "in progress" status counts
    } catch (error) {
        console.error('Error loading events:', error);
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

async function loadEvents() {
    // loads events for a logged-in user — then applies the completed/active filter
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.classList.remove('hidden');
    try {
        const response = await fetchNoCache(`${API_URL}/events`);
        rawEvents = await response.json();
        applyCompletedFilter(); // apply the current checkbox state to the fresh data
    } catch (error) {
        console.error('Error loading events:', error);
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

function displayEvents(events) {
    // renders a list of event objects into the main table — called after every filter/sort/load
    const tbody = document.getElementById('eventsTableBody');
    tbody.innerHTML = ''; // clear existing rows before rendering new ones
    if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align: center;">אין אירועים להצגה</td></tr>';
        return;
    }
    events.forEach(event => {
        const row = document.createElement('tr');
        row.onclick = () => showEventDetail(event.id); // clicking a row opens the detail modal

        let urgencyClass = 'urgency-low';
        if (event.urgency === 'קריטית') urgencyClass = 'urgency-critical';
        else if (event.urgency === 'גבוהה') urgencyClass = 'urgency-high';
        else if (event.urgency === 'בינונית') urgencyClass = 'urgency-medium';

        const today = new Date(); today.setHours(0,0,0,0);
        const isOverdue = new Date(event.status_deadline) < today && !CLOSED_STATUSES.includes(event.status);
        if (isOverdue) row.classList.add('row-overdue'); // red background for overdue rows

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
    // fetches full event data and renders it in the read-only detail modal
    try {
        const response = await fetchNoCache(`${API_URL}/events/${eventId}`);
        const event = await response.json();
        currentEventId = eventId; // store so history/edit/delete buttons know which event to act on
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

        const canEdit = currentUser && currentUserRole !== 'development'; // development role cannot edit events
        document.getElementById('detailEditBtn').classList.toggle('hidden', !canEdit);
        document.getElementById('detailDeleteBtn').classList.toggle('hidden', !canEdit);
        document.getElementById('detailModal').classList.add('active');
    } catch (error) {
        console.error('Error loading event details:', error);
        alert('שגיאה בטעינת פרטי האירוע');
    }
}

function closeDetailModal() {
    // closes the detail modal and clears the tracked event ID
    document.getElementById('detailModal').classList.remove('active');
    currentEventId = null;
}

function handleDetailEdit() {
    // closes the detail modal and immediately opens the edit form for the same event
    const id = currentEventId;
    closeDetailModal();
    if (id) editEvent(id);
}

function handleDetailDelete() {
    // closes the detail modal and triggers the delete confirmation for the same event
    const id = currentEventId;
    if (id) { closeDetailModal(); deleteEvent(id); }
}

// ============= HISTORY MODAL =============

async function showHistoryModal() {
    // fetches and renders the full audit log for the currently open event
    const eventId = currentEventId;
    if (!eventId) return;

    const modal = document.getElementById('historyModal');
    const content = document.getElementById('historyContent');
    content.innerHTML = '<div style="text-align:center;padding:30px;color:#667eea;">⏳ טוען היסטוריה...</div>'; // show loading state
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

        // always show the creation entry first as a fixed header
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
            // group consecutive audit log entries by the same user at the same timestamp into one UI card
            const groups = [];
            for (const entry of data.entries) {
                if (entry.action === 'created') continue; // creation is shown separately above
                const last = groups[groups.length - 1];
                if (last && last.action === 'updated' && entry.action === 'updated' &&
                    last.changed_by === entry.changed_by && last.changed_at === entry.changed_at) {
                    last.fields.push(entry); // same save operation — group the fields together
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
                    // deleted / restored actions — simpler card with no field rows
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
    // fetches the four stat card numbers from the server and updates the DOM
    try {
        const response = await fetchNoCache(`${API_URL}/stats`);
        const stats = await response.json();
        document.getElementById('totalEvents').textContent = stats.total_events || 0;
        document.getElementById('overdueEvents').textContent = stats.overdue || 0;
        document.getElementById('criticalEvents').textContent = stats.critical || 0;
        document.getElementById('inProgressEvents').textContent = Object.entries(stats.by_status)
            .filter(([s]) => !['בהקפאה','הושלם הטיפול','טופל חלקית','אירוע חדש'].includes(s))
            .reduce((a,[,v]) => a+v, 0); // sum all "active working" statuses
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ============= EVENT FORM =============

function showNewEventForm() {
    // opens the event modal pre-cleared for creating a brand new event
    if (!currentUser) { alert('יש לבחור משתמש תחילה'); return; }
    if (currentUserRole === 'development') { alert('משתמשי פיתוח אינם יכולים ליצור אירועים חדשים'); return; }

    document.getElementById('modalTitle').textContent = 'אירוע חדש';
    document.getElementById('eventForm').reset(); // clears all form fields
    document.getElementById('eventId').value = '';       // hidden field used to detect create vs edit
    document.getElementById('eventIdInput').value = '';  // optional custom ID input
    document.getElementById('filesList').innerHTML = '';
    document.getElementById('fileNameDisplay').textContent = 'לא נבחרו קבצים';
    setTodayDate();
    setDefaultDeadline(); // sets deadline to today + 3 days
    document.getElementById('completionDateGroup').style.display = 'none';
    document.getElementById('completionDate').value = '';
    document.getElementById('systemOtherGroup').classList.add('hidden');
    document.getElementById('systemOther').required = false;
    document.getElementById('systemOther').value = '';
    document.getElementById('responsiblePersonOther').classList.add('hidden');
    document.getElementById('responsiblePersonOther').value = '';
    populateResponsibleDropdown(''); // populate with current users, no pre-selected value
    enableAllFormFields();
    applyFieldRestrictions(); // disable fields the current role isn't allowed to edit
    document.getElementById('eventModal').classList.add('active');
}

async function editEvent(eventId) {
    // fetches an existing event and pre-fills the modal form with its current values
    if (!currentUser) { alert('יש לבחור משתמש תחילה'); return; }
    try {
        const response = await fetchNoCache(`${API_URL}/events/${eventId}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const event = await response.json();

        document.getElementById('modalTitle').textContent = `עריכת אירוע #${event.id}`;
        document.getElementById('eventId').value = event.id; // hidden field — non-empty means this is an edit
        document.getElementById('eventIdInput').value = event.id;
        document.getElementById('registrationDate').value = event.registration_date;
        document.getElementById('firstContactDate').value = event.first_contact_date || '';

        const systemSelect = document.getElementById('system');
        const systems = event.system.split(',').map(s => s.trim()); // handles comma-separated multi-system values
        const standardOptions = ['ספיר', 'שמיר', 'גאודאטה', 'אחר'];
        Array.from(systemSelect.options).forEach(opt => { opt.selected = systems.includes(opt.value); }); // pre-select matching options
        const nonStandard = systems.filter(s => !standardOptions.includes(s)); // detect custom system names
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
            // callback runs after dropdown is populated so restrictions are applied to the final state
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
    // removes the disabled attribute from every field in the form before re-applying role restrictions
    document.querySelectorAll('#eventForm input, #eventForm select, #eventForm textarea')
        .forEach(input => { input.disabled = false; });
}

// ============= FIELD RESTRICTIONS =============

function applyFieldRestrictions() {
    // disables form fields that the current user role is not permitted to edit
    if (currentUserRole === 'admin') {
        // admin can edit everything — also makes all fields optional (no required validation)
        document.querySelectorAll('#eventForm input, #eventForm select, #eventForm textarea')
            .forEach(input => { input.required = false; input.disabled = false; });
        return;
    }
    if (currentUserRole === 'development') {
        // development can only update status-related and assignment fields — basic event info is locked
        document.querySelectorAll('#eventForm input, #eventForm select, #eventForm textarea')
            .forEach(input => {
                const allowedFields = ['status','statusDetails','completionDate','responsiblePerson','responsiblePersonOther','statusDeadline','priceQuote','additionalNotes','eventClassification'];
                if (!allowedFields.includes(input.id)) input.disabled = true;
            });
    }
    if (currentUserRole === 'planning') {
        // planning can edit basic event info but cannot assign responsible persons or update status
        const blockedFields = ['responsiblePerson','responsiblePersonOther','status','statusDetails','completionDate','priceQuote'];
        document.querySelectorAll('#eventForm input, #eventForm select, #eventForm textarea')
            .forEach(input => { if (blockedFields.includes(input.id)) input.disabled = true; });
    }
}

function setTodayDate() {
    // sets the registration date input to today's date in YYYY-MM-DD format
    document.getElementById('registrationDate').value = new Date().toISOString().split('T')[0];
}

function setDefaultDeadline() {
    // sets the status deadline input to 3 days from today as the default
    const d = new Date();
    d.setDate(d.getDate() + 3);
    document.getElementById('statusDeadline').value = d.toISOString().split('T')[0];
}

function updateFileNameDisplay() {
    // updates the file name label next to the file input after the user selects files
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
    // shows or hides the free-text "other" input when "אחר" is selected in the responsible person dropdown
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
    // fetches the current user list and builds the responsible person dropdown with an "other" option at the end
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
                select.value = selectedValue; // pre-select if the value is in the list
            } else {
                // value is not in the user list — select "אחר" and fill the text input
                select.value = 'אחר';
                const otherInput = document.getElementById('responsiblePersonOther');
                otherInput.classList.remove('hidden');
                otherInput.value = selectedValue;
            }
        }
        if (callback) callback(); // call callback after dropdown is fully populated
    });
}

function toggleSystemOtherInput() {
    // shows or hides the custom system name text input when "אחר" is selected in the multi-select
    const systemSelect = document.getElementById('system');
    const otherGroup   = document.getElementById('systemOtherGroup');
    const otherInput   = document.getElementById('systemOther');
    const selected     = Array.from(systemSelect.selectedOptions).map(o => o.value);
    if (selected.includes('אחר')) {
        otherGroup.classList.remove('hidden');
        otherInput.required = true; // make the custom name required when "אחר" is chosen
    } else {
        otherGroup.classList.add('hidden');
        otherInput.required = false;
        otherInput.value    = '';
    }
}

// ============= HANDLE SUBMIT =============

async function handleEventSubmit(e) {
    // handles form submission for both creating a new event and saving edits to an existing one
    e.preventDefault(); // stop the browser's default form POST behavior
    const eventId = document.getElementById('eventId').value;
    const isEdit = eventId !== ''; // empty hidden field means new event, non-empty means edit

    // resolve the system field — replaces "אחר" with the custom typed value
    const systemSelect = document.getElementById('system');
    const selectedSystems = Array.from(systemSelect.selectedOptions).map(o => o.value);
    const systemOtherValue = document.getElementById('systemOther').value.trim();
    const finalSystems = selectedSystems.map(s => (s === 'אחר' && systemOtherValue) ? systemOtherValue : s);
    const systemValue = finalSystems.join(', '); // multiple systems stored as comma-separated string

    // resolve the responsible person — replaces "אחר" with the custom typed value
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

    if (!isEdit && customEventId) eventData.event_id = customEventId; // only set custom ID for new events
    if (isEdit) eventData.event_id = parseInt(eventId);

    try {
        const url    = isEdit ? `${API_URL}/events/${eventId}` : `${API_URL}/events`;
        const method = isEdit ? 'PUT' : 'POST'; // PUT for update, POST for create
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(eventData)
        });
        const result = await response.json();
        if (result.success) {
            alert(result.message);
            closeEventModal();
            loadEvents(); // refresh the table with the new/updated event
            loadStats();  // refresh the stat cards
        } else {
            alert('שגיאה: ' + result.error);
        }
    } catch (error) {
        console.error('Error saving event:', error);
        alert('שגיאה בשמירת האירוע');
    }
}

async function deleteEvent(eventId) {
    // sends a DELETE request to soft-delete an event after user confirmation
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
    // uploads all selected files one by one for the currently open event
    const eventId = document.getElementById('eventId').value;
    if (!eventId) { alert('יש לשמור את האירוע תחילה לפני העלאת קבצים'); return; } // can't attach files to an unsaved event
    const fileInput = document.getElementById('fileInput');
    if (fileInput.files.length === 0) { alert('לא נבחרו קבצים'); return; }

    for (let i = 0; i < fileInput.files.length; i++) {
        const formData = new FormData(); // FormData is needed for file uploads — can't use JSON
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
    // refresh the files list after upload
    const response = await fetchNoCache(`${API_URL}/events/${eventId}`);
    const event = await response.json();
    displayEventFiles(event.files || []);
    fileInput.value = ''; // clear the file input so the same files can't be accidentally re-uploaded
    document.getElementById('fileNameDisplay').textContent = 'לא נבחרו קבצים';
    alert('הקבצים הועלו בהצלחה');
}

function displayEventFiles(files) {
    // renders the list of attached files in the edit form's file section
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
    // downloads a file by fetching it as a binary blob and triggering a browser save dialog
    try {
        const response = await fetch(`${API_URL}/files/${fileId}/download`);
        if (!response.ok) throw new Error('שגיאת שרת: ' + response.status);
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob); // creates a temporary in-browser URL for the blob
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = filename || 'download'; // sets the filename shown in the save dialog
        document.body.appendChild(a);
        a.click(); // programmatically click the link to trigger the download
        setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(blobUrl); }, 500); // cleanup after download starts
    } catch (err) {
        console.error('Download error:', err);
        alert('שגיאה בהורדת הקובץ: ' + err.message);
    }
}

async function deleteFile(fileId) {
    // deletes a file from the server (both DB record and disk) after confirmation then refreshes the list
    if (!confirm('האם אתה בטוח שברצונך למחוק קובץ זה?')) return;
    try {
        const response = await fetch(`${API_URL}/files/${fileId}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) {
            const eventId = document.getElementById('eventId').value;
            const eventResponse = await fetchNoCache(`${API_URL}/events/${eventId}`);
            const event = await eventResponse.json();
            displayEventFiles(event.files || []); // refresh file list after deletion
        } else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה במחיקת הקובץ');
    }
}

// ============= ADMIN PANEL =============

function showAdminPanel() {
    // opens the admin panel modal — only accessible to admin role
    if (currentUserRole !== 'admin') { alert('אין לך הרשאה לפעולה זו'); return; }
    loadUsersList();   // populate the users tab
    loadEmailList();   // populate the email list tab
    document.getElementById('adminModal').classList.add('active');
}

function closeAdminModal() { document.getElementById('adminModal').classList.remove('active'); }

async function loadUsersList() {
    // fetches all users and renders them in the admin panel with edit/delete buttons
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
    // shows or hides the inline edit form for a specific user row
    document.getElementById(`editForm_${userId}`).classList.toggle('open');
}

async function saveUser(userId) {
    // saves changes to a user's name, role, and email
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
        if (result.success) { loadUsersList(); loadUsers(); } // refresh both the admin panel and the login dropdown
        else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה בשמירת המשתמש');
    }
}

async function handleAddUser(e) {
    // handles the "Add User" form submission in the admin panel
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
            loadUsersList();  // refresh admin panel user list
            loadEmailList();  // new user is also added to email list
            loadUsers();      // refresh login dropdown
        } else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה בהוספת משתמש');
    }
}

async function deleteUser(userId, userName) {
    // permanently deletes a user after confirmation and refreshes all affected lists
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
    // fetches the notification email list and renders it in the admin panel emails tab
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
    // adds a manually entered email address to the notification list
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
            loadEmailList(); // refresh the list to show the new entry
        } else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה בהוספת אימייל');
    }
}

async function deleteEmail(emailId) {
    // removes an email from the notification list after confirmation
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
    // switches between tabs in the admin panel — hides all, shows the clicked one
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById(tabName + 'Tab').classList.add('active');
    event.target.classList.add('active'); // highlight the clicked tab button
    if (tabName === 'notifications') loadNotificationsTable(); // lazy-load notifications only when that tab is opened
}

// ============= EMAIL NOTIFICATIONS =============

async function loadNotificationsTable() {
    // fetches user notification preferences and renders them as a checkbox table in the admin panel
    try {
        const response = await fetchNoCache(`${API_URL}/notifications`);
        const data = await response.json();
        const tbody = document.getElementById('notificationsTableBody');
        tbody.innerHTML = '';
        data.forEach(row => {
            const tr = document.createElement('tr');
            const fields = ['notify_status_change','notify_weekly_report','notify_new_event','notify_responsible','notify_overdue'];
            const allChecked = fields.every(f => row[f] === 1); // used to determine if the "check all" box should be checked
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
    // toggles a single notification checkbox and saves the change to the server
    try {
        await fetch(`${API_URL}/notifications/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field, value: value ? 1 : 0 })
        });
        loadNotificationsTable(); // re-render the table to reflect the new state
    } catch (error) {
        console.error('Error updating notification:', error);
    }
}

async function toggleAllNotifications(userId, checked) {
    // turns all notification types on or off for a user at once
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
    // requests the Excel report from the server and triggers a browser download
    try {
        const response = await fetch(`${API_URL}/reports/excel`);
        if (!response.ok) throw new Error('Report generation failed');
        const blob = await response.blob(); // receive the file as binary data
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `דוח_אירועים_${new Date().toISOString().split('T')[0]}.xlsx`; // filename includes today's date
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
]; // fixed color palette used for all charts to keep a consistent look

function destroyChart(id) {
    // destroys an existing Chart.js instance by canvas ID — must be done before drawing a new chart on the same canvas
    if (analysisCharts[id]) { analysisCharts[id].destroy(); delete analysisCharts[id]; }
}

function buildDonut(canvasId, labels, data) {
    // creates a doughnut chart on the given canvas with the provided labels and data
    destroyChart(canvasId);
    const ctx = document.getElementById(canvasId).getContext('2d');
    analysisCharts[canvasId] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{ data, backgroundColor: CHART_PALETTE.slice(0, labels.length), borderWidth: 2, borderColor: '#fff', hoverOffset: 8 }]
        },
        options: {
            responsive: true, cutout: '62%', // cutout makes it a donut instead of a full pie
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 13 }, padding: 12, boxWidth: 14 } },
                tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed} (${Math.round(ctx.parsed / ctx.dataset.data.reduce((a,b) => a+b, 0) * 100)}%)` } } // shows count and percentage in tooltip
            }
        }
    });
}

function buildBar(canvasId, labels, data, label, color) {
    // creates a bar chart on the given canvas — used for the "events per responsible person" chart
    destroyChart(canvasId);
    const ctx = document.getElementById(canvasId).getContext('2d');
    const bgColors = Array.isArray(color) ? color : labels.map((_, i) => CHART_PALETTE[i % CHART_PALETTE.length]); // cycle through palette if more bars than colors
    analysisCharts[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ label, data, backgroundColor: bgColors, borderRadius: 6, borderSkipped: false }] },
        options: {
            responsive: true,
            plugins: { legend: { display: false } }, // hide legend since bar labels are on the x-axis
            scales: {
                y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: '#e2e8f0' } },
                x: { grid: { display: false }, ticks: { font: { size: 12 } } }
            }
        }
    });
}

let _analysisEvents = []; // cached events list used by the analysis modal filter buttons

async function showAnalysisModal() {
    // loads events and renders all three analysis charts in the analysis modal
    if (currentUserRole !== 'admin') { alert('אין לך הרשאה לפעולה זו'); return; }
    let events = rawEvents.length ? rawEvents : allEvents;
    try {
        // always fetch fresh data for analysis — ignore the cached rawEvents
        const r = await fetchNoCache(`${API_URL}/events`);
        const all = await r.json();
        events = all.filter(e => e.is_deleted !== 1 && e.status !== 'הושלם הטיפול'); // exclude deleted and completed
    } catch(e) {}
    _analysisEvents = events;
    document.getElementById('analysisModal').classList.add('active');

    // reset the filter buttons to "all" state
    document.querySelectorAll('.chart-filter-btn').forEach(b => b.classList.remove('active'));
    const allBtn = document.querySelector('#userChartFilters .chart-filter-btn');
    if (allBtn) allBtn.classList.add('active');

    setTimeout(() => {
        // small delay to ensure the modal is visible before drawing charts — otherwise canvas size is 0
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
    // renders or re-renders the "events per responsible person" bar chart with the given event list
    const byUser = {};
    events.forEach(e => { const n = e.responsible_person || 'לא שויך'; byUser[n] = (byUser[n] || 0) + 1; }); // group events by responsible person
    if (Object.keys(byUser).length === 0) {
        // no data — draw an empty state message on the canvas directly
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
    // filters the responsible person bar chart by event type when a filter button is clicked
    document.querySelectorAll('.chart-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active'); // highlight the clicked filter button
    const today = new Date(); today.setHours(0,0,0,0);
    let filtered = _analysisEvents;
    if (type === 'overdue') {
        filtered = _analysisEvents.filter(e => e.status_deadline && new Date(e.status_deadline) < today && !CLOSED_STATUSES.includes(e.status));
    } else if (type === 'critical') {
        filtered = _analysisEvents.filter(e => e.urgency === 'קריטית');
    } else if (type === 'inprogress') {
        filtered = _analysisEvents.filter(e => e.status === 'בטיפול' || e.status === 'אירוע חדש');
    }
    renderUserChart(filtered); // re-draw the chart with the filtered subset
}

function closeAnalysisModal() {
    document.getElementById('analysisModal').classList.remove('active');
}

// ============= UTILITY FUNCTIONS =============

function formatDate(dateString) {
    // converts a YYYY-MM-DD date string to Israeli DD/MM/YYYY format — returns '-' if empty
    if (!dateString) return '-';
    const date = new Date(dateString.replace(' ', 'T')); // replace space with T to fix Safari parsing bug
    return isNaN(date) ? dateString : date.toLocaleDateString('he-IL');
}

function formatDateTime(dateString) {
    // converts a datetime string to Israeli locale date+time format — returns '-' if empty
    if (!dateString) return '-';
    const date = new Date(dateString.replace(' ', 'T'));
    return isNaN(date) ? dateString : date.toLocaleString('he-IL');
}