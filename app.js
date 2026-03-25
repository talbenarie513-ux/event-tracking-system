// ============================================================
// app.js — Frontend logic for the Event Management System
// This file handles ALL user interactions, API calls, and UI updates.
// It is loaded by index.html and runs entirely in the browser.
// There is no framework (no React/Vue) — plain vanilla JavaScript.
// ============================================================

// ── GLOBAL CONFIGURATION & STATE ────────────────────────────────────────────

// Base URL for all API calls. In multi-user mode, change this to the
// server's actual IP address (e.g. 'http://192.168.1.100:5000/api').
const API_URL = 'http://localhost:5000/api';

// Currently logged-in user — set when user picks from the dropdown.
// null means nobody is logged in (read-only mode).
let currentUser = null;

// Role of the logged-in user: 'admin' | 'planning' | 'development' | null
let currentUserRole = null;

// Database ID of the logged-in user — used for permission lookups.
let currentUserId = null;

// Master list of all events currently loaded from the server.
// Filters and sorts operate on this array in-memory.
let allEvents = [];

// ID of the event currently open in the detail/edit modal.
// null when no modal is open.
let currentEventId = null;

// Permission map for the logged-in user: { fieldId: 0 | 1 }
// 1 = can edit, 0 = read-only. Populated by loadPermissions().
let userPermissions = {};

// Active column filters: { columnName: [allowedValue1, allowedValue2] }
// Empty object means no filters active.
let columnFilters = {};

// Currently active sort option (matches the <select> value in the toolbar).
// Empty string means no sort applied.
let currentSort = '';

// Stores Chart.js chart instances by canvas ID so we can destroy them
// before re-rendering to prevent memory leaks.
let analysisCharts = {};

// Statuses that mean an event is "closed" — used to exclude events from
// overdue checks and the default visible list.
const CLOSED_STATUSES = ['הושלם הטיפול', 'טופל חלקית', 'בהקפאה'];

// ── CACHE BUSTING ────────────────────────────────────────────────────────────

/**
 * Wrapper around fetch() that appends a timestamp query param and sets
 * no-cache headers on every request.
 * This prevents the browser from returning stale cached responses.
 *
 * @param {string} url - The URL to fetch.
 * @param {object} options - Standard fetch() options object.
 * @returns {Promise<Response>}
 */
function fetchNoCache(url, options = {}) {
    const timestamp = new Date().getTime();
    // append _t=... to the URL — unique every call, so the browser sees a "new" URL
    const separator = url.includes('?') ? '&' : '?';
    const nocacheUrl = `${url}${separator}_t=${timestamp}`;
    const headers = options.headers || {};
    // these three headers tell both browser and any proxy not to cache
    headers['Cache-Control'] = 'no-cache, no-store, must-revalidate';
    headers['Pragma'] = 'no-cache';
    headers['Expires'] = '0';
    return fetch(nocacheUrl, { ...options, headers });
}

// ── INITIALISATION ───────────────────────────────────────────────────────────

/**
 * Runs once when the DOM is fully loaded.
 * Sets up all event listeners and performs the initial data load.
 * Using DOMContentLoaded instead of window.onload ensures we don't
 * wait for images/iframes to finish loading.
 */
document.addEventListener('DOMContentLoaded', function() {
    loadUsers();          // populate the user dropdown in the header
    setTodayDate();       // pre-fill the registration date field with today
    loadEventsReadOnly(); // show events without requiring a login (read-only mode)

    // User dropdown — switching user triggers login logic
    document.getElementById('userSelect').addEventListener('change', handleUserLogin);
    // Search box — filter events on every keystroke
    document.getElementById('searchBox').addEventListener('input', filterEvents);
    // Event form — intercept submit to use our AJAX handler instead of a page reload
    document.getElementById('eventForm').addEventListener('submit', handleEventSubmit);
    // Add-user form — same pattern, prevent default form submission
    document.getElementById('addUserForm').addEventListener('submit', handleAddUser);

    // Show/hide the "completion date" field based on status selection.
    // Only visible when status is "הושלם הטיפול" (treatment completed).
    document.getElementById('status').addEventListener('change', function() {
        const completionDateGroup = document.getElementById('completionDateGroup');
        const completionDate = document.getElementById('completionDate');
        if (this.value === 'הושלם הטיפול') {
            completionDateGroup.style.display = 'block';
            // default completion date to today if not already set
            if (!completionDate.value) completionDate.value = new Date().toISOString().split('T')[0];
        } else {
            completionDateGroup.style.display = 'none';
            completionDate.value = '';
        }
    });

    setupColumnFilters(); // attach click listeners to the ▼ filter icons in table headers

    // Close any open modal when the user clicks the dark overlay behind it.
    // e.target === modal checks that the click was on the backdrop, not inside the modal box.
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) closeAllModals();
        });
    });

    // inject the duplicate-ID toast element once into the document body
    _injectIdToast();
});

/**
 * Closes every modal at once.
 * Called when the user clicks outside a modal or presses a close button
 * that should dismiss all open dialogs.
 */
function closeAllModals() {
    closeEventModal();
    closeDetailModal();
    closeAdminModal();
    closeAnalysisModal();
    closeHistoryModal();
    closeHelpModal();
    closeFilePreviewModal();
}

// ── DUPLICATE-ID TOAST ────────────────────────────────────────────────────────

/**
 * Creates the toast element once and appends it to the body.
 * The toast is a small, styled popup that appears near the event ID input
 * whenever the user types an ID that already exists in the database.
 * It is completely separate from the modal system and does not block the UI.
 */
function _injectIdToast() {
    if (document.getElementById('idDuplicateToast')) return; // already injected
    const toast = document.createElement('div');
    toast.id = 'idDuplicateToast';
    toast.innerHTML = `
        <span style="font-size:18px;line-height:1;">⚠️</span>
        <div style="flex:1;">
            <div style="font-weight:700;font-size:13px;margin-bottom:2px;">מספר אירוע תפוס</div>
            <div id="idDuplicateToastMsg" style="font-size:12px;opacity:0.9;"></div>
        </div>
        <button onclick="_hideIdToast()" style="
            background:none;border:none;color:inherit;font-size:18px;
            cursor:pointer;padding:0 0 0 4px;line-height:1;opacity:0.7;
        ">×</button>
    `;
    Object.assign(toast.style, {
        display:         'none',
        position:        'fixed',
        zIndex:          '9999',
        background:      'linear-gradient(135deg,#f56565,#c53030)',
        color:           '#fff',
        borderRadius:    '10px',
        boxShadow:       '0 6px 24px rgba(197,48,48,0.45)',
        padding:         '12px 16px',
        maxWidth:        '320px',
        minWidth:        '220px',
        flexDirection:   'row',
        alignItems:      'flex-start',
        gap:             '10px',
        fontSize:        '13px',
        pointerEvents:   'auto',
        transition:      'opacity 0.25s ease, transform 0.25s ease',
        opacity:         '0',
        transform:       'translateY(-8px)',
    });
    document.body.appendChild(toast);
}

/**
 * Positions the toast just below the eventIdInput field and fades it in.
 * @param {number} id - The duplicate event ID that was typed.
 */
function _showIdToast(id) {
    const toast = document.getElementById('idDuplicateToast');
    const input = document.getElementById('eventIdInput');
    if (!toast || !input) return;

    document.getElementById('idDuplicateToastMsg').textContent =
        `אירוע מספר ${id} כבר קיים במערכת. אנא בחר מספר אחר.`;

    // position below the input field, aligned to its left edge
    const rect = input.getBoundingClientRect();
    toast.style.top  = (rect.bottom + window.scrollY + 8) + 'px';
    toast.style.left = Math.max(8, rect.left + window.scrollX) + 'px';

    toast.style.display = 'flex';
    // slight delay so the browser paints display:flex before the transition kicks in
    requestAnimationFrame(() => {
        toast.style.opacity   = '1';
        toast.style.transform = 'translateY(0)';
    });
}

/**
 * Fades the toast out and hides it.
 */
function _hideIdToast() {
    const toast = document.getElementById('idDuplicateToast');
    if (!toast) return;
    toast.style.opacity   = '0';
    toast.style.transform = 'translateY(-8px)';
    setTimeout(() => { toast.style.display = 'none'; }, 260);
}

// ── "MY EVENTS" TOGGLE ───────────────────────────────────────────────────────

// Tracks whether the "My Events" filter is currently active.
let myEventsActive = false;

/**
 * Toggles between showing all events and showing only the current user's
 * events (where responsible_person === currentUser).
 * Flips the button text and colour as a visual indicator.
 */
function toggleMyEvents() {
    const btn = document.getElementById('myEventsBtn');
    myEventsActive = !myEventsActive;
    if (myEventsActive) {
        // filter allEvents down to those where this user is responsible
        const myEvents = allEvents.filter(e =>
            e.responsible_person && e.responsible_person === currentUser
        );
        btn.textContent = '✖ כל האירועים'; // clicking again will clear the filter
        btn.style.background = '#e53e3e';   // red = filter active
        displayEvents(myEvents);
    } else {
        btn.textContent = '📋 האירועים שלי';
        btn.style.background = ''; // reset to CSS default
        displayEvents(allEvents);  // show all events again
    }
}

// ── HELP MODAL ───────────────────────────────────────────────────────────────

/** Opens the help/guide modal. */
function showHelpModal() { document.getElementById('helpModal').classList.add('active'); }
/** Closes the help/guide modal. */
function closeHelpModal() { document.getElementById('helpModal').classList.remove('active'); }

// ── FILE PREVIEW MODAL ───────────────────────────────────────────────────────

