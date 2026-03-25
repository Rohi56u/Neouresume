/**
 * popup.js — NeuroResume Chrome Extension Popup Logic
 */

const NEURORESUME_API = 'http://localhost:8502';
const STREAMLIT_URL   = 'http://localhost:8501';

let currentJob = null;
let serverOnline = false;

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  await checkServerStatus();
  await getCurrentTabJob();
  await loadStats();
  await loadPendingJobs();
}

// ─── Server Health Check ──────────────────────────────────────────────────────
async function checkServerStatus() {
  try {
    const resp = await fetch(`${NEURORESUME_API}/health`, { signal: AbortSignal.timeout(2000) });
    serverOnline = resp.ok;
  } catch {
    serverOnline = false;
  }

  const dot = document.getElementById('statusDot');
  const text = document.getElementById('serverStatusText');

  if (serverOnline) {
    dot.classList.add('connected');
    text.textContent = 'Server online';
    text.style.color = '#10b981';
  } else {
    text.textContent = 'Server offline — run app.py';
    text.style.color = '#f59e0b';
  }
}

// ─── Get Job from Active Tab ──────────────────────────────────────────────────
async function getCurrentTabJob() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  // Check if it's a job board
  const jobBoards = ['linkedin.com/jobs', 'naukri.com', 'indeed.com', 'glassdoor', 'wellfound.com', 'internshala.com'];
  const isJobBoard = jobBoards.some(b => tab.url && tab.url.includes(b));

  if (!isJobBoard) {
    showNoJob();
    return;
  }

  // Ask content script for job data
  try {
    const response = await chrome.tabs.sendMessage(tab.id, { type: 'get_job_data' });
    if (response && response.job && (response.job.title || response.job.company)) {
      currentJob = response.job;
      showJobCard(response.job, response.platform_name);
    } else {
      showNoJob();
    }
  } catch {
    showNoJob();
  }
}

// ─── Show Job Card ────────────────────────────────────────────────────────────
function showJobCard(job, platform) {
  const section = document.getElementById('jobSection');
  section.innerHTML = `
    <div class="job-card">
      <div class="job-card-label">📍 Detected Job — ${platform || job.platform || 'Job Board'}</div>
      <div class="job-title">${job.title || 'Unknown Role'}</div>
      <div class="job-company">${job.company || 'Unknown Company'}</div>
      <div class="job-meta">
        ${job.location ? `<span class="meta-chip">📍 ${job.location.slice(0, 25)}</span>` : ''}
        ${job.salary ? `<span class="meta-chip">💰 ${job.salary.slice(0, 20)}</span>` : ''}
        ${job.job_type ? `<span class="meta-chip">${job.job_type}</span>` : ''}
      </div>
    </div>

    <div class="actions">
      <button class="action-btn btn-primary" id="saveBtn">
        <span>💾</span> Save to NeuroResume
      </button>
      <button class="action-btn btn-secondary" id="resumeBtn">
        <span>🧠</span> Generate AI Resume
      </button>
      <button class="action-btn btn-green" id="queueBtn">
        <span>📤</span> Add to Apply Queue
      </button>
      <button class="action-btn btn-cyan" id="coverBtn">
        <span>✍️</span> Generate Cover Letter
      </button>
    </div>
    <div class="divider"></div>
  `;

  document.getElementById('saveBtn').addEventListener('click', () => saveJob(job));
  document.getElementById('resumeBtn').addEventListener('click', () => generateResume(job));
  document.getElementById('queueBtn').addEventListener('click', () => addToQueue(job));
  document.getElementById('coverBtn').addEventListener('click', () => generateCoverLetter(job));
}

// ─── Show No Job ──────────────────────────────────────────────────────────────
function showNoJob() {
  document.getElementById('jobSection').innerHTML = `
    <div class="no-job">
      <div class="no-job-icon">🔍</div>
      <strong style="color:#f1f5f9;">No job detected</strong><br>
      Navigate to a job listing on LinkedIn, Naukri, Indeed, Glassdoor, or Wellfound.
    </div>
    <div class="divider"></div>
  `;
}

