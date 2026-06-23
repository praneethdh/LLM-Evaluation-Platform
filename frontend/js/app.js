/**
 * EvalForge — Frontend Application
 * SPA with hash-based routing, API client, Chart.js visualizations
 */

// ═══════════════════════════════════════════════════════════════
// API Client
// ═══════════════════════════════════════════════════════════════

const API = {
    base: window.location.origin,

    async request(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);

        const resp = await fetch(`${this.base}${path}`, opts);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        return resp.json();
    },

    // Test Suites
    getSuites: () => API.request('GET', '/api/suites'),
    getSuite: (id) => API.request('GET', `/api/suites/${id}`),
    createSuite: (data) => API.request('POST', '/api/suites', data),
    updateSuite: (id, data) => API.request('PUT', `/api/suites/${id}`, data),
    deleteSuite: (id) => API.request('DELETE', `/api/suites/${id}`),
    addCase: (suiteId, data) => API.request('POST', `/api/suites/${suiteId}/cases`, data),
    deleteCase: (id) => API.request('DELETE', `/api/cases/${id}`),

    // Runs
    startRun: (data) => API.request('POST', '/api/runs', data),
    getRuns: (params = '') => API.request('GET', `/api/runs${params ? '?' + params : ''}`),
    getRun: (id) => API.request('GET', `/api/runs/${id}`),
    getProgress: (id) => API.request('GET', `/api/runs/${id}/progress`),

    // Compare
    compare: (runA, runB) => API.request('GET', `/api/compare?run_a=${runA}&run_b=${runB}`),
    checkRegression: (id) => API.request('GET', `/api/runs/${id}/regression`),

    // System
    getModels: () => API.request('GET', '/api/models'),
    getHealth: () => API.request('GET', '/api/health'),
    estimateQuota: (data) => API.request('POST', '/api/quota/estimate', data),
};

// ═══════════════════════════════════════════════════════════════
// Router
// ═══════════════════════════════════════════════════════════════

const Router = {
    routes: {},

    register(hash, handler) {
        this.routes[hash] = handler;
    },

    navigate(hash) {
        window.location.hash = hash;
    },

    init() {
        window.addEventListener('hashchange', () => this._resolve());
        this._resolve();
    },

    _resolve() {
        const hash = window.location.hash || '#dashboard';
        const [route, ...params] = hash.split('/');

        // Update nav active state
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.toggle('active', el.dataset.route === route);
        });

        const handler = this.routes[route];
        if (handler) {
            handler(params);
        } else {
            this.routes['#dashboard']?.([]);
        }
    }
};

// ═══════════════════════════════════════════════════════════════
// Utility Functions
// ═══════════════════════════════════════════════════════════════

function $(selector) { return document.querySelector(selector); }
function $$(selector) { return document.querySelectorAll(selector); }

function scoreClass(score, max = 10) {
    const pct = (score / max) * 100;
    if (pct >= 80) return 'excellent';
    if (pct >= 60) return 'good';
    if (pct >= 40) return 'average';
    return 'poor';
}

function scoreColor(score, max = 10) {
    const pct = (score / max) * 100;
    if (pct >= 80) return '#10b981';
    if (pct >= 60) return '#34d399';
    if (pct >= 40) return '#fbbf24';
    return '#f87171';
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function truncate(str, len = 80) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '…' : str;
}

function scorePill(score, max = 10) {
    if (score == null) return '<span class="score-pill average">—</span>';
    const cls = scoreClass(score, max);
    const display = max === 1 ? score.toFixed(2) : score.toFixed(1);
    return `<span class="score-pill ${cls}">${display}</span>`;
}

function deltaIndicator(delta) {
    if (delta == null) return '<span class="delta-indicator delta-neutral">—</span>';
    const sign = delta > 0 ? '+' : '';
    const cls = delta > 0 ? 'delta-positive' : delta < 0 ? 'delta-negative' : 'delta-neutral';
    return `<span class="delta-indicator ${cls}">${sign}${delta.toFixed(1)}</span>`;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed; bottom: 24px; right: 24px; padding: 14px 24px;
        border-radius: 10px; font-size: 0.85rem; z-index: 1000;
        animation: slide-in 0.3s ease; font-family: 'Inter', sans-serif;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        ${type === 'error' ? 'background: rgba(239,68,68,0.2); border: 1px solid rgba(239,68,68,0.4); color: #fca5a5;'
        : type === 'success' ? 'background: rgba(16,185,129,0.2); border: 1px solid rgba(16,185,129,0.4); color: #6ee7b7;'
        : 'background: rgba(99,102,241,0.2); border: 1px solid rgba(99,102,241,0.4); color: #a5b4fc;'}
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3000);
}

// ═══════════════════════════════════════════════════════════════
// Page Renderers
// ═══════════════════════════════════════════════════════════════

const content = () => $('#main-content');

// ── Dashboard ─────────────────────────────────────────────────