/**
 * Fetches preview data for a file from the server and renders it inside
 * the file preview modal. Supports PDF, images, plain text, CSV/Excel
 * (rendered as HTML tables), and .docx Word documents.
 *
 * The server endpoint (/api/files/<id>/view) returns a JSON object with:
 *   - previewable: boolean
 *   - preview_type: 'base64' | 'text' | 'html_table' | 'html_doc'
 *   - filename, mime_type, data / content / html (depending on type)
 *
 * @param {number} fileId - The database ID of the file to preview.
 */
async function openFile(fileId) {
    try {
        const res = await fetchNoCache(`${API_URL}/files/${fileId}/view`);

        if (!res.ok) {
            // server returned an error — offer to download instead
            const err = await res.json().catch(() => ({ error: `שגיאת שרת ${res.status}` }));
            if (confirm(`שגיאה בפתיחת הקובץ:\n${err.error}\n\nהאם להוריד את הקובץ במקום?`)) {
                downloadFile(fileId);
            }
            return;
        }

        const data = await res.json();

        if (!data.previewable) {
            // server says this file type cannot be previewed (e.g. old .doc files)
            const reason = data.reason === 'doc_old'
                ? 'קבצי .doc ישנים אינם נתמכים לתצוגה מקדימה.\nניתן להמיר ל-.docx ולהעלות מחדש.'
                : 'סוג קובץ זה אינו נתמך לתצוגה מקדימה.';
            if (confirm(`${reason}\n\nהאם להוריד את הקובץ?`)) {
                downloadFile(fileId);
            }
            return;
        }

        // grab modal elements
        const modal = document.getElementById('filePreviewModal');
        const title = document.getElementById('filePreviewTitle');
        const body  = document.getElementById('filePreviewBody');
        const dlBtn = document.getElementById('filePreviewDownloadBtn');

        title.textContent = data.filename;
        dlBtn.onclick = () => downloadFile(fileId); // wire download button to this specific file
        body.innerHTML = '';

        // render the correct preview type
        switch (data.preview_type) {
            case 'base64': {
                // PDF or image — convert base64 back to a data URI and embed
                const src = `data:${data.mime_type};base64,${data.data}`;
                if (data.mime_type === 'application/pdf') {
                    // <iframe> gives the browser's native PDF viewer
                    body.innerHTML = `<iframe src="${src}" style="width:100%;height:75vh;border:none;border-radius:8px;"></iframe>`;
                } else {
                    // image — constrain to modal size
                    body.innerHTML = `<img src="${src}" style="max-width:100%;max-height:75vh;display:block;margin:auto;border-radius:8px;object-fit:contain;">`;
                }
                break;
            }
            case 'text': {
                // plain text — wrap in <pre> to preserve whitespace/newlines
                body.innerHTML =
                    `<pre style="white-space:pre-wrap;word-break:break-word;font-size:14px;line-height:1.6;padding:10px;background:#f7fafc;border-radius:8px;max-height:75vh;overflow-y:auto;direction:ltr;text-align:left;">`
                    + escapeHtml(data.content) + `</pre>`;
                break;
            }
            case 'html_table': {
                // CSV or Excel — server already converted to an HTML table string
                body.innerHTML = `<div style="max-height:75vh;overflow:auto;border-radius:8px;">` + data.html + `</div>`;
                break;
            }
            case 'html_doc': {
                // .docx Word document — server already converted paragraphs/tables to HTML
                body.innerHTML =
                    `<div style="max-height:75vh;overflow-y:auto;padding:20px;background:#fff;border-radius:8px;border:1px solid #e2e8f0;">`
                    + data.html + `</div>`;
                break;
            }
            default:
                body.innerHTML = `<p style="color:#999;text-align:center;">אין תצוגה מקדימה זמינה</p>`;
        }

        modal.classList.add('active'); // show the modal

    } catch (err) {
        console.error('Error opening file:', err);
        if (confirm(`שגיאה בפתיחת הקובץ: ${err.message}\n\nהאם להוריד את הקובץ במקום?`)) {
            downloadFile(fileId);
        }
    }
}

/**
 * Escapes HTML special characters in a string.
 * Used before inserting untrusted content into innerHTML to prevent XSS.
 * @param {string} str - Raw string that may contain HTML characters.
 * @returns {string} Safe string with &, <, >, " replaced by their HTML entities.
 */
