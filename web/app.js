// Mobile nav
const toggle = () => {
    const nav = document.querySelector('.site-nav');
    if (!nav) return;
    nav.style.display = (nav.style.display === 'flex') ? 'none' : 'flex';   
};
document.querySelectorAll('.nav-toggle').forEach(btn => btn.addEventListener('click', toggle));


// Year footer
const yEl = document.getElementById('year');
if (yEl) yEl.textContent = new Date().getFullYear();

function fmtDate(d) {
    const dt = new Date(d + 'T00:00:00');
    return dt.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

async function fetchJSON(url, opts = {}) {
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

// Dashboard: upcoming & suggestions
(function initDashboard(){
    if (document.body.dataset.page !== 'dashboard') return;
    const ul = document.getElementById('upcoming-list');
    const suggestions = document.getElementById('suggestions');
    const week = document.getElementById('week-preview');

    if (week) {
        week.innerHTML = '<div class="muted">Calendar preview powered by in-app events.</div>';
    }
})();

// Assignments page
(function initAssignments(){
    if (document.body.dataset.page !== 'assignments') return;
    const listEl = document.getElementById('assignment-list');
    const searchEl = document.getElementById('search');
    const courseEl = document.getElementById('course-filter');
    const statusEl = document.getElementById('status-filter');


    // Stub content until assignments are hooked to backend events.
    listEl.innerHTML = '<p class="muted">Assignments will sync from calendar events in a future update.</p>';
})();

// Calendar page
(function initCalendar(){
    if (document.body.dataset.page !== 'calendar') return;
    const grid = document.getElementById('calendar-grid');
    const label = document.getElementById('month-label');
    const prev = document.getElementById('prev-month');
    const next = document.getElementById('next-month');
    const form = document.getElementById('event-form');
    const status = document.getElementById('event-status');
    const list = document.getElementById('event-list');


    const today = new Date();
    let view = new Date(today.getFullYear(), today.getMonth(), 1);
    let events = [];

    const state = {
        async load() {
            try {
                const data = await fetchJSON('/api/events');
                events = data.events || [];
                draw();
                renderList();
                status.textContent = '';
            } catch (err) {
                status.textContent = 'Failed to load events.';
                console.error(err);
            }
        },
        async add(payload) {
            try {
                const res = await fetchJSON('/api/events', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                events.push(res);
                draw();
                renderList();
                status.textContent = 'Event added.';
            } catch (err) {
                status.textContent = 'Could not add event.';
                console.error(err);
            }
        }
    };


    function draw(){
        const year = view.getFullYear(); const month = view.getMonth();
        label.textContent = view.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });


        const firstDay = new Date(year, month, 1);
        const startDay = (firstDay.getDay() + 6) % 7; // make Monday=0
        const daysInMonth = new Date(year, month+1, 0).getDate();


        grid.innerHTML = '';
        // Weekday headers
        ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].forEach(d => {
            const head = document.createElement('div'); head.className='calendar-cell'; head.style.background='transparent'; head.style.border='0'; head.innerHTML = `<div class="muted">${d}</div>`; grid.appendChild(head);
        });


        for (let i=0;i<startDay;i++) { const cell=document.createElement('div'); cell.className='calendar-cell'; grid.appendChild(cell); }
        for (let day=1; day<=daysInMonth; day++) {
            const cell = document.createElement('div'); cell.className = 'calendar-cell';
            cell.innerHTML = `<div class="date">${day}</div>`;
            const thisDate = new Date(year, month, day);
            events
                .map(e => ({ raw: e, date: new Date(e.date) }))
                .filter(e => e.date.getFullYear()===year && e.date.getMonth()===month && e.date.getDate()===day)
                .forEach(e => {
                    const tag = document.createElement('div'); 
                    tag.className='event'; 
                    const progress = e.raw.ai?.progress_percent ?? 0;
                    tag.innerHTML = `<div>${e.raw.title}</div><div class="muted" style="font-size:12px;">${progress}%</div>`;
                    cell.appendChild(tag);
                });
            grid.appendChild(cell);
        }
    }

    function renderList() {
        if (!list) return;
        list.innerHTML = '';
        if (!events.length) {
            list.innerHTML = '<p class="muted">No events yet. Add one above.</p>';
            return;
        }
        events
            .slice()
            .sort((a,b) => (a.date || '').localeCompare(b.date || ''))
            .forEach(ev => {
                const wrap = document.createElement('div');
                wrap.className = 'panel';
                const progress = ev.ai?.progress_percent ?? 0;
                const docs = ev.docs || [];
                wrap.innerHTML = `
                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;">
                        <div>
                            <div style="font-weight:600;">${ev.title}</div>
                            <div class="muted">${ev.date ? fmtDate(ev.date) : ''}</div>
                        </div>
                        <span class="badge" style="background:rgba(126,240,212,0.12);border:1px solid rgba(126,240,212,0.4);color:#7ef0d4;">${progress}%</span>
                    </div>
                    <div class="progress">
                        <div class="progress__bar" style="width:${progress}%"></div>
                    </div>
                    <div class="muted" style="margin:6px 0;">${ev.ai?.notes || ''}</div>
                    <ul class="list" style="margin-top:8px;">
                        ${(ev.ai?.steps || []).map(s => `<li>${s}</li>`).join('')}
                    </ul>
                    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">
                        ${docs.map(d => `<a class="doc-chip" href="${d.url || '#'}" target="_blank" rel="noreferrer">${d.title || 'Document'}</a>`).join('')}
                    </div>
                `;
                list.appendChild(wrap);
            });
    }


    prev.addEventListener('click', ()=>{ view = new Date(view.getFullYear(), view.getMonth()-1, 1); draw(); });
    next.addEventListener('click', ()=>{ view = new Date(view.getFullYear(), view.getMonth()+1, 1); draw(); });

    if (form) {
        form.addEventListener('submit', async (e)=>{
            e.preventDefault();
            const payload = {
                title: document.getElementById('event-title').value,
                date: document.getElementById('event-date').value,
                description: document.getElementById('event-desc').value,
                docs: []
            };
            const docTitle = document.getElementById('doc-title').value;
            const docUrl = document.getElementById('doc-url').value;
            const docNotes = document.getElementById('doc-notes').value;
            if (docTitle || docUrl || docNotes) {
                payload.docs.push({ title: docTitle, url: docUrl, summary: docNotes });
            }
            status.textContent = 'Saving...';
            await state.add(payload);
            form.reset();
        });
    }

    state.load();
})();

// Settings page (stub)
(function initSettings(){
    if (document.body.dataset.page !== 'settings') return;
    document.getElementById('settings-form').addEventListener('submit', (e)=>{
        e.preventDefault();
        alert('Settings saved (stub).');
    });
    document.getElementById('connect-google').addEventListener('click', ()=>{
        // TODO: Trigger OAuth to Google in your real app
        alert('Google Calendar connect stub.');
    });
    document.getElementById('connect-openai').addEventListener('click', ()=>{
        // TODO: Store OpenAI API key or connect account in your real app
        alert('OpenAI connect stub.');
    });
})();