// ─── Actions ──────────────────────────────────────────────────────────────────
async function saveJob(job) {
  try {
    if (serverOnline) {
      const resp = await fetch(`${NEURORESUME_API}/api/capture-job`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(job)
      });
      const result = await resp.json();
      currentJob.job_id = result.job_id;
      showToast(`✅ Saved: ${job.title} @ ${job.company}`);
    } else {
      // Offline storage
      const stored = await chrome.storage.local.get('pending_jobs');
      const pending = stored.pending_jobs || [];
      pending.push({ ...job, captured_at: new Date().toISOString() });
      await chrome.storage.local.set({ pending_jobs: pending });
      showToast('📦 Saved locally — sync when server is running');
    }
  } catch (e) {
    showToast('❌ Error saving job');
  }
}

async function generateResume(job) {
  await saveJob(job);
  if (currentJob.job_id) {
    chrome.tabs.create({ url: `${STREAMLIT_URL}?tab=phase1&job_id=${currentJob.job_id}` });
  } else {
    chrome.tabs.create({ url: STREAMLIT_URL });
  }
  window.close();
}

async function addToQueue(job) {
  await saveJob(job);
  if (serverOnline && currentJob.job_id) {
    await fetch(`${NEURORESUME_API}/api/add-to-queue?job_id=${currentJob.job_id}`);
    showToast('✅ Added to apply queue!');
  } else {
    chrome.tabs.create({ url: `${STREAMLIT_URL}?tab=phase3` });
    window.close();
  }
}

async function generateCoverLetter(job) {
  await saveJob(job);
  if (currentJob.job_id) {
    chrome.tabs.create({ url: `${STREAMLIT_URL}?tab=phase4&job_id=${currentJob.job_id}` });
  } else {
    chrome.tabs.create({ url: `${STREAMLIT_URL}?tab=phase4` });
  }
  window.close();
}

// ─── Stats Section ────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    if (!serverOnline) return;
    const resp = await fetch(`${NEURORESUME_API}/api/stats`);
    const stats = await resp.json();

    document.getElementById('statsSection').innerHTML = `
      <div class="stats-row">
        <div class="stat-box">
          <div class="stat-num" style="color:#7c3aed;">${stats.total_jobs || 0}</div>
          <div class="stat-lbl">Jobs</div>
        </div>
        <div class="stat-box">
          <div class="stat-num" style="color:#10b981;">${stats.interviews || 0}</div>
          <div class="stat-lbl">Interviews</div>
        </div>
        <div class="stat-box">
          <div class="stat-num" style="color:#f59e0b;">${stats.total_applications || 0}</div>
          <div class="stat-lbl">Applied</div>
        </div>
      </div>
      <div class="divider"></div>
    `;
  } catch { /* server not ready */ }
}

// ─── Pending Jobs Section ─────────────────────────────────────────────────────
async function loadPendingJobs() {
  const stored = await chrome.storage.local.get('pending_jobs');
  const pending = stored.pending_jobs || [];

  if (pending.length === 0) return;

  const section = document.getElementById('pendingSection');
  section.innerHTML = `
    <div class="pending-section">
      <div class="pending-label">📦 ${pending.length} Offline Jobs — Ready to Sync</div>
      ${pending.slice(-3).map(j => `
        <div class="pending-item">
          <strong style="color:#f1f5f9;">${j.title || 'Unknown'}</strong> @ ${j.company || '?'}
          <div style="font-size:0.7rem; color:#475569; margin-top:2px;">${j.platform || ''} · ${j.captured_at ? j.captured_at.slice(0,10) : ''}</div>
        </div>
      `).join('')}
      ${serverOnline ? `<button class="action-btn btn-secondary" id="syncBtn" style="margin-top:4px;">🔄 Sync All to NeuroResume</button>` : ''}
    </div>
    <div class="divider"></div>
  `;

  if (serverOnline) {
    document.getElementById('syncBtn').addEventListener('click', syncPendingJobs);
  }
}

async function syncPendingJobs() {
  const stored = await chrome.storage.local.get('pending_jobs');
  const pending = stored.pending_jobs || [];
  let synced = 0;

  for (const job of pending) {
    try {
      await fetch(`${NEURORESUME_API}/api/capture-job`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(job)
      });
      synced++;
    } catch { break; }
  }

  if (synced > 0) {
    await chrome.storage.local.set({ pending_jobs: [] });
    showToast(`✅ Synced ${synced} jobs to NeuroResume!`);
    setTimeout(loadPendingJobs, 1000);
  }
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}

// ─── Start ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