function escapeHtml(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ── EVENT ID EXISTENCE CHECK ──────────────────────────────────────────────────

/**
 * Called on every input event on the eventIdInput field.
 * Checks whether the typed ID already exists in the database by attempting
 * to fetch /api/events/<id>.  If the server returns a 200 (event found),
 * shows a small toast popup warning and disables the submit button so the
 * user cannot accidentally overwrite data.
 * If the ID is free (404) or the field is empty, hides the toast and
 * re-enables the submit button.
 *
 * Uses a small debounce (300 ms) so we don't fire a request on every
 * single keystroke — only after the user pauses typing.
 *
 * @param {string} value - The current raw string value of the input field.
 */
let _idCheckTimer = null; // stores the debounce timer ID between calls

async function checkEventIdExists(value) {
    const submitBtn = document.querySelector('#eventForm button[type="submit"]');

    // clear any pending debounce timer so rapid keystrokes only trigger one request
    clearTimeout(_idCheckTimer);

    // if the field is empty there is nothing to check — hide any previous warning
    if (!value || value === '') {
        _hideIdToast();
        if (submitBtn) submitBtn.disabled = false;
        return;
    }

    const id = parseInt(value);
    // guard: skip non-positive values (sanitised by oninput already, but be safe)
    if (isNaN(id) || id < 1) {
        _hideIdToast();
        if (submitBtn) submitBtn.disabled = false;
        return;
    }

    // debounce — wait 300 ms after the user stops typing before hitting the API
    _idCheckTimer = setTimeout(async () => {
        try {
            const res = await fetchNoCache(`${API_URL}/events/${id}`);
            if (res.ok) {
                // 200 → event with this ID already exists → show toast, block submit
                _showIdToast(id);
                if (submitBtn) submitBtn.disabled = true;
            } else {
                // 404 or other error → ID is free → hide toast, allow submit
                _hideIdToast();
                if (submitBtn) submitBtn.disabled = false;
            }
        } catch (err) {
            // network error — fail silently, don't block the user
            _hideIdToast();
            if (submitBtn) submitBtn.disabled = false;
        }
    }, 300);
}

/**
 * Hides the file preview modal and clears its content so the next
 * file starts with a blank slate.
 */
function closeFilePreviewModal() {
    const modal = document.getElementById('filePreviewModal');
    modal.classList.remove('active');
    document.getElementById('filePreviewBody').innerHTML = '';
}

// ── USER MANAGEMENT ──────────────────────────────────────────────────────────

// In-memory cache of all users — avoids re-fetching the user list every time
// we need to populate a dropdown.
let allUsers = [];

/**
 * Fetches all users from the server and populates the login dropdown.
 * Each <option> stores the user's role and DB id as data attributes so
 * handleUserLogin() can read them without another API call.
 */
async function loadUsers() {
    try {
        const response = await fetchNoCache(`${API_URL}/users`);
        allUsers = await response.json();
        const userSelect = document.getElementById('userSelect');
        userSelect.innerHTML = '<option value="">בחר משתמש...</option>'; // reset before repopulating
        allUsers.forEach(user => {
            const option = document.createElement('option');
            option.value = user.name;
            option.dataset.role = user.role; // stored so handleUserLogin can read it synchronously
            option.dataset.id   = user.id;
            option.textContent  = `${user.name} (${getRoleLabel(user.role)})`;
            userSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

/**
 * Fires when the user selects a name from the login dropdown.
 * Sets all global auth state and shows/hides UI elements based on role.
 * If the user clears the selection, resets to anonymous read-only mode.
 */
async function handleUserLogin() {
    const userSelect = document.getElementById('userSelect');
    const selectedOption = userSelect.options[userSelect.selectedIndex];

    if (selectedOption.value) {
        // store globally so every other function can check who is logged in
        currentUser     = selectedOption.value;
        currentUserRole = selectedOption.dataset.role;
        currentUserId   = parseInt(selectedOption.dataset.id);

        // admin-only buttons
        if (currentUserRole === 'admin') {
            document.getElementById('adminBtn').classList.remove('hidden');
            document.getElementById('analysisBtn').classList.remove('hidden');
        } else {
            document.getElementById('adminBtn').classList.add('hidden');
            document.getElementById('analysisBtn').classList.add('hidden');
        }
        document.getElementById('myEventsBtn').classList.remove('hidden');

        // load field-level permissions for this specific user
        await loadPermissions(currentUserId, currentUserRole);
        updateNewEventButton(); // development role can't create events
        loadEvents();           // reload events respecting any show-completed toggle
        loadStats();            // update the stat cards

    } else {
        // user cleared the selection — back to anonymous read-only
        currentUser     = null;
        currentUserRole = null;
        currentUserId   = null;
        userPermissions = {};
        document.getElementById('adminBtn').classList.add('hidden');
        document.getElementById('analysisBtn').classList.add('hidden');
        document.getElementById('newEventBtn').classList.add('hidden');
        document.getElementById('myEventsBtn').classList.add('hidden');
        loadEventsReadOnly(); // re-load without login context
    }
}

/**
 * Shows or hides the "New Event" button depending on the user's role.
 * Development role users are not allowed to create events.
 */
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

/**
 * Loads the field-level edit permissions for the logged-in user.
 * Admins always get full access (all fields set to 1) without an API call.
 * For other roles, fetches the per-user permission map from the server.
 * Result is stored in the global `userPermissions` object and then applied
 * by applyFieldRestrictions() when a form is opened.
 *
 * @param {number} userId - The DB id of the user.
 * @param {string} role   - 'admin' | 'planning' | 'development'
 */
async function loadPermissions(userId, role) {
    if (role === 'admin') {
        // admins have unrestricted access — build a full-access map from known field IDs
        const allFields = [
            'registrationDate', 'firstContactDate', 'system', 'systemOther',
            'eventSummary', 'eventDetails', 'affectedCustomers',
            'urgency', 'priority', 'status', 'statusDetails',
            'eventClassification', 'statusDeadline', 'completionDate',
            'responsiblePerson', 'responsiblePersonOther',
            'priceQuote', 'additionalNotes',
        ];
        userPermissions = {};
        allFields.forEach(f => { userPermissions[f] = 1; });
        return;
    }
    try {
        const response = await fetchNoCache(`${API_URL}/user-permissions/${userId}`);
        const data = await response.json();
        userPermissions = data.permissions || {};
    } catch (error) {
        console.error('Error loading user permissions:', error);
        userPermissions = {}; // default to no permissions on error (safer than full access)
    }
}

/**
 * Converts an internal role key to a display label in Hebrew.
 * @param {string} role - 'admin' | 'planning' | 'development'
 * @returns {string} Hebrew label.
 */
function getRoleLabel(role) {
    const roles = { 'admin': 'אדמין', 'planning': 'תכנון', 'development': 'פיתוח' };
    return roles[role] || role; // fall back to the raw key if unknown
}

// ── COLUMN FILTERS ───────────────────────────────────────────────────────────

/**
 * Attaches click handlers to every element with class "column-filter"
 * (the ▼ icons in table column headers).
 * Also registers a document-level click handler to close any open filter
 * dropdown when the user clicks elsewhere.
 */
function setupColumnFilters() {
    document.querySelectorAll('.column-filter').forEach(filter => {
        filter.addEventListener('click', function(e) {
            e.stopPropagation(); // don't let the click bubble up to the document handler below
            toggleColumnFilter(this.dataset.column, this);
        });
    });
    // clicking anywhere outside a dropdown should close it
    document.addEventListener('click', function() {
        document.querySelectorAll('.filter-dropdown').forEach(d => d.remove());
    });
}

/**
 * Builds and positions a filter dropdown for a specific column.
 * The dropdown lists every unique value in that column and lets the user
 * check/uncheck values to include in the filter.
 *
 * @param {string} column  - The event object key to filter on (e.g. 'status').
 * @param {Element} element - The ▼ icon element — used to position the dropdown below it.
 */
function toggleColumnFilter(column, element) {
    document.querySelectorAll('.filter-dropdown').forEach(d => d.remove()); // close any existing dropdown first

    // collect every distinct non-empty value in this column from the current data
    const uniqueValues = [...new Set(allEvents.map(e => e[column]))].filter(v => v);
    if (uniqueValues.length === 0) return; // nothing to filter by

    const dropdown = document.createElement('div');
    dropdown.className = 'filter-dropdown';
    dropdown.style.position = 'fixed'; // fixed so it doesn't scroll away with the table

    // position the dropdown just below the filter icon
    const rect = element.getBoundingClientRect();
    dropdown.style.top = (rect.bottom + 5) + 'px';

    // prevent the dropdown from overflowing off the right edge of the viewport
    const dropdownWidth = 180;
    let leftPos = rect.left;
    if (leftPos + dropdownWidth > window.innerWidth - 5) leftPos = window.innerWidth - dropdownWidth - 5;
    if (leftPos < 5) leftPos = 5;
    dropdown.style.left = leftPos + 'px';

    // "Show all" option — clears the filter for this column
    const clearOption = document.createElement('label');
    clearOption.innerHTML = `<input type="checkbox" ${!columnFilters[column] ? 'checked' : ''} onchange="clearColumnFilter('${column}')"><strong>הצג הכל</strong>`;
    dropdown.appendChild(clearOption);

    // one checkbox per unique value
    uniqueValues.forEach(value => {
        const label = document.createElement('label');
        // pre-check the box if this value is currently included in the filter (or no filter is set)
        const isChecked = !columnFilters[column] || columnFilters[column].includes(value);
        label.innerHTML = `<input type="checkbox" ${isChecked ? 'checked' : ''} onchange="updateColumnFilter('${column}', '${value}', this.checked)">${value}`;
        dropdown.appendChild(label);
    });

    document.body.appendChild(dropdown);
    dropdown.addEventListener('click', e => e.stopPropagation()); // keep clicks inside from closing it
}

/**
 * Adds or removes a value from the active filter for a column,
 * then re-runs filterEvents() to refresh the table.
 *
 * @param {string}  column  - The column being filtered.
 * @param {string}  value   - The specific value being toggled.
 * @param {boolean} checked - True = include this value, false = exclude it.
 */
function updateColumnFilter(column, value, checked) {
    if (!columnFilters[column]) columnFilters[column] = [];
    if (checked) {
        if (!columnFilters[column].includes(value)) columnFilters[column].push(value);
    } else {
        columnFilters[column] = columnFilters[column].filter(v => v !== value);
    }
    filterEvents();
}

/**
 * Removes the filter for a specific column entirely (shows all values).
 * @param {string} column - The column whose filter should be cleared.
 */
function clearColumnFilter(column) {
    delete columnFilters[column];
    filterEvents();
    document.querySelectorAll('.filter-dropdown').forEach(d => d.remove());
}

// ── STAT CARD FILTERING ──────────────────────────────────────────────────────

/**
 * Filters the event table to match the clicked stat card.
 * Clicking the same card a second time toggles the filter off.
 * Cards: 'total' | 'overdue' | 'critical' | 'inprogress'
 *
 * @param {string} type - Which stat card was clicked.
 */
function filterByStat(type) {
    const cards = document.querySelectorAll('.stat-card');
    // check if the same card is already active (toggle off)
    const isActive = document.querySelector(`.stat-card.active-filter[data-stat="${type}"]`);
    cards.forEach(c => { c.classList.remove('active-filter'); c.removeAttribute('data-stat'); });
    if (isActive) { displayEvents(allEvents); return; } // toggle off — show all

    // activate the clicked card visually
    const idx = ['total', 'overdue', 'critical', 'inprogress'];
    cards[idx.indexOf(type)].classList.add('active-filter');
    cards[idx.indexOf(type)].setAttribute('data-stat', type);

    const today = new Date(); today.setHours(0, 0, 0, 0);
    let filtered;
    switch(type) {
        case 'total':
            // exclude completed and frozen — these don't count as "active"
            filtered = allEvents.filter(e => e.status !== 'הושלם הטיפול' && e.status !== 'בהקפאה'); break;
        case 'overdue':
            // deadline is in the past and event is not closed
            filtered = allEvents.filter(e =>
                new Date(e.status_deadline) < today && !CLOSED_STATUSES.includes(e.status)); break;
        case 'critical':
            filtered = allEvents.filter(e => e.urgency === 'קריטית'); break;
        case 'inprogress':
            // "in progress" excludes both closed statuses and "new event" / "frozen"
            filtered = allEvents.filter(e => !['בהקפאה','הושלם הטיפול','טופל חלקית','אירוע חדש'].includes(e.status)); break;
        default:
            filtered = allEvents;
    }
    displayEvents(filtered);
}

/**
 * Filters the table to show only events with a specific status.
 * Used by clicking status labels in the detail view or elsewhere.
 * @param {string} status - The status value to filter by.
 */
function filterByStatus(status) {
    columnFilters = { status: [status] };
    filterEvents();
}

// ── SEARCH & FILTER ──────────────────────────────────────────────────────────

/**
 * Combines the text search box and active column filters to produce
 * a filtered subset of allEvents, then renders the result.
 * Called on every keystroke in the search box and on every filter change.
 */
function filterEvents() {
    const searchTerm = document.getElementById('searchBox').value.toLowerCase();
    let filtered = allEvents.filter(event => {
        // search matches if any of these fields contains the search term
        const matchesSearch = !searchTerm ||
            (event.event_summary || '').toLowerCase().includes(searchTerm) ||
            (event.system || '').toLowerCase().includes(searchTerm) ||
            (event.event_details || '').toLowerCase().includes(searchTerm) ||
            (event.affected_customers || '').toLowerCase().includes(searchTerm);

        // each active column filter must be satisfied (AND logic between columns)
        let matchesFilters = true;
        for (const [column, values] of Object.entries(columnFilters)) {
            if (values.length > 0 && !values.includes(event[column])) {
                matchesFilters = false;
                break;
            }
        }
        return matchesSearch && matchesFilters;
    });
    displayEvents(filtered);
}

/**
 * Sorts allEvents in-place based on the sort dropdown selection,
 * then re-runs filterEvents() so the sorted result respects active filters.
 */
function sortEvents() {
    const sortValue = document.getElementById('sortSelect').value;
    if (!sortValue) { filterEvents(); return; } // no sort selected — just re-filter
    let sorted = [...allEvents]; // clone to avoid mutating allEvents before the sort comparison
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
    allEvents = sorted; // replace allEvents with the sorted version
    filterEvents();     // re-apply search + column filters on top of the new sort order
}

// ── SHOW COMPLETED / DELETED TOGGLES ─────────────────────────────────────────

// rawEvents holds the full unfiltered server response.
// allEvents is derived from it by applyCompletedFilter() or showAllEvents().
let rawEvents = [];

/**
 * Called when the "show completed events" checkbox changes.
 * Delegates to applyCompletedFilter() unless "show deleted" is also checked
 * (the two modes are mutually exclusive).
 */
function toggleCompleted() {
    if (document.getElementById('showDeleted').checked) return; // deleted mode takes priority
    applyCompletedFilter();
}

/**
 * Rebuilds allEvents from rawEvents based on the show-completed checkbox state,
 * then re-renders the table.
 * - Unchecked (default): show only active events (exclude 'הושלם הטיפול' and 'בהקפאה').
 * - Checked: show only completed events.
 */
function applyCompletedFilter() {
    const showCompleted = document.getElementById('showCompleted').checked;
    columnFilters = {}; // reset column filters whenever the completion toggle changes
    if (showCompleted) {
        allEvents = rawEvents.filter(e => e.id > 0 && e.status === 'הושלם הטיפול');
    } else {
        allEvents = rawEvents.filter(e => e.id > 0 && e.status !== 'הושלם הטיפול' && e.status !== 'בהקפאה');
    }
    displayEvents(allEvents);
}

/**
 * Resets all filters and shows every event (active, completed, frozen).
 * Unchecks both the completed and deleted checkboxes.
 */
function showAllEvents() {
    document.getElementById('showCompleted').checked = false;
    document.getElementById('showDeleted').checked = false;
    document.getElementById('showCompleted').disabled = false;
    document.getElementById('deletedBanner').classList.remove('active');
    columnFilters = {};
    allEvents = rawEvents; // show everything including completed/frozen
    displayEvents(allEvents);
}

/**
 * Called when the "show recently deleted events" checkbox changes.
 * In deleted mode:
 *  - The "show completed" checkbox is disabled (modes are mutually exclusive).
 *  - A warning banner is shown.
 *  - Calls loadDeletedEvents() which fetches soft-deleted records.
 * When unchecked, restores normal event loading.
 */
function toggleDeleted() {
    const showDeleted = document.getElementById('showDeleted').checked;
    const showCompleted = document.getElementById('showCompleted');
    const banner = document.getElementById('deletedBanner');
    if (showDeleted) {
        showCompleted.disabled = true; // can't mix deleted + completed views
        banner.classList.add('active');
        loadDeletedEvents();
    } else {
        showCompleted.disabled = false;
        banner.classList.remove('active');
        loadEvents(); // return to normal event list
    }
}

/**
 * Fetches all soft-deleted events (is_deleted = 1) and renders them
 * with a restore button instead of the normal edit/delete actions.
 */
async function loadDeletedEvents() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.classList.remove('hidden');
    try {
        // ?show_deleted=true tells the server to include is_deleted=1 rows
        const response = await fetchNoCache(`${API_URL}/events?show_deleted=true`);
        const allFetched = await response.json();
        // filter client-side to only show actually-deleted ones (server returns all)
        const deleted = allFetched.filter(e => e.id > 0 && e.is_deleted === 1);
        displayDeletedEvents(deleted);
    } catch (error) {
        console.error('Error loading deleted events:', error);
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

/**
 * Renders a list of deleted events into the table.
 * Each row shows a ♻️ restore button instead of edit/delete.
 * @param {Array} events - Array of soft-deleted event objects.
 */
function displayDeletedEvents(events) {
    const tbody = document.getElementById('eventsTableBody');
    tbody.innerHTML = '';
    if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; color:#999;">אין אירועים שנמחקו לאחרונה</td></tr>';
        return;
    }
    events.forEach(event => {
        const row = document.createElement('tr');
        row.style.opacity = '0.6';       // visually dim deleted rows
        row.style.background = '#f9f9f9';

        let urgencyClass = 'urgency-low';
        if (event.urgency === 'קריטית') urgencyClass = 'urgency-critical';
        else if (event.urgency === 'גבוהה') urgencyClass = 'urgency-high';
        else if (event.urgency === 'בינונית') urgencyClass = 'urgency-medium';

        const eventId = event.id;
        row.innerHTML = `
            <td>${event.id}</td>
            <td>${formatDate(event.registration_date)}</td>
            <td>${event.system || ''}</td>
            <td class="col-summary">${event.event_summary || ''}</td>
            <td>${event.affected_customers || ''}</td>
            <td><span class="urgency-badge ${urgencyClass}">${event.urgency || ''}</span></td>
            <td>${event.priority || ''}</td>
            <td><span style="color:#999;">${event.status || ''} 🗑️</span></td>
            <td>${formatDate(event.status_deadline)}</td>
            <td>${event.responsible_person || '-'}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-restore" onclick="restoreEvent(${eventId})">♻️ שחזר</button>
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });
}

/**
 * Sends a PUT request to restore a soft-deleted event (sets is_deleted = 0).
 * Reloads the deleted events list and stat cards on success.
 * @param {number} eventId - The ID of the event to restore.
 */
async function restoreEvent(eventId) {
    if (!confirm('האם לשחזר אירוע זה?')) return;
    try {
        const response = await fetch(`${API_URL}/events/${eventId}/restore`, { method: 'PUT' });
        const result = await response.json();
        if (result.success) {
            alert('האירוע שוחזר בהצלחה');
            loadDeletedEvents(); // refresh the deleted list
            loadStats();         // update stat cards (active count changes)
        } else {
            alert('שגיאה: ' + result.error);
        }
    } catch (error) {
        console.error('Error restoring event:', error);
        alert('שגיאה בשחזור האירוע');
    }
}

// ── EVENT LOADING ─────────────────────────────────────────────────────────────

/**
 * Loads events from the server without requiring a login.
 * Used for the initial read-only view when the page first loads.
 * Also loads stats for the four summary cards.
 * Does NOT respect the show-completed toggle (always hides completed).
 */
async function loadEventsReadOnly() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.classList.remove('hidden');
    try {
        const response = await fetchNoCache(`${API_URL}/events`);
        rawEvents = (await response.json()).filter(e => e.id > 0); // guard against any id=0 sentinel rows
        // default view: hide completed events
        allEvents = rawEvents.filter(e => e.status !== 'הושלם הטיפול');
        displayEvents(allEvents);
        // also fetch stats separately (stats endpoint is cheaper than recalculating client-side)
        const statsResponse = await fetchNoCache(`${API_URL}/stats`);
        const stats = await statsResponse.json();
        document.getElementById('totalEvents').textContent     = stats.total_events || 0;
        document.getElementById('overdueEvents').textContent   = stats.overdue || 0;
        document.getElementById('criticalEvents').textContent  = stats.critical || 0;
        // "in progress" = all active statuses that are not frozen/new/completed
        document.getElementById('inProgressEvents').textContent = Object.entries(stats.by_status)
            .filter(([s]) => !['בהקפאה','הושלם הטיפול','טופל חלקית','אירוע חדש'].includes(s))
            .reduce((a,[,v]) => a+v, 0);
    } catch (error) {
        console.error('Error loading events:', error);
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

/**
 * Loads events when a user is logged in.
 * Stores the full server response in rawEvents, then applies the
 * show-completed toggle via applyCompletedFilter().
 */
async function loadEvents() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.classList.remove('hidden');
    try {
        const response = await fetchNoCache(`${API_URL}/events`);
        rawEvents = (await response.json()).filter(e => e.id > 0);
        applyCompletedFilter(); // honour whatever the checkbox says
    } catch (error) {
        console.error('Error loading events:', error);
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

// ── DISPLAY EVENTS ────────────────────────────────────────────────────────────

/**
 * Renders an array of events as rows in the main table.
 * Each row gets an onclick to open the detail modal.
 * Overdue rows get a red CSS class.
 * Action buttons (edit/delete) are only shown to logged-in non-development users.
 *
 * @param {Array} events - The filtered/sorted array of event objects to render.
 */
function displayEvents(events) {
    const tbody = document.getElementById('eventsTableBody');
    tbody.innerHTML = '';
    if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align: center;">אין אירועים להצגה</td></tr>';
        return;
    }
    events.forEach(event => {
        const row = document.createElement('tr');
        row.onclick = () => showEventDetail(event.id); // clicking anywhere on the row opens details

        // map urgency to the right CSS badge class
        let urgencyClass = 'urgency-low';
        if (event.urgency === 'קריטית') urgencyClass = 'urgency-critical';
        else if (event.urgency === 'גבוהה') urgencyClass = 'urgency-high';
        else if (event.urgency === 'בינונית') urgencyClass = 'urgency-medium';

        // overdue = deadline is in the past AND status is not closed
        const today = new Date(); today.setHours(0,0,0,0);
        const isOverdue = new Date(event.status_deadline) < today && !CLOSED_STATUSES.includes(event.status);
        if (isOverdue) row.classList.add('row-overdue'); // red background via CSS

        const editId = event.id; // captured in closure for button onclick handlers

        row.innerHTML = `
            <td>${event.id}</td>
            <td>${formatDate(event.registration_date)}</td>
            <td>${event.system || ''}</td>
            <td class="col-summary">${event.event_summary || ''}</td>
            <td>${event.affected_customers || ''}</td>
            <td><span class="urgency-badge ${urgencyClass}">${event.urgency || ''}</span></td>
            <td>${event.priority || ''}</td>
            <td>${event.status || ''}</td>
            <td>${formatDate(event.status_deadline)}</td>
            <td>${event.responsible_person || '-'}</td>
            <td>
                <div class="action-buttons">
                    ${currentUser ? `
                    <button class="btn btn-primary btn-small" onclick="event.stopPropagation(); editEvent(${editId})">✏️</button>
                    ${currentUserRole !== 'development' ? `
                    <button class="btn btn-danger btn-small" onclick="event.stopPropagation(); deleteEvent(${editId})">🗑️</button>
                    ` : ''}
                    ` : ''}
                </div>
            </td>
        `;
        // event.stopPropagation() on the buttons prevents the row's onclick from also firing
        tbody.appendChild(row);
    });
}

// ── EVENT DETAIL MODAL ────────────────────────────────────────────────────────

/**
 * Fetches full event data (including files) and renders it in the detail modal.
 * The detail modal is read-only — editing requires clicking the Edit button inside it.
 * Also triggers loadComments() to populate the comments section.
 *
 * @param {number} eventId - The DB id of the event to display.
 */
async function showEventDetail(eventId) {
    try {
        const response = await fetchNoCache(`${API_URL}/events/${eventId}`);
        if (!response.ok) throw new Error(`שגיאת שרת ${response.status}`);
        const event = await response.json();
        currentEventId = eventId; // save globally so edit/delete buttons in the modal know what to act on

        document.getElementById('detailEventId').textContent = event.id;

        // ── helper: render a value or a styled "—" placeholder ──
        const val = (v) => (v && String(v).trim()) ? v : '<span class="detail-value empty">—</span>';

        // ── urgency badge ──
        const urgencyClass =
            event.urgency === 'קריטית' ? 'urgency-critical' :
            event.urgency === 'גבוהה'  ? 'urgency-high'     :
            event.urgency === 'בינונית' ? 'urgency-medium'   : 'urgency-low';
        const urgencyBadge = event.urgency
            ? `<span class="urgency-badge ${urgencyClass}">${event.urgency}</span>`
            : '<span class="detail-value empty">—</span>';

        // ── status pill ──
        const statusPill = event.status
            ? `<span class="detail-status-pill">${event.status}</span>`
            : '<span class="detail-value empty">—</span>';

        // ── build the file attachments section — show display_name, original_filename as tooltip ──
        let filesHtml = '';
        if (event.files && event.files.length > 0) {
            const fileRows = event.files.map(file => {
                const shownName = file.display_name || file.original_filename;
                return `
                <div class="file-item">
                    <span title="${file.original_filename}">📄 ${shownName}</span>
                    <div style="display:flex;gap:6px;">
                        <button class="btn btn-primary btn-small" onclick="openFile(${file.id})">👁️ פתח</button>
                        <button class="btn btn-primary btn-small" onclick="downloadFile(${file.id})">⬇️ הורד</button>
                    </div>
                </div>`;
            }).join('');
            filesHtml = `
            <div class="detail-section">
                <div class="detail-section-header">📎 קבצים מצורפים (${event.files.length})</div>
                <div style="padding:12px 16px;background:#fff;">${fileRows}</div>
            </div>`;
        }

        // ── inject all event fields into the detail content area ──
        const detailContent = document.getElementById('detailContent');
        detailContent.innerHTML = `

            <!-- ── SECTION 1: Basic Details ── -->
            <div class="detail-section">
                <div class="detail-section-header">📋 פרטים בסיסיים</div>
                <div class="detail-grid">
                    <div class="detail-cell">
                        <div class="detail-label">תאריך רישום</div>
                        <div class="detail-value">${val(formatDate(event.registration_date))}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">תאריך פנייה ראשונה</div>
                        <div class="detail-value">${val(event.first_contact_date ? formatDate(event.first_contact_date) : '')}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">מערכת</div>
                        <div class="detail-value">${val(event.system)}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">לקוחות מושפעים</div>
                        <div class="detail-value">${val(event.affected_customers)}</div>
                    </div>
                </div>
            </div>

            <!-- ── SECTION 2: Event Description ── -->
            <div class="detail-section">
                <div class="detail-section-header">📝 תיאור האירוע</div>
                <div class="detail-grid">
                    <div class="detail-cell detail-cell-full">
                        <div class="detail-label">תמצית</div>
                        <div class="detail-value" style="font-weight:600;">${val(event.event_summary)}</div>
                    </div>
                    <div class="detail-cell detail-cell-full">
                        <div class="detail-label">פירוט</div>
                        <div class="detail-value" style="white-space:pre-wrap;">${val(event.event_details)}</div>
                    </div>
                </div>
            </div>

            <!-- ── SECTION 3: Status & Treatment ── -->
            <div class="detail-section">
                <div class="detail-section-header">⚙️ סטטוס וטיפול</div>
                <div class="detail-grid">
                    <div class="detail-cell">
                        <div class="detail-label">דחיפות</div>
                        <div class="detail-value">${urgencyBadge}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">עדיפות</div>
                        <div class="detail-value">${val(event.priority)}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">סטטוס</div>
                        <div class="detail-value">${statusPill}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">סיווג אירוע</div>
                        <div class="detail-value">${val(event.event_classification)}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">לו"ז</div>
                        <div class="detail-value">${val(formatDate(event.status_deadline))}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">גורם אחראי</div>
                        <div class="detail-value">${val(event.responsible_person)}</div>
                    </div>
                    ${event.completion_date ? `
                    <div class="detail-cell">
                        <div class="detail-label">תאריך השלמה</div>
                        <div class="detail-value">${formatDate(event.completion_date)}</div>
                    </div>
                    <div class="detail-cell"></div>` : ''}
                    ${event.status_details ? `
                    <div class="detail-cell detail-cell-full">
                        <div class="detail-label">פירוט סטטוס</div>
                        <div class="detail-value" style="white-space:pre-wrap;">${event.status_details}</div>
                    </div>` : ''}
                </div>
            </div>

            <!-- ── SECTION 4: Additional Info ── -->
            <div class="detail-section">
                <div class="detail-section-header">💡 מידע נוסף</div>
                <div class="detail-grid">
                    <div class="detail-cell">
                        <div class="detail-label">הצעת מחיר</div>
                        <div class="detail-value">${event.price_quote ? event.price_quote + ' ₪' : '<span class="detail-value empty">—</span>'}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">נוצר על ידי</div>
                        <div class="detail-value">${val(event.created_by)}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">תאריך יצירה</div>
                        <div class="detail-value">${val(formatDateTime(event.created_at))}</div>
                    </div>
                    <div class="detail-cell">
                        <div class="detail-label">עודכן לאחרונה</div>
                        <div class="detail-value">${val(formatDateTime(event.updated_at))}</div>
                    </div>
                    ${event.additional_notes ? `
                    <div class="detail-cell detail-cell-full">
                        <div class="detail-label">הערות נוספות</div>
                        <div class="detail-value" style="white-space:pre-wrap;">${event.additional_notes}</div>
                    </div>` : ''}
                </div>
            </div>

            ${filesHtml}
        `;

        // only show edit/delete buttons in the detail modal if the user has permission
        const canEdit = currentUser && currentUserRole !== 'development';
        document.getElementById('detailEditBtn').classList.toggle('hidden', !canEdit);
        document.getElementById('detailDeleteBtn').classList.toggle('hidden', !canEdit);
        document.getElementById('detailModal').classList.add('active');

        loadComments(eventId); // populate the comments section asynchronously

    } catch (error) {
        console.error('Error loading event details:', error);
        alert('שגיאה בטעינת פרטי האירוע: ' + error.message);
    }
}

/** Closes the event detail modal and clears the current event ID. */
function closeDetailModal() {
    document.getElementById('detailModal').classList.remove('active');
    currentEventId = null;
}

/**
 * Called by the "Edit" button inside the detail modal.
 * Closes the detail view and immediately opens the edit form.
 */
function handleDetailEdit() {
    const id = currentEventId;
    closeDetailModal();
    if (id) editEvent(id);
}

/**
 * Called by the "Delete" button inside the detail modal.
 * Closes the detail view and immediately triggers the delete confirmation.
 */
function handleDetailDelete() {
    const id = currentEventId;
    if (id) { closeDetailModal(); deleteEvent(id); }
}

// ── COMMENTS ─────────────────────────────────────────────────────────────────

/**
 * Fetches and renders comments for the currently open event.
 * Shows the comment input row only if a user is logged in.
 * Each comment gets a delete button if the current user is the author or an admin.
 *
 * @param {number} eventId - The ID of the event whose comments to load.
 */
async function loadComments(eventId) {
    const commentList      = document.getElementById('commentList');
    const commentInputRow  = document.getElementById('commentInputRow');
    const commentLoginMsg  = document.getElementById('commentLoginMsg');

    commentList.innerHTML = '<div class="comment-no-items">טוען הערות...</div>';

    // show input row only to logged-in users
    if (currentUser) {
        commentInputRow.style.display = 'flex';
        commentLoginMsg.style.display = 'none';
    } else {
        commentInputRow.style.display = 'none';
        commentLoginMsg.style.display = 'block';
    }

    try {
        const res = await fetchNoCache(`${API_URL}/events/${eventId}/comments`);
        const comments = await res.json();

        if (!comments || comments.length === 0) {
            commentList.innerHTML = '<div class="comment-no-items">אין הערות עדיין</div>';
            return;
        }

        commentList.innerHTML = comments.map(c => {
            // user can delete their own comments; admins can delete any comment
            const canDelete = currentUser && (currentUser === c.author || currentUserRole === 'admin');
            return `
            <div class="comment-item" id="comment-${c.id}">
                <div class="comment-header">
                    <span class="comment-author">👤 ${escapeHtml(c.author)}</span>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span class="comment-date">${formatDateTime(c.created_at)}</span>
                        ${canDelete ? `<button class="comment-delete" onclick="deleteComment(${c.id})" title="מחק הערה">✕</button>` : ''}
                    </div>
                </div>
                <div class="comment-text">${escapeHtml(c.comment_text)}</div>
            </div>`;
        }).join('');

    } catch (err) {
        console.error('Error loading comments:', err);
        commentList.innerHTML = '<div class="comment-no-items" style="color:#f56565;">שגיאה בטעינת הערות</div>';
    }
}

/**
 * Reads the comment textarea and POSTs a new comment to the server.
 * Clears the textarea and reloads comments on success.
 */
async function submitComment() {
    if (!currentUser) { alert('יש להתחבר כמשתמש תחילה'); return; }
    if (!currentEventId) return;

    const textarea = document.getElementById('commentText');
    const text = (textarea.value || '').trim();
    if (!text) { alert('יש להזין תוכן להערה'); return; }

    try {
        const res = await fetch(`${API_URL}/events/${currentEventId}/comments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comment_text: text, author: currentUser })
        });
        const result = await res.json();
        if (result.success) {
            textarea.value = '';
            loadComments(currentEventId); // refresh the comment list
        } else {
            alert('שגיאה: ' + result.error);
        }
    } catch (err) {
        console.error('Error submitting comment:', err);
        alert('שגיאה בשליחת ההערה');
    }
}

/**
 * Sends a DELETE request for a specific comment.
 * The server checks that the requester is the author or an admin.
 * Reloads comments on success.
 *
 * @param {number} commentId - The DB id of the comment to delete.
 */
async function deleteComment(commentId) {
    if (!confirm('האם למחוק הערה זו?')) return;
    try {
        const res = await fetch(`${API_URL}/comments/${commentId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            // pass requester info so server can check permissions
            body: JSON.stringify({ requester: currentUser, requester_role: currentUserRole })
        });
        const result = await res.json();
        if (result.success) {
            loadComments(currentEventId);
        } else {
            alert('שגיאה: ' + result.error);
        }
    } catch (err) {
        console.error('Error deleting comment:', err);
        alert('שגיאה במחיקת ההערה');
    }
}

// ── HISTORY MODAL ─────────────────────────────────────────────────────────────

/**
 * Fetches the full audit log for the current event and renders it as
 * a visual timeline inside the history modal.
 */
async function showHistoryModal() {
    const eventId = currentEventId;
    if (!eventId) return;

    const modal   = document.getElementById('historyModal');
    const content = document.getElementById('historyContent');
    content.innerHTML = '<div style="text-align:center;padding:30px;color:#667eea;">⏳ טוען היסטוריה...</div>';
    modal.classList.add('active');

    try {
        const response = await fetchNoCache(`${API_URL}/events/${eventId}/history`);
        const data = await response.json();

        const actionLabels = {
            'created':       { icon: '🟢', text: 'אירוע נוצר'       },
            'updated':       { icon: '✏️',  text: 'עדכון שדה'        },
            'deleted':       { icon: '🗑️', text: 'אירוע נמחק'       },
            'restored':      { icon: '♻️', text: 'אירוע שוחזר'      },
            'file_uploaded': { icon: '📎', text: 'קובץ צורף לאירוע'  },
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
                        action:     entry.action,
                        changed_by: entry.changed_by,
                        changed_at: entry.changed_at,
                        fields:     [entry],
                    });
                }
            }
            for (const grp of groups) {
                const lbl = actionLabels[grp.action] || { icon: '🔵', text: grp.action };
                if (grp.action === 'updated' || grp.action === 'file_uploaded') {
                    const nonCommentFields = grp.fields.filter(f => f.field_name !== 'comment');
                    const commentFields    = grp.fields.filter(f => f.field_name === 'comment');

                    if (nonCommentFields.length > 0) {
                        const fieldsHtml = nonCommentFields.map(f => `
                            <div class="history-field-row">
                                <span class="history-field-name">${f.field_label || f.field_name}</span>
                                <span class="history-arrow">←</span>
                                <span class="history-old">${f.old_value || '—'}</span>
                                <span class="history-arrow">→</span>
                                <span class="history-new">${f.new_value || '—'}</span>
                            </div>`).join('');
                        html += `
                        <div class="history-item history-${grp.action}">
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
                    }

                    commentFields.forEach(f => {
                        html += `
                        <div class="history-item history-updated" style="border-right-color:#48bb78;">
                            <div class="history-icon">💬</div>
                            <div class="history-body">
                                <div class="history-action">הערה נוספה</div>
                                <div class="history-fields">
                                    <div class="history-field-row">
                                        <span class="history-new" style="max-width:none;">${f.new_value || '—'}</span>
                                    </div>
                                </div>
                                <div class="history-meta">
                                    <span class="history-user">👤 ${grp.changed_by || '—'}</span>
                                    <span class="history-date">🕐 ${formatDateTime(grp.changed_at)}</span>
                                </div>
                            </div>
                        </div>`;
                    });

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

/** Closes the history modal. */
function closeHistoryModal() {
    document.getElementById('historyModal').classList.remove('active');
}

// ── STATISTICS ────────────────────────────────────────────────────────────────

async function loadStats() {
    try {
        const response = await fetchNoCache(`${API_URL}/stats`);
        const stats = await response.json();
        document.getElementById('totalEvents').textContent    = stats.total_events || 0;
        document.getElementById('overdueEvents').textContent  = stats.overdue || 0;
        document.getElementById('criticalEvents').textContent = stats.critical || 0;
        document.getElementById('inProgressEvents').textContent = Object.entries(stats.by_status)
            .filter(([s]) => !['בהקפאה','הושלם הטיפול','טופל חלקית','אירוע חדש'].includes(s))
            .reduce((a,[,v]) => a+v, 0);
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ── EVENT FORM — NEW & EDIT ───────────────────────────────────────────────────

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
    // make sure any leftover toast from a previous session is hidden
    _hideIdToast();
    document.getElementById('eventModal').classList.add('active');
}

async function editEvent(eventId) {
    if (!currentUser) { alert('יש לבחור משתמש תחילה'); return; }
    try {
        const response = await fetchNoCache(`${API_URL}/events/${eventId}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const event = await response.json();

        document.getElementById('modalTitle').textContent = `עריכת אירוע #${event.id}`;
        document.getElementById('eventId').value      = event.id;
        document.getElementById('eventIdInput').value = event.id;
        document.getElementById('registrationDate').value   = event.registration_date || '';
        document.getElementById('firstContactDate').value   = event.first_contact_date || '';

        const systemSelect = document.getElementById('system');
        const systems = (event.system || '').split(',').map(s => s.trim());
        const standardOptions = ['ספיר', 'שמיר', 'גאודאטה', 'אחר'];
        Array.from(systemSelect.options).forEach(opt => { opt.selected = systems.includes(opt.value); });
        const nonStandard = systems.filter(s => !standardOptions.includes(s) && s !== '');
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

        document.getElementById('eventSummary').value        = event.event_summary || '';
        document.getElementById('eventDetails').value        = event.event_details || '';
        document.getElementById('affectedCustomers').value   = event.affected_customers || '';
        document.getElementById('urgency').value             = event.urgency || '';
        document.getElementById('priority').value            = event.priority || 5;
        document.getElementById('status').value              = event.status || '';
        document.getElementById('statusDetails').value       = event.status_details || '';
        document.getElementById('eventClassification').value = event.event_classification || '';
        document.getElementById('statusDeadline').value      = event.status_deadline || '';
        document.getElementById('completionDate').value      = event.completion_date || '';
        document.getElementById('priceQuote').value          = event.price_quote || '';
        document.getElementById('additionalNotes').value     = event.additional_notes || '';
        document.getElementById('fileNameDisplay').textContent = 'לא נבחרו קבצים';

        document.getElementById('completionDateGroup').style.display =
            event.status === 'הושלם הטיפול' ? 'block' : 'none';

        populateResponsibleDropdown(event.responsible_person || '', () => {
            enableAllFormFields();
            applyFieldRestrictions();
        });
        displayEventFiles(event.files || []);
        // hide any duplicate-ID toast that might be lingering from a previous open
        _hideIdToast();
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

// ── FIELD RESTRICTIONS ────────────────────────────────────────────────────────

function applyFieldRestrictions() {
    if (currentUserRole === 'admin') {
        document.querySelectorAll('#eventForm input, #eventForm select, #eventForm textarea')
            .forEach(input => { input.required = false; input.disabled = false; });
        return;
    }

    document.querySelectorAll('#eventForm input, #eventForm select, #eventForm textarea')
        .forEach(input => {
            if (!input.id) return;
            const perm = userPermissions[input.id];
            if (perm === 0) {
                input.disabled = true;
            }
        });
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
    const input   = document.getElementById('fileInput');
    const display = document.getElementById('fileNameDisplay');
    if (input.files.length === 0) {
        display.textContent = 'לא נבחרו קבצים';
    } else if (input.files.length === 1) {
        display.textContent = input.files[0].name;
    } else {
        display.textContent = `${input.files.length} קבצים נבחרו`;
    }
}

// ── RESPONSIBLE PERSON DROPDOWN ───────────────────────────────────────────────

function toggleResponsibleOther() {
    const select     = document.getElementById('responsiblePerson');
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
    }).catch(err => {
        console.error('Error loading users for dropdown:', err);
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

// ── FORM SUBMISSION ───────────────────────────────────────────────────────────

async function handleEventSubmit(e) {
    e.preventDefault();
    if (!currentUser) { alert('יש לבחור משתמש תחילה'); return; }

    // ── block double-submit ──
    const submitBtn = document.querySelector('#eventForm button[type="submit"]');
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'שומר...'; }

    const eventId = document.getElementById('eventId').value;
    const isEdit  = eventId !== '';

    const systemSelect    = document.getElementById('system');
    const selectedSystems = Array.from(systemSelect.selectedOptions).map(o => o.value);
    const systemOtherValue = document.getElementById('systemOther').value.trim();
    const finalSystems = selectedSystems.map(s => (s === 'אחר' && systemOtherValue) ? systemOtherValue : s);
    const systemValue  = finalSystems.join(', ');

    const responsibleSelect = document.getElementById('responsiblePerson');
    const responsibleOther  = document.getElementById('responsiblePersonOther').value.trim();
    const responsibleValue  = responsibleSelect.value;
    const responsible = responsibleValue === 'אחר' ? responsibleOther : responsibleValue;

    const customEventId = !isEdit ? document.getElementById('eventIdInput').value : null;

    const priorityRaw = document.getElementById('priority').value;
    const priceRaw    = document.getElementById('priceQuote').value;

    const eventData = {
        registration_date:    document.getElementById('registrationDate').value,
        first_contact_date:   document.getElementById('firstContactDate').value || null,
        system:               systemValue,
        event_summary:        document.getElementById('eventSummary').value,
        event_details:        document.getElementById('eventDetails').value,
        affected_customers:   document.getElementById('affectedCustomers').value,
        urgency:              document.getElementById('urgency').value,
        priority:             priorityRaw ? parseInt(priorityRaw) : 5,
        status:               document.getElementById('status').value,
        status_details:       document.getElementById('statusDetails').value,
        event_classification: document.getElementById('eventClassification').value,
        status_deadline:      document.getElementById('statusDeadline').value,
        completion_date:      document.getElementById('completionDate').value || null,
        responsible_person:   responsible,
        price_quote:          priceRaw ? parseFloat(priceRaw) : null,
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

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`שגיאת שרת ${response.status}: ${errText}`);
        }

        const result = await response.json();
        if (result.success) {
            if (!isEdit && result.event_id) {
                // ── NEW EVENT: write the server-assigned ID back into the hidden field ──
                // This lets the user upload files immediately after saving without
                // re-opening the event. The modal stays open after a new-event save.
                document.getElementById('eventId').value = result.event_id;
                document.getElementById('eventIdInput').value = result.event_id;
                document.getElementById('modalTitle').textContent = `עריכת אירוע #${result.event_id}`;
                alert(result.message);
                loadEvents();
                loadStats();
            } else {
                // ── EDIT: close the modal as usual ──
                alert(result.message);
                closeEventModal();
                loadEvents();
                loadStats();
            }
        } else {
            if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'שמור'; }
            alert('שגיאה: ' + result.error);
        }
    } catch (error) {
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'שמור'; }
        console.error('Error saving event:', error);
        alert('שגיאה בשמירת האירוע: ' + error.message);
    }
}

async function deleteEvent(eventId) {
    if (!currentUser) { alert('יש לבחור משתמש תחילה'); return; }
    if (!confirm('האם אתה בטוח שברצונך למחוק אירוע זה?')) return;
    try {
        const response = await fetch(`${API_URL}/events/${eventId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ changed_by: currentUser })
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`שגיאת שרת ${response.status}: ${errText}`);
        }

        const result = await response.json();
        if (result.success) {
            alert(result.message);
            loadEvents();
            loadStats();
        } else {
            alert('שגיאה: ' + result.error);
        }
    } catch (error) {
        console.error('Error deleting event:', error);
        alert('שגיאה במחיקת האירוע: ' + error.message);
    }
}

/** Closes the create/edit event modal and also hides any lingering toast. */
function closeEventModal() {
    document.getElementById('eventModal').classList.remove('active');
    _hideIdToast();
    // reset save button in case it was disabled during a previous submit
    const submitBtn = document.querySelector('#eventForm button[type="submit"]');
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'שמור'; }
}

// ── FILE MANAGEMENT ───────────────────────────────────────────────────────────

async function uploadFiles() {
    const eventId = document.getElementById('eventId').value;
    if (!eventId) { alert('יש לשמור את האירוע תחילה לפני העלאת קבצים'); return; }
    const fileInput = document.getElementById('fileInput');
    if (fileInput.files.length === 0) { alert('לא נבחרו קבצים'); return; }

    for (let i = 0; i < fileInput.files.length; i++) {
        const originalName = fileInput.files[i].name;

        // ask the user what they want to call this file — prefill with the original name
        const displayName = window.prompt(
            `שם תצוגה לקובץ "${originalName}":\n(ניתן לשנות או להשאיר כפי שהוא)`,
            originalName
        );
        // if the user pressed Cancel — skip this file
        if (displayName === null) continue;

        const formData = new FormData();
        formData.append('file', fileInput.files[i]);
        formData.append('uploaded_by', currentUser || 'Unknown');
        formData.append('display_name', displayName.trim() || originalName); // never save an empty name
        try {
            const response = await fetch(`${API_URL}/events/${eventId}/files`, { method: 'POST', body: formData });
            const result = await response.json();
            if (!result.success) alert(`שגיאה בהעלאת ${originalName}: ${result.error}`);
        } catch (error) {
            alert(`שגיאה בהעלאת ${originalName}`);
        }
    }
    const response = await fetchNoCache(`${API_URL}/events/${eventId}`);
    const event    = await response.json();
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
        // show the user-supplied display_name; fall back to original_filename for old files
        const shownName = file.display_name || file.original_filename;
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <span title="${file.original_filename}">📄 ${shownName}</span>
            <div style="display:flex;gap:5px;">
                <button type="button" class="btn btn-primary btn-small" onclick="openFile(${file.id})">👁️ פתח</button>
                <button type="button" class="btn btn-primary btn-small" onclick="downloadFile(${file.id})">⬇️ הורד</button>
                <button type="button" class="btn btn-danger btn-small" onclick="deleteFile(${file.id})">🗑️</button>
            </div>
        `;
        filesList.appendChild(fileItem);
    });
}

// ── FILE DOWNLOAD ─────────────────────────────────────────────────────────────

async function downloadFile(fileId) {
    try {
        const response = await fetch(`${API_URL}/files/${fileId}/download`);
        if (!response.ok) throw new Error('שגיאת שרת: ' + response.status);
        const disposition2 = response.headers.get('Content-Disposition') || '';
        const match2       = disposition2.match(/filename="?([^"]+)"?/);
        const filename2    = match2 ? match2[1] : 'download';
        const blob    = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href     = blobUrl;
        a.download = filename2;
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
        const result   = await response.json();
        if (result.success) {
            const eventId       = document.getElementById('eventId').value;
            const eventResponse = await fetchNoCache(`${API_URL}/events/${eventId}`);
            const event         = await eventResponse.json();
            displayEventFiles(event.files || []);
        } else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה במחיקת הקובץ');
    }
}

// ── ADMIN PANEL ───────────────────────────────────────────────────────────────

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
        const users    = await response.json();
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
        if (result.success) {
            loadUsersList();
            loadUsers();
            loadEvents();
            loadStats();
        }
        else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה בשמירת המשתמש');
    }
}

async function handleAddUser(e) {
    e.preventDefault();
    const userData = {
        name:  document.getElementById('newUserName').value,
        role:  document.getElementById('newUserRole').value,
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
        const result   = await response.json();
        if (result.success) { alert(result.message); loadUsersList(); loadEmailList(); loadUsers(); }
        else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה במחיקת משתמש');
    }
}

// ── EMAIL DISTRIBUTION LIST ───────────────────────────────────────────────────

async function loadEmailList() {
    try {
        const response = await fetchNoCache(`${API_URL}/email-list`);
        const emails   = await response.json();
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
        const result   = await response.json();
        if (result.success) loadEmailList();
        else alert('שגיאה: ' + result.error);
    } catch (error) {
        alert('שגיאה במחיקת אימייל');
    }
}

// ── ADMIN TABS ────────────────────────────────────────────────────────────────

function switchTab(tabName, evt) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById(tabName + 'Tab').classList.add('active');
    if (evt && evt.target) evt.target.classList.add('active');
    if (tabName === 'notifications') loadNotificationsTable();
    if (tabName === 'permissions')   loadPermissionsMatrix();
}