async function renderDashboard() {
    content().innerHTML = `
        <div class="page-header">
            <h2>Dashboard</h2>
            <p>Overview of recent evaluations and system status</p>
        </div>
        <div id="regression-alerts"></div>
        <div id="dashboard-stats" class="score-grid">
            <div class="skeleton skeleton-card"></div>
            <div class="skeleton skeleton-card"></div>
            <div class="skeleton skeleton-card"></div>
            <div class="skeleton skeleton-card"></div>
        </div>
        <div class="card mt-24">
            <div class="card-header">
                <span class="card-title">Recent Evaluation Runs</span>
                <button class="btn btn-primary btn-sm" onclick="Router.navigate('#run')">+ New Run</button>
            </div>
            <div id="recent-runs-table">
                <div class="skeleton skeleton-line medium"></div>
                <div class="skeleton skeleton-line"></div>
                <div class="skeleton skeleton-line short"></div>
            </div>
        </div>
    `;

    try {
        const [runs, health] = await Promise.all([API.getRuns(), API.getHealth()]);

        // Update provider status in sidebar
        renderProviderStatus(health.providers);

        // Stats
        const completed = runs.filter(r => r.status === 'completed');
        const totalCases = completed.reduce((sum, r) => sum + r.total_cases, 0);
        const avgScore = completed.length > 0
            ? completed.reduce((sum, r) => sum + (r.avg_correctness || 0), 0) / completed.length
            : 0;
        const avgLatency = completed.length > 0
            ? completed.reduce((sum, r) => sum + (r.avg_latency_ms || 0), 0) / completed.length
            : 0;

        $('#dashboard-stats').innerHTML = `
            <div class="score-card ${scoreClass(completed.length > 0 ? 8 : 2)}">
                <div class="score-label">Total Runs</div>
                <div class="score-value">${runs.length}</div>
            </div>
            <div class="score-card ${scoreClass(totalCases > 0 ? 8 : 2)}">
                <div class="score-label">Cases Evaluated</div>
                <div class="score-value">${totalCases}</div>
            </div>
            <div class="score-card ${scoreClass(avgScore)}">
                <div class="score-label">Avg Correctness</div>
                <div class="score-value">${avgScore.toFixed(1)} <span class="score-max">/ 10</span></div>
            </div>
            <div class="score-card ${scoreClass(avgLatency < 2000 ? 8 : 4)}">
                <div class="score-label">Avg Latency</div>
                <div class="score-value">${avgLatency.toFixed(0)} <span class="score-max">ms</span></div>
            </div>
        `;

        // Check for regressions in recent completed runs
        const alertsHtml = [];
        for (const run of completed.slice(0, 5)) {
            try {
                const reg = await API.checkRegression(run.id);
                if (reg && reg.has_regression) {
                    alertsHtml.push(`
                        <div class="regression-banner">
                            <span class="alert-icon">⚠️</span>
                            <div class="alert-text">
                                <strong>Regression detected</strong> in Run #${run.id} (${run.model_id}):
                                ${reg.regression_summary}
                            </div>
                        </div>
                    `);
                }
            } catch (e) { /* no previous run for comparison */ }
        }
        $('#regression-alerts').innerHTML = alertsHtml.join('');

        // Recent runs table
        if (runs.length === 0) {
            $('#recent-runs-table').innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📊</div>
                    <p>No evaluation runs yet. Create a test suite and start your first run.</p>
                    <button class="btn btn-primary" onclick="Router.navigate('#suites')">Create Test Suite</button>
                </div>
            `;
        } else {
            $('#recent-runs-table').innerHTML = `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Run</th>
                            <th>Suite</th>
                            <th>Model</th>
                            <th>Status</th>
                            <th>Correctness</th>
                            <th>Latency</th>
                            <th>Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${runs.slice(0, 15).map(r => `
                            <tr style="cursor:pointer" onclick="Router.navigate('#results/${r.id}')">
                                <td class="mono">#${r.id}</td>
                                <td>${truncate(r.suite_name, 25)}</td>
                                <td class="mono">${r.model_id.split('/').pop().replace(':free', '')}</td>
                                <td><span class="badge badge-${r.status}">${r.status}</span></td>
                                <td>${scorePill(r.avg_correctness)}</td>
                                <td class="mono">${r.avg_latency_ms ? r.avg_latency_ms.toFixed(0) + 'ms' : '—'}</td>
                                <td>${formatDate(r.created_at)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    } catch (err) {
        content().innerHTML += `<div class="regression-banner"><span class="alert-icon">❌</span><div class="alert-text">${err.message}</div></div>`;
    }
}

function renderProviderStatus(providers) {
    const container = $('#provider-status');
    if (!container) return;
    container.innerHTML = providers.map(p => `
        <div class="provider-status">
            <span class="status-dot ${p.status}"></span>
            <span>${p.name}</span>
        </div>
    `).join('');
}

// ── Test Suites ───────────────────────────────────────────────

async function renderSuites() {
    content().innerHTML = `
        <div class="page-header flex justify-between items-center">
            <div>
                <h2>Test Suites</h2>
                <p>Manage your evaluation test suites and test cases</p>
            </div>
            <button class="btn btn-primary" onclick="showCreateSuiteModal()">+ New Suite</button>
        </div>
        <div id="suites-list">
            <div class="skeleton skeleton-card"></div>
            <div class="skeleton skeleton-card"></div>
        </div>
        <div id="modal-container"></div>
    `;

    try {
        const suites = await API.getSuites();
        if (suites.length === 0) {
            $('#suites-list').innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📝</div>
                    <p>No test suites yet. Create your first suite to start evaluating.</p>
                    <button class="btn btn-primary" onclick="showCreateSuiteModal()">Create Test Suite</button>
                </div>
            `;
        } else {
            $('#suites-list').innerHTML = suites.map(s => `
                <div class="card" style="margin-bottom:12px; cursor:pointer" onclick="Router.navigate('#suites/${s.id}')">
                    <div class="flex justify-between items-center">
                        <div>
                            <div class="card-title">${s.name}</div>
                            <div style="color:var(--text-secondary); font-size:0.82rem; margin-top:4px">${s.description || 'No description'}</div>
                        </div>
                        <div class="flex gap-12 items-center">
                            <span class="badge badge-completed">${s.case_count} cases</span>
                            <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); deleteSuiteConfirm(${s.id}, '${s.name}')">🗑</button>
                        </div>
                    </div>
                </div>
            `).join('');
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function renderSuiteDetail(suiteId) {
    content().innerHTML = `<div class="skeleton skeleton-card"></div>`;

    try {
        const suite = await API.getSuite(suiteId);
        content().innerHTML = `
            <div class="page-header">
                <div class="flex items-center gap-12">
                    <button class="btn btn-secondary btn-sm" onclick="Router.navigate('#suites')">← Back</button>
                    <div>
                        <h2>${suite.name}</h2>
                        <p>${suite.description || 'No description'}</p>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Test Cases (${suite.test_cases.length})</span>
                    <button class="btn btn-primary btn-sm" onclick="showAddCaseModal(${suite.id})">+ Add Case</button>
                </div>
                <div id="cases-list">
                    ${suite.test_cases.length === 0 ? `
                        <div class="empty-state">
                            <p>No test cases yet. Add your first test case.</p>
                        </div>
                    ` : suite.test_cases.map((tc, i) => `
                        <div class="test-case-row">
                            <div class="case-header">
                                <span class="case-number">Case #${i + 1} ${tc.tags ? '• ' + tc.tags : ''}</span>
                                <button class="btn btn-danger btn-sm" onclick="deleteCase(${tc.id}, ${suite.id})">✕</button>
                            </div>
                            <div class="test-case-fields">
                                <div>
                                    <label style="font-size:0.7rem; color:var(--text-muted); margin-bottom:4px; display:block">INPUT</label>
                                    <div class="result-output">${tc.input_text}</div>
                                </div>
                                <div>
                                    <label style="font-size:0.7rem; color:var(--text-muted); margin-bottom:4px; display:block">EXPECTED OUTPUT</label>
                                    <div class="result-output">${tc.expected_output || '(open-ended)'}</div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div id="modal-container"></div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Suite CRUD Modals

window.showCreateSuiteModal = function () {
    const container = $('#modal-container');
    container.innerHTML = `
        <div class="modal-overlay" onclick="if(event.target===this) this.remove()">
            <div class="modal">
                <h3>Create Test Suite</h3>
                <div class="form-group">
                    <label>Suite Name</label>
                    <input class="form-input" id="suite-name" placeholder="e.g., Customer Support QA">
                </div>
                <div class="form-group">
                    <label>Description</label>
                    <input class="form-input" id="suite-desc" placeholder="e.g., Tests for support chatbot accuracy">
                </div>
                <div id="create-cases">
                    <label style="font-size:0.8rem; font-weight:600; color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px; display:block;">Initial Test Cases</label>
                    <div id="case-rows"></div>
                    <button class="btn btn-secondary btn-sm mt-16" onclick="addCaseRow()">+ Add Test Case</button>
                </div>
                <div class="modal-actions">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="btn btn-primary" onclick="createSuite()">Create Suite</button>
                </div>
            </div>
        </div>
    `;
    addCaseRow();
};

window.addCaseRow = function () {
    const rows = $('#case-rows');
    const idx = rows.children.length + 1;
    const row = document.createElement('div');
    row.className = 'test-case-row';
    row.innerHTML = `
        <div class="case-header">
            <span class="case-number">Case #${idx}</span>
            <button class="btn btn-danger btn-sm" onclick="this.closest('.test-case-row').remove()">✕</button>
        </div>
        <div class="test-case-fields">
            <div class="form-group" style="margin:0">
                <textarea class="form-textarea case-input" placeholder="Input prompt / question"></textarea>
            </div>
            <div class="form-group" style="margin:0">
                <textarea class="form-textarea case-expected" placeholder="Expected output (optional)"></textarea>
            </div>
        </div>
    `;
    rows.appendChild(row);
};

window.createSuite = async function () {
    const name = $('#suite-name').value.trim();
    const desc = $('#suite-desc').value.trim();

    if (!name) { showToast('Suite name is required', 'error'); return; }

    const cases = [];
    $$('#case-rows .test-case-row').forEach(row => {
        const input = row.querySelector('.case-input').value.trim();
        if (input) {
            cases.push({
                input_text: input,
                expected_output: row.querySelector('.case-expected').value.trim(),
                tags: '',
            });
        }
    });

    try {
        await API.createSuite({ name, description: desc, test_cases: cases });
        showToast('Suite created successfully', 'success');
        $('.modal-overlay')?.remove();
        renderSuites();
    } catch (err) {
        showToast(err.message, 'error');
    }
};

window.showAddCaseModal = function (suiteId) {
    const container = $('#modal-container');
    container.innerHTML = `
        <div class="modal-overlay" onclick="if(event.target===this) this.remove()">
            <div class="modal">
                <h3>Add Test Case</h3>
                <div class="form-group">
                    <label>Input Prompt</label>
                    <textarea class="form-textarea" id="new-case-input" placeholder="The question or prompt to test"></textarea>
                </div>
                <div class="form-group">
                    <label>Expected Output (optional)</label>
                    <textarea class="form-textarea" id="new-case-expected" placeholder="The ideal answer for comparison"></textarea>
                </div>
                <div class="modal-actions">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="btn btn-primary" onclick="addCaseToSuite(${suiteId})">Add Case</button>
                </div>
            </div>
        </div>
    `;
};

window.addCaseToSuite = async function (suiteId) {
    const input = $('#new-case-input').value.trim();
    if (!input) { showToast('Input text is required', 'error'); return; }

    try {
        await API.addCase(suiteId, {
            input_text: input,
            expected_output: $('#new-case-expected').value.trim(),
            tags: '',
        });
        showToast('Test case added', 'success');
        $('.modal-overlay')?.remove();
        renderSuiteDetail(suiteId);
    } catch (err) {
        showToast(err.message, 'error');
    }
};

window.deleteCase = async function (caseId, suiteId) {
    if (!confirm('Delete this test case?')) return;
    try {
        await API.deleteCase(caseId);
        showToast('Case deleted', 'success');
        renderSuiteDetail(suiteId);
    } catch (err) {
        showToast(err.message, 'error');
    }
};

window.deleteSuiteConfirm = async function (id, name) {
    if (!confirm(`Delete suite "${name}" and all its data? This cannot be undone.`)) return;
    try {
        await API.deleteSuite(id);
        showToast('Suite deleted', 'success');
        renderSuites();
    } catch (err) {
        showToast(err.message, 'error');
    }
};

// ── Run Evaluation ────────────────────────────────────────────

async function renderRun() {
    content().innerHTML = `
        <div class="page-header">
            <h2>Run Evaluation</h2>
            <p>Select a model and test suite, then run the evaluation</p>
        </div>
        <div class="card">
            <div class="form-group">
                <label>Test Suite</label>
                <select class="form-select" id="run-suite">
                    <option value="">Loading suites...</option>
                </select>
            </div>
            <div class="form-group">
                <label>Model</label>
                <select class="form-select" id="run-model">
                    <option value="">Loading models...</option>
                </select>
            </div>
            <div class="form-group">
                <label>System Prompt (template)</label>
                <textarea class="form-textarea" id="run-prompt" placeholder="You are a helpful assistant that..."
                    rows="4">You are a helpful, accurate, and professional assistant. Answer questions clearly and concisely.</textarea>
            </div>
            <div id="quota-panel"></div>
            <div id="run-progress" class="hidden"></div>
            <div class="flex gap-12 mt-16">
                <button class="btn btn-secondary" id="btn-estimate" onclick="estimateQuota()">📊 Estimate</button>
                <button class="btn btn-primary" id="btn-start-run" onclick="startEvalRun()">▶ Start Run</button>
            </div>
        </div>
    `;

    try {
        const [suites, models] = await Promise.all([API.getSuites(), API.getModels()]);

        const suiteSelect = $('#run-suite');
        suiteSelect.innerHTML = '<option value="">Select a test suite</option>' +
            suites.map(s => `<option value="${s.id}">${s.name} (${s.case_count} cases)</option>`).join('');

        const modelSelect = $('#run-model');
        modelSelect.innerHTML = '<option value="">Select a model</option>' +
            models.map(m => `<option value="${m.provider}::${m.model_id}">${m.display_name} (${m.provider})</option>`).join('');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

window.estimateQuota = async function () {
    const suiteId = $('#run-suite').value;
    const modelVal = $('#run-model').value;
    const prompt = $('#run-prompt').value;

    if (!suiteId || !modelVal) { showToast('Select a suite and model first', 'error'); return; }

    const [provider, modelId] = modelVal.split('::');

    try {
        const est = await API.estimateQuota({
            suite_id: parseInt(suiteId),
            provider,
            model_id: modelId,
            system_prompt: prompt,
        });

        const minutes = Math.floor(est.estimated_time_seconds / 60);
        const seconds = est.estimated_time_seconds % 60;

        $('#quota-panel').innerHTML = `
            <div class="quota-panel">
                <h4>📊 Run Estimate</h4>
                <div class="quota-row">
                    <span>Test cases</span>
                    <span class="quota-value">${est.total_cases}</span>
                </div>
                <div class="quota-row">
                    <span>Model API calls</span>
                    <span class="quota-value">${est.model_calls_needed}</span>
                </div>
                <div class="quota-row cached">
                    <span>Cached results (skip API)</span>
                    <span class="quota-value">−${est.cache_hits}</span>
                </div>
                <div class="quota-row">
                    <span>Judge calls (Gemini)</span>
                    <span class="quota-value">${est.judge_calls_needed}</span>
                </div>
                <hr class="quota-divider">
                <div class="quota-row">
                    <span><strong>Total API calls</strong></span>
                    <span class="quota-value"><strong>${est.total_api_calls}</strong></span>
                </div>
                <div class="quota-row">
                    <span>Estimated time</span>
                    <span class="quota-value">~${minutes}m ${seconds}s</span>
                </div>
                <div class="quota-row">
                    <span>Est. cost (at paid rates)</span>
                    <span class="quota-value">$${est.estimated_cost_usd.toFixed(4)}</span>
                </div>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
    }
};

window.startEvalRun = async function () {
    const suiteId = $('#run-suite').value;
    const modelVal = $('#run-model').value;
    const prompt = $('#run-prompt').value;

    if (!suiteId || !modelVal) { showToast('Select a suite and model first', 'error'); return; }

    const [provider, modelId] = modelVal.split('::');
    const btn = $('#btn-start-run');
    btn.disabled = true;
    btn.textContent = '⏳ Starting...';

    try {
        const run = await API.startRun({
            suite_id: parseInt(suiteId),
            provider,
            model_id: modelId,
            system_prompt: prompt,
        });

        showToast('Evaluation started', 'success');
        pollProgress(run.id);
    } catch (err) {
        showToast(err.message, 'error');
        btn.disabled = false;
        btn.textContent = '▶ Start Run';
    }
};

function pollProgress(runId) {
    const progressDiv = $('#run-progress');
    progressDiv.classList.remove('hidden');

    const interval = setInterval(async () => {
        try {
            const p = await API.getProgress(runId);
            const pct = p.total_cases > 0 ? Math.round((p.completed_cases / p.total_cases) * 100) : 0;

            progressDiv.innerHTML = `
                <div class="card mt-16" style="border-color: rgba(99, 102, 241, 0.3)">
                    <div class="flex justify-between items-center mb-16">
                        <span class="card-title">Run #${runId}</span>
                        <span class="badge badge-${p.status}">${p.status}</span>
                    </div>
                    <div class="progress-container">
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" style="width: ${pct}%"></div>
                        </div>
                        <div class="progress-text">${p.completed_cases} / ${p.total_cases} cases (${pct}%)</div>
                    </div>
                    ${p.error_message ? `<div class="regression-banner mt-16"><span class="alert-icon">❌</span><div class="alert-text">${p.error_message}</div></div>` : ''}
                </div>
            `;

            if (p.status === 'completed' || p.status === 'failed') {
                clearInterval(interval);
                const btn = $('#btn-start-run');
                if (btn) { btn.disabled = false; btn.textContent = '▶ Start Run'; }

                if (p.status === 'completed') {
                    showToast('Evaluation completed!', 'success');
                    progressDiv.innerHTML += `
                        <div class="flex gap-12 mt-16">
                            <button class="btn btn-primary" onclick="Router.navigate('#results/${runId}')">View Results</button>
                            <button class="btn btn-secondary" onclick="Router.navigate('#compare/${runId}')">Compare</button>
                        </div>
                    `;
                }
            }
        } catch (err) {
            clearInterval(interval);
        }
    }, 3000);
}

// ── Results ───────────────────────────────────────────────────

async function renderResults(params) {
    const runId = params[0];

    if (!runId) {
        // Show list of all runs to pick from
        content().innerHTML = `
            <div class="page-header">
                <h2>Results</h2>
                <p>Select a run to view detailed results</p>
            </div>
            <div id="runs-list"><div class="skeleton skeleton-card"></div></div>
        `;

        try {
            const runs = await API.getRuns();
            const completed = runs.filter(r => r.status === 'completed');

            if (completed.length === 0) {
                $('#runs-list').innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div><p>No completed runs yet.</p></div>`;
                return;
            }

            $('#runs-list').innerHTML = completed.map(r => `
                <div class="card" style="margin-bottom:10px; cursor:pointer" onclick="Router.navigate('#results/${r.id}')">
                    <div class="flex justify-between items-center">
                        <div>
                            <span class="mono" style="color:var(--text-accent)">Run #${r.id}</span>
                            <span style="color:var(--text-secondary); margin-left:12px">${r.suite_name}</span>
                            <span class="mono" style="color:var(--text-muted); margin-left:12px">${r.model_id.split('/').pop()}</span>
                        </div>
                        <div class="flex gap-8 items-center">
                            ${scorePill(r.avg_correctness)}
                            <span class="mono" style="font-size:0.75rem; color:var(--text-muted)">${formatDate(r.created_at)}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        } catch (err) { showToast(err.message, 'error'); }
        return;
    }

    // Show specific run results
    content().innerHTML = `<div class="skeleton skeleton-card"></div>`;

    try {
        const run = await API.getRun(runId);

        content().innerHTML = `
            <div class="page-header">
                <div class="flex items-center gap-12">
                    <button class="btn btn-secondary btn-sm" onclick="Router.navigate('#results')">← Back</button>
                    <div>
                        <h2>Run #${run.id} — ${run.model_id.split('/').pop().replace(':free', '')}</h2>
                        <p>${run.provider} • ${run.total_cases} cases • ${formatDate(run.created_at)}
                            ${run.cache_hits > 0 ? ` • ${run.cache_hits} cache hits` : ''}</p>
                    </div>
                </div>
            </div>

            <div class="score-grid">
                ${[
                    ['Correctness', run.avg_correctness, 10],
                    ['Relevance', run.avg_relevance, 10],
                    ['Coherence', run.avg_coherence, 10],
                    ['Tone', run.avg_tone, 10],
                    ['Hallucination Res.', run.avg_hallucination_resistance, 10],
                    ['ROUGE-L', run.avg_rouge_l, 1],
                    ['Similarity', run.avg_similarity, 1],
                ].map(([label, score, max]) => `
                    <div class="score-card ${score != null ? scoreClass(score, max) : 'average'}">
                        <div class="score-label">${label}</div>
                        <div class="score-value">${score != null ? (max === 1 ? score.toFixed(2) : score.toFixed(1)) : '—'} <span class="score-max">/ ${max}</span></div>
                    </div>
                `).join('')}
            </div>

            <div class="chart-row">
                <div class="card">
                    <div class="card-title mb-16">Score Radar</div>
                    <div class="chart-container">
                        <canvas id="radar-chart"></canvas>
                    </div>
                </div>
                <div class="card">
                    <div class="card-title mb-16">Performance Metrics</div>
                    <div style="padding: 20px 0">
                        <div class="quota-row"><span>Avg Latency</span><span class="quota-value">${run.avg_latency_ms?.toFixed(0) || '—'} ms</span></div>
                        <div class="quota-row"><span>Total Input Tokens</span><span class="quota-value">${run.total_input_tokens.toLocaleString()}</span></div>
                        <div class="quota-row"><span>Total Output Tokens</span><span class="quota-value">${run.total_output_tokens.toLocaleString()}</span></div>
                        <div class="quota-row"><span>Est. Cost (paid rates)</span><span class="quota-value">$${run.estimated_cost_usd.toFixed(4)}</span></div>
                        <div class="quota-row"><span>Cache Hits</span><span class="quota-value">${run.cache_hits}</span></div>
                    </div>
                </div>
            </div>

            <div class="card mt-24">
                <div class="card-header">
                    <span class="card-title">Per-Case Results</span>
                    <button class="btn btn-secondary btn-sm" onclick="Router.navigate('#compare/${run.id}')">Compare with another run</button>
                </div>
                ${run.results.map((r, i) => `
                    <div class="result-row">
                        <div class="result-row-header" onclick="this.nextElementSibling.classList.toggle('expanded')">
                            <div class="truncate">${truncate(r.input_text, 60)}</div>
                            <div>${scorePill(r.correctness)}</div>
                            <div>${scorePill(r.relevance)}</div>
                            <div>${scorePill(r.coherence)}</div>
                            <div>${scorePill(r.hallucination_resistance)}</div>
                            <div class="mono" style="font-size:0.75rem">${r.latency_ms.toFixed(0)}ms</div>
                            <div style="color:var(--text-muted)">▼</div>
                        </div>
                        <div class="result-row-body">
                            <div class="flex gap-8 mb-16">
                                ${r.from_cache ? '<span class="badge badge-completed">CACHED</span>' : ''}
                                ${r.similarity_method ? `<span class="badge badge-pending">${r.similarity_method}</span>` : ''}
                            </div>
                            <label style="font-size:0.7rem; color:var(--text-muted); font-weight:700">INPUT</label>
                            <div class="result-output">${r.input_text}</div>
                            ${r.expected_output ? `
                                <label style="font-size:0.7rem; color:var(--text-muted); font-weight:700">EXPECTED</label>
                                <div class="result-output">${r.expected_output}</div>
                            ` : ''}
                            <label style="font-size:0.7rem; color:var(--text-muted); font-weight:700">ACTUAL OUTPUT</label>
                            <div class="result-output">${r.actual_output}</div>
                            <div class="result-reasoning">
                                <strong>Judge Reasoning:</strong> ${r.judge_reasoning}
                            </div>
                            <div class="flex gap-8 mt-16">
                                <span class="mono" style="font-size:0.75rem; color:var(--text-muted)">
                                    ROUGE-L: ${r.rouge_l != null ? r.rouge_l.toFixed(3) : '—'} |
                                    Similarity: ${r.semantic_similarity != null ? r.semantic_similarity.toFixed(3) : '—'} |
                                    Tokens: ${r.input_tokens}→${r.output_tokens}
                                </span>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        // Render radar chart
        renderRadarChart(run);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function renderRadarChart(run) {
    const ctx = document.getElementById('radar-chart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Correctness', 'Relevance', 'Coherence', 'Tone', 'Hallucination\nResistance'],
            datasets: [{
                label: run.model_id.split('/').pop().replace(':free', ''),
                data: [
                    run.avg_correctness || 0,
                    run.avg_relevance || 0,
                    run.avg_coherence || 0,
                    run.avg_tone || 0,
                    run.avg_hallucination_resistance || 0,
                ],
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.15)',
                borderWidth: 2,
                pointBackgroundColor: '#8b5cf6',
                pointRadius: 4,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: '#9494b8', font: { family: 'Inter' } } }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 10,
                    ticks: { stepSize: 2, color: '#5c5c7a', backdropColor: 'transparent', font: { size: 10 } },
                    grid: { color: 'rgba(99, 102, 241, 0.1)' },
                    pointLabels: { color: '#9494b8', font: { size: 11, family: 'Inter' } },
                    angleLines: { color: 'rgba(99, 102, 241, 0.1)' },
                }
            }
        }
    });
}

// ── Compare ───────────────────────────────────────────────────

async function renderCompare(params) {
    const preselectedRunId = params[0];

    content().innerHTML = `
        <div class="page-header">
            <h2>Compare Runs</h2>
            <p>Select two runs to compare side by side</p>
        </div>
        <div class="card">
            <div class="comparison-grid">
                <div class="form-group">
                    <label>Run A (Baseline)</label>
                    <select class="form-select" id="compare-a"></select>
                </div>
                <div class="form-group">
                    <label>Run B (New)</label>
                    <select class="form-select" id="compare-b"></select>
                </div>
            </div>
            <button class="btn btn-primary" onclick="runComparison()">Compare</button>
        </div>
        <div id="comparison-results" class="mt-24"></div>
    `;

    try {
        const runs = await API.getRuns();
        const completed = runs.filter(r => r.status === 'completed');
        const options = completed.map(r =>
            `<option value="${r.id}" ${r.id == preselectedRunId ? 'selected' : ''}>
                Run #${r.id} — ${r.model_id.split('/').pop().replace(':free', '')} (${r.suite_name})
            </option>`
        ).join('');

        $('#compare-a').innerHTML = '<option value="">Select baseline run</option>' + options;
        $('#compare-b').innerHTML = '<option value="">Select new run</option>' + options;

        // If preselected, auto-select the previous run as Run A
        if (preselectedRunId) {
            const idx = completed.findIndex(r => r.id == preselectedRunId);
            if (idx < completed.length - 1) {
                $('#compare-a').value = completed[idx + 1].id;
            }
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
}

window.runComparison = async function () {
    const runA = $('#compare-a').value;
    const runB = $('#compare-b').value;

    if (!runA || !runB) { showToast('Select both runs', 'error'); return; }
    if (runA === runB) { showToast('Select two different runs', 'error'); return; }

    try {
        const comp = await API.compare(runA, runB);
        const resultsDiv = $('#comparison-results');

        // Regression banner
        let bannerHtml = '';
        if (comp.has_regression) {
            bannerHtml = `
                <div class="regression-banner">
                    <span class="alert-icon">⚠️</span>
                    <div class="alert-text">
                        <strong>Regression detected:</strong> ${comp.regression_summary}
                    </div>
                </div>
            `;
        }

        resultsDiv.innerHTML = `
            ${bannerHtml}
            <div class="comparison-grid">
                <div class="card">
                    <div class="card-title" style="color:var(--text-accent)">Run A — Baseline</div>
                    <div style="font-size:0.82rem; color:var(--text-secondary); margin-top:4px">${comp.run_a_model}</div>
                    <div class="result-output" style="margin-top:8px; max-height:80px">${truncate(comp.run_a_prompt, 150)}</div>
                </div>
                <div class="card">
                    <div class="card-title" style="color:var(--text-accent)">Run B — New</div>
                    <div style="font-size:0.82rem; color:var(--text-secondary); margin-top:4px">${comp.run_b_model}</div>
                    <div class="result-output" style="margin-top:8px; max-height:80px">${truncate(comp.run_b_prompt, 150)}</div>
                </div>
            </div>

            <div class="card mt-24">
                <div class="card-title mb-16">Dimension Comparison</div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Dimension</th>
                            <th>Run A</th>
                            <th>Run B</th>
                            <th>Delta</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${comp.dimensions.map(d => `
                            <tr>
                                <td style="text-transform:capitalize; font-weight:500">${d.dimension.replace(/_/g, ' ')}</td>
                                <td class="mono">${d.run_a_score != null ? d.run_a_score.toFixed(2) : '—'}</td>
                                <td class="mono">${d.run_b_score != null ? d.run_b_score.toFixed(2) : '—'}</td>
                                <td>${deltaIndicator(d.delta)}</td>
                                <td>${d.is_regression ? '<span class="badge badge-failed">REGRESSION</span>' : '<span class="badge badge-completed">OK</span>'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>

            <div class="card mt-24">
                <div class="card-title mb-16">Per-Case Comparison</div>
                <div class="chart-container" style="max-width:100%">
                    <canvas id="comparison-chart"></canvas>
                </div>
                ${comp.case_comparisons.map(c => `
                    <div class="result-row">
                        <div class="result-row-header" onclick="this.nextElementSibling.classList.toggle('expanded')" style="grid-template-columns: 2fr 1fr 1fr 1fr 40px">
                            <div class="truncate">${truncate(c.input_text, 60)}</div>
                            <div>${scorePill(c.run_a_avg_score)}</div>
                            <div>${scorePill(c.run_b_avg_score)}</div>
                            <div>${deltaIndicator(c.delta)}</div>
                            <div style="color:var(--text-muted)">▼</div>
                        </div>
                        <div class="result-row-body">
                            <div class="comparison-grid">
                                <div>
                                    <label style="font-size:0.7rem; color:var(--text-muted); font-weight:700">RUN A OUTPUT</label>
                                    <div class="result-output">${c.run_a_output}</div>
                                </div>
                                <div>
                                    <label style="font-size:0.7rem; color:var(--text-muted); font-weight:700">RUN B OUTPUT</label>
                                    <div class="result-output">${c.run_b_output}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        // Render comparison bar chart
        renderComparisonChart(comp);
    } catch (err) {
        showToast(err.message, 'error');
    }
};

function renderComparisonChart(comp) {
    const ctx = document.getElementById('comparison-chart');
    if (!ctx) return;

    const labels = comp.dimensions
        .filter(d => d.dimension !== 'latency_ms')
        .map(d => d.dimension.replace(/_/g, ' '));
    const dataA = comp.dimensions
        .filter(d => d.dimension !== 'latency_ms')
        .map(d => d.run_a_score || 0);
    const dataB = comp.dimensions
        .filter(d => d.dimension !== 'latency_ms')
        .map(d => d.run_b_score || 0);

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: `Run A (${comp.run_a_model.split('/').pop()})`,
                    data: dataA,
                    backgroundColor: 'rgba(99, 102, 241, 0.6)',
                    borderColor: '#6366f1',
                    borderWidth: 1,
                    borderRadius: 4,
                },
                {
                    label: `Run B (${comp.run_b_model.split('/').pop()})`,
                    data: dataB,
                    backgroundColor: 'rgba(236, 72, 153, 0.6)',
                    borderColor: '#ec4899',
                    borderWidth: 1,
                    borderRadius: 4,
                },
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: '#9494b8', font: { family: 'Inter' } } }
            },
            scales: {
                x: {
                    ticks: { color: '#9494b8', font: { size: 10 } },
                    grid: { color: 'rgba(99, 102, 241, 0.06)' },
                },
                y: {
                    beginAtZero: true,
                    max: 10,
                    ticks: { color: '#5c5c7a', stepSize: 2 },
                    grid: { color: 'rgba(99, 102, 241, 0.06)' },
                }
            }
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// Initialize App
// ═══════════════════════════════════════════════════════════════

Router.register('#dashboard', () => renderDashboard());
Router.register('#suites', (params) => {
    if (params[0]) renderSuiteDetail(params[0]);
    else renderSuites();
});
Router.register('#run', () => renderRun());
Router.register('#results', (params) => renderResults(params));
Router.register('#compare', (params) => renderCompare(params));

// Nav click handlers
document.addEventListener('DOMContentLoaded', () => {
    $$('.nav-item').forEach(el => {
        el.addEventListener('click', () => Router.navigate(el.dataset.route));
    });

    // Load health status
    API.getHealth().then(h => renderProviderStatus(h.providers)).catch(() => { });

    Router.init();
});