// ── EMAIL NOTIFICATION PREFERENCES ───────────────────────────────────────────

async function loadNotificationsTable() {
    try {
        const response = await fetchNoCache(`${API_URL}/notifications`);
        const data     = await response.json();
        const tbody    = document.getElementById('notificationsTableBody');
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

// ── PERMISSIONS MATRIX ────────────────────────────────────────────────────────

const FIELD_LABELS_UI = {
    registrationDate:        'תאריך רישום',
    firstContactDate:        'תאריך פנייה ראשונה',
    system:                  'מערכת',
    systemOther:             'מערכת אחרת (טקסט)',
    eventSummary:            'תמצית האירוע',
    eventDetails:            'פירוט האירוע',
    affectedCustomers:       'לקוחות מושפעים',
    urgency:                 'דחיפות',
    priority:                'עדיפות',
    status:                  'סטטוס',
    statusDetails:           'פירוט סטטוס',
    eventClassification:     'סיווג האירוע',
    statusDeadline:          'לו"ז',
    completionDate:          'תאריך השלמה',
    responsiblePerson:       'גורם אחראי',
    responsiblePersonOther:  'גורם אחראי (טקסט חופשי)',
    priceQuote:              'הצעת מחיר',
    additionalNotes:         'הערות נוספות',
};

async function loadPermissionsMatrix() {
    await loadRolePermissionsMatrix();
    await loadUserPermissionsMatrix();
}

async function loadRolePermissionsMatrix() {
    const tbody = document.getElementById('permMatrixBody');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:20px;color:#a0aec0;">טוען הרשאות...</td></tr>';

    try {
        const res    = await fetchNoCache(`${API_URL}/permissions/all`);
        const matrix = await res.json();

        const roles     = ['admin', 'planning', 'development'];
        const allFields = Object.keys(FIELD_LABELS_UI);

        tbody.innerHTML = allFields.map(field => {
            const label = FIELD_LABELS_UI[field] || field;
            const cells = roles.map(role => {
                const val = (matrix[role] && matrix[role][field] !== undefined)
                    ? matrix[role][field] : 1;
                const isAdmin = role === 'admin';
                if (isAdmin) {
                    return `<td><input type="checkbox" class="perm-toggle" checked disabled title="אדמין תמיד בעל גישה מלאה"></td>`;
                }
                return `<td>
                    <input type="checkbox" class="perm-toggle"
                        ${val ? 'checked' : ''}
                        onchange="updatePermissionCell('${role}', '${field}', this.checked)"
                        title="${label} — ${getRoleLabel(role)}">
                </td>`;
            }).join('');
            return `<tr><td>${label}</td>${cells}</tr>`;
        }).join('');

    } catch (err) {
        console.error('Error loading role permissions matrix:', err);
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#f56565;">שגיאה בטעינת הרשאות</td></tr>';
    }
}

async function updatePermissionCell(role, fieldName, checked) {
    try {
        const res = await fetch(`${API_URL}/permissions/${role}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field_name: fieldName, can_edit: checked ? 1 : 0 })
        });
        const result = await res.json();
        if (result.success) {
            showPermSaveBanner();
        } else {
            alert('שגיאה בשמירת הרשאה: ' + result.error);
        }
    } catch (err) {
        console.error('Error updating permission:', err);
        alert('שגיאה בשמירת הרשאה');
    }
}

async function loadUserPermissionsMatrix() {
    const container = document.getElementById('userPermMatrixContainer');
    if (!container) return;

    container.innerHTML = '<p style="color:#a0aec0;text-align:center;padding:20px;">טוען הרשאות משתמשים...</p>';

    try {
        const res  = await fetchNoCache(`${API_URL}/user-permissions/all`);
        const data = await res.json();

        const nonAdminUsers = (data.users || []).filter(u => u.role !== 'admin');
        const matrix        = data.matrix || {};
        const allFields     = Object.keys(FIELD_LABELS_UI);

        if (nonAdminUsers.length === 0) {
            container.innerHTML = '<p style="color:#a0aec0;text-align:center;padding:20px;">אין משתמשים שאינם אדמין</p>';
            return;
        }

        const roleColors = { planning: '#667eea', development: '#48bb78' };
        const headerCells = nonAdminUsers.map(u => {
            const color = roleColors[u.role] || '#999';
            return `<th style="text-align:center;min-width:110px;">
                <div style="font-weight:bold;">${u.name}</div>
                <div style="font-size:11px;color:${color};margin-top:2px;">${getRoleLabel(u.role)}</div>
            </th>`;
        }).join('');

        const dataRows = allFields.map(field => {
            const label = FIELD_LABELS_UI[field] || field;
            const cells = nonAdminUsers.map(u => {
                const userPerms = matrix[u.id] || {};
                const val = userPerms[field] !== undefined ? userPerms[field] : 1;
                return `<td style="text-align:center;">
                    <input type="checkbox" class="perm-toggle"
                        ${val ? 'checked' : ''}
                        onchange="updateUserPermissionCell(${u.id}, '${field}', this.checked)"
                        title="${label} — ${u.name}">
                </td>`;
            }).join('');
            return `<tr><td style="font-weight:bold;color:#4a5568;">${label}</td>${cells}</tr>`;
        }).join('');

        container.innerHTML = `
            <h3 style="color:#667eea;margin:24px 0 8px;">הרשאות עריכת שדות לפי משתמש</h3>
            <p style="color:#888;font-size:14px;margin-bottom:12px;">
                הרשאות אלו עוקפות את הגדרות התפקיד עבור כל משתמש בנפרד.
                שינויים נשמרים אוטומטית.
            </p>
            <div style="overflow-x:auto;">
                <table class="perm-matrix-table">
                    <thead>
                        <tr>
                            <th style="min-width:160px;">שדה</th>
                            ${headerCells}
                        </tr>
                    </thead>
                    <tbody>${dataRows}</tbody>
                </table>
            </div>`;

    } catch (err) {
        console.error('Error loading user permissions matrix:', err);
        container.innerHTML = '<p style="color:#f56565;text-align:center;padding:20px;">שגיאה בטעינת הרשאות משתמשים</p>';
    }
}

async function updateUserPermissionCell(userId, fieldName, checked) {
    try {
        const res = await fetch(`${API_URL}/user-permissions/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field_name: fieldName, can_edit: checked ? 1 : 0 })
        });
        const result = await res.json();
        if (result.success) {
            showPermSaveBanner();
            if (currentUserId && userId === currentUserId) {
                await loadPermissions(currentUserId, currentUserRole);
            }
        } else {
            alert('שגיאה בשמירת הרשאת משתמש: ' + result.error);
        }
    } catch (err) {
        console.error('Error updating user permission:', err);
        alert('שגיאה בשמירת הרשאת משתמש');
    }
}

function showPermSaveBanner() {
    const banner = document.getElementById('permSaveBanner');
    if (!banner) return;
    banner.classList.add('visible');
    clearTimeout(banner._hideTimer);
    banner._hideTimer = setTimeout(() => banner.classList.remove('visible'), 2500);
}

// ── EXCEL REPORT ──────────────────────────────────────────────────────────────

// All possible event statuses — used to populate the report dropdown
const ALL_STATUSES = [
    'אירוע חדש', 'בטיפול', 'בהכנת הצעת מחיר', 'בפיתוח',
    'בבדיקת איכות של פיתוח', 'ממתין לאישור הצעת מחיר',
    'בבדיקת תחום תכנון', 'הושלם הטיפול', 'בהקפאה', 'טופל חלקית'
];

/**
 * Generates and downloads an Excel report (all-time).
 * @param {string} [status] - If provided, filters to events matching that status (all time).
 *                            If empty/omitted, includes ALL events from all time.
 * Note: the automated weekly email is sent by the server scheduler — completely separate.
 */
async function generateReport(status) {
    try {
        const url = (status !== undefined && status !== '')
            ? `${API_URL}/reports/excel?status=${encodeURIComponent(status)}`
            : `${API_URL}/reports/excel`;

        const response = await fetch(url);
        if (!response.ok) throw new Error('Report generation failed');

        const blob    = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a       = document.createElement('a');
        a.href     = blobUrl;
        const dateStr = new Date().toISOString().split('T')[0];
        a.download = (status !== undefined && status !== '')
            ? `דוח_אירועים_${status}_${dateStr}.xlsx`
            : `דוח_אירועים_כל_הזמנים_${dateStr}.xlsx`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(blobUrl); }, 500);

        // close the dropdown after download starts
        const dd = document.getElementById('reportDropdown');
        if (dd) dd.style.display = 'none';

    } catch (err) {
        console.error('Report error:', err);
        alert('שגיאה בהפקת הדוח');
    }
}

/**
 * Toggles the report dropdown open/closed.
 * Populated lazily on first open: "הכל (כל הזמנים)" at top, then one button per status.
 */
function toggleReportDropdown() {
    const dd = document.getElementById('reportDropdown');
    if (!dd) return;
    const isVisible = dd.style.display === 'block';
    dd.style.display = isVisible ? 'none' : 'block';

    // populate only once — skip if already built
    if (dd.children.length === 0) {
        const allBtn = document.createElement('button');
        allBtn.className        = 'report-dd-item';
        allBtn.textContent      = '📋 הכל (כל הזמנים)';
        allBtn.style.fontWeight = 'bold';
        allBtn.onclick          = () => generateReport('');
        dd.appendChild(allBtn);

        const sep = document.createElement('hr');
        sep.style.cssText = 'margin:4px 0;border:none;border-top:1px solid #e2e8f0;';
        dd.appendChild(sep);

        ALL_STATUSES.forEach(s => {
            const btn = document.createElement('button');
            btn.className   = 'report-dd-item';
            btn.textContent = s;
            btn.onclick     = () => generateReport(s);
            dd.appendChild(btn);
        });
    }
}

// close the report dropdown when clicking anywhere outside the wrapper
document.addEventListener('click', function(e) {
    const wrapper = document.getElementById('reportBtnWrapper');
    const dd      = document.getElementById('reportDropdown');
    if (dd && wrapper && !wrapper.contains(e.target)) {
        dd.style.display = 'none';
    }
});

// ── ANALYSIS MODAL (CHARTS) ───────────────────────────────────────────────────

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
            datasets: [{
                data,
                backgroundColor: CHART_PALETTE.slice(0, labels.length),
                borderWidth: 2,
                borderColor: '#fff',
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true, cutout: '62%',
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 13 }, padding: 12, boxWidth: 14 } },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${ctx.label}: ${ctx.parsed} (${Math.round(ctx.parsed / ctx.dataset.data.reduce((a,b) => a+b, 0) * 100)}%)`
                    }
                }
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
        const r   = await fetchNoCache(`${API_URL}/events`);
        const all = await r.json();
        events = all.filter(e => e.id > 0 && e.is_deleted !== 1 && e.status !== 'הושלם הטיפול');
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
        const ctx    = canvas.getContext('2d');
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

// ── DATE FORMATTING UTILITIES ─────────────────────────────────────────────────

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