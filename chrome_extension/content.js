/**
 * content.js — NeuroResume Chrome Extension
 * Runs on job board pages, extracts job details,
 * injects a floating "Save to NeuroResume" button.
 */

(function() {
  'use strict';

  const NEURORESUME_PORT = 8502;  // FastAPI local server port
  const NEURORESUME_URL = `http://localhost:${NEURORESUME_PORT}`;

  // ─── Platform Detectors ──────────────────────────────────────────────────────
  const platforms = {
    linkedin: {
      match: () => window.location.hostname.includes('linkedin.com'),
      extract: extractLinkedIn
    },
    naukri: {
      match: () => window.location.hostname.includes('naukri.com'),
      extract: extractNaukri
    },
    indeed: {
      match: () => window.location.hostname.includes('indeed.com'),
      extract: extractIndeed
    },
    glassdoor: {
      match: () => window.location.hostname.includes('glassdoor'),
      extract: extractGlassdoor
    },
    wellfound: {
      match: () => window.location.hostname.includes('wellfound.com'),
      extract: extractWellfound
    },
    internshala: {
      match: () => window.location.hostname.includes('internshala.com'),
      extract: extractInternshala
    }
  };

  // ─── Extractors per Platform ─────────────────────────────────────────────────
  function extractLinkedIn() {
    const title = getText('.job-details-jobs-unified-top-card__job-title, h1.job-details-jobs-unified-top-card__job-title, .topcard__title');
    const company = getText('.job-details-jobs-unified-top-card__company-name a, .topcard__org-name-link');
    const location = getText('.job-details-jobs-unified-top-card__bullet, .topcard__flavor--bullet');
    const description = getText('.job-details-module__content, .description__text, .jobs-description__content');
    const url = window.location.href.split('?')[0];

    return { platform: 'LinkedIn', title, company, location, description: description.slice(0, 3000), url, job_type: '', salary: '' };
  }

  function extractNaukri() {
    const title = getText('.jd-header-title, h1.jd-header-title, .styles_jd-header-title__rZwM1');
    const company = getText('.jd-header-comp-name a, .comp-name');
    const location = getText('.location, .styles_jhc__loc__W0ZCH');
    const description = getText('.job-desc, .dang-inner-html, .styles_JD-section__description__xjbH0');
    const salary = getText('.salary, .styles_jhc__salary__jdfEC');
    const url = window.location.href;

    return { platform: 'Naukri', title, company, location, description: description.slice(0, 3000), url, job_type: '', salary };
  }

  function extractIndeed() {
    const title = getText('.jobsearch-JobInfoHeader-title, h1[class*="jobTitle"]');
    const company = getText('.icl-u-lg-mr--sm .icl-u-xs-mr--xs, [data-testid="inlineHeader-companyName"] a');
    const location = getText('[data-testid="job-location"], .icl-u-xs-mt--xs');
    const description = getText('#jobDescriptionText, .job-snippet');
    const salary = getText('.icl-u-xs-mt--xs.icl-u-textColor--secondary, [data-testid="attribute_snippet_testid"]');
    const url = window.location.href;

    return { platform: 'Indeed', title, company, location, description: description.slice(0, 3000), url, job_type: '', salary };
  }

  function extractGlassdoor() {
    const title = getText('[data-test="job-title"], .e1tk4kwz0');
    const company = getText('[data-test="employer-name"], .css-87uc0g');
    const location = getText('[data-test="location"], .css-1v5elnn');
    const description = getText('[data-test="jobDesc"], .desc');
    const salary = getText('[data-test="salary-estimate"]');
    const url = window.location.href;

    return { platform: 'Glassdoor', title, company, location, description: description.slice(0, 3000), url, job_type: '', salary };
  }

  function extractWellfound() {
    const title = getText('h1, .styles-module_component__Ycb9J');
    const company = getText('.company-name, [class*="company"]');
    const location = getText('[class*="location"]');
    const description = getText('.job-description, [class*="description"]');
    const salary = getText('[class*="compensation"], [class*="salary"]');
    const url = window.location.href;

    return { platform: 'Wellfound', title, company, location, description: description.slice(0, 3000), url, job_type: 'Full-time', salary };
  }

  function extractInternshala() {
    const title = getText('.profile-box h1, .internship-heading h1');
    const company = getText('.company-name a, .heading_4_5');
    const location = getText('.location_link, .other_detail_item .detail_name');
    const description = getText('#about-internship, .internship_other_details');
    const salary = getText('.stipend, #stipend1');
    const url = window.location.href;

    return { platform: 'Internshala', title, company, location, description: description.slice(0, 3000), url, job_type: 'Internship', salary };
  }

  // ─── DOM Helper ──────────────────────────────────────────────────────────────
  function getText(selectors) {
    const selectorList = selectors.split(', ');
    for (const sel of selectorList) {
      const el = document.querySelector(sel);
      if (el) return el.innerText.trim();
    }
    return '';
  }

  // ─── Detect Current Platform ─────────────────────────────────────────────────
  function detectPlatform() {
    for (const [name, platform] of Object.entries(platforms)) {
      if (platform.match()) return { name, extractor: platform.extract };
    }
    return null;
  }

  // ─── Inject Floating Button ──────────────────────────────────────────────────
  function injectButton() {
    if (document.getElementById('neuroresume-btn')) return;

    const btn = document.createElement('div');
    btn.id = 'neuroresume-btn';
    btn.innerHTML = `
      <div id="nr-widget" style="
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 999999;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      ">
        <button id="nr-main-btn" style="
          background: linear-gradient(135deg, #7c3aed, #6d28d9);
          color: white;
          border: none;
          border-radius: 50px;
          padding: 12px 20px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          box-shadow: 0 4px 20px rgba(124,58,237,0.5);
          display: flex;
          align-items: center;
          gap: 8px;
          transition: all 0.2s;
          white-space: nowrap;
        ">
          <span style="font-size: 18px;">🧠</span>
          <span id="nr-btn-text">Save to NeuroResume</span>
        </button>

        <div id="nr-status" style="
          display: none;
          background: #16161f;
          border: 1px solid #1e1e2e;
          border-radius: 12px;
          padding: 12px 16px;
          margin-bottom: 10px;
          font-size: 13px;
          color: #f1f5f9;
          max-width: 280px;
          box-shadow: 0 4px 20px rgba(0,0,0,0.4);
          position: absolute;
          bottom: 50px;
          right: 0;
        ">
          <div id="nr-status-text"></div>
          <div id="nr-action-btns" style="margin-top: 10px; display: flex; gap: 6px; flex-wrap: wrap;"></div>
        </div>
      </div>
    `;
    document.body.appendChild(btn);

    document.getElementById('nr-main-btn').addEventListener('click', handleMainClick);
    document.getElementById('nr-main-btn').addEventListener('mouseenter', () => {
      document.getElementById('nr-main-btn').style.transform = 'translateY(-2px)';
      document.getElementById('nr-main-btn').style.boxShadow = '0 6px 24px rgba(124,58,237,0.6)';
    });
    document.getElementById('nr-main-btn').addEventListener('mouseleave', () => {
      document.getElementById('nr-main-btn').style.transform = 'translateY(0)';
      document.getElementById('nr-main-btn').style.boxShadow = '0 4px 20px rgba(124,58,237,0.5)';
    });
  }

  // ─── Handle Button Click ──────────────────────────────────────────────────────
  async function handleMainClick() {
    const platform = detectPlatform();
    if (!platform) {
      showStatus('❌ No job detected on this page', 'error');
      return;
    }

    const btnText = document.getElementById('nr-btn-text');
    btnText.textContent = 'Capturing...';

    const jobData = platform.extractor();

    if (!jobData.title && !jobData.company) {
      showStatus('❌ Could not extract job details. Navigate to a specific job page.', 'error');
      btnText.textContent = 'Save to NeuroResume';
      return;
    }

    // Send to local NeuroResume server
    try {
      const response = await fetch(`${NEURORESUME_URL}/api/capture-job`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(jobData)
      });

      if (response.ok) {
        const result = await response.json();
        showStatus(
          `✅ Saved: ${jobData.title} @ ${jobData.company}`,
          'success',
          [
            { text: '⚡ Generate Resume', action: `${NEURORESUME_URL}/api/generate-resume?job_id=${result.job_id}` },
            { text: '📤 Add to Queue', action: `${NEURORESUME_URL}/api/add-to-queue?job_id=${result.job_id}` },
            { text: '🧠 Open App', action: 'http://localhost:8501' },
          ]
        );
        btnText.textContent = '✅ Saved!';

        // Notify via chrome notifications
        chrome.runtime.sendMessage({
          type: 'job_captured',
          title: jobData.title,
          company: jobData.company,
          job_id: result.job_id
        });
      } else {
        throw new Error(`Server returned ${response.status}`);
      }
    } catch (error) {
      // Server not running — save to extension storage
      const stored = await chrome.storage.local.get('pending_jobs') || {};
      const pending = stored.pending_jobs || [];
      pending.push({ ...jobData, captured_at: new Date().toISOString() });
      await chrome.storage.local.set({ pending_jobs: pending });

      showStatus(
        `📦 Saved locally (${jobData.title} @ ${jobData.company}). Open NeuroResume to sync.`,
        'warning'
      );
      btnText.textContent = '📦 Saved Locally';
    }

    // Reset button after 3s
    setTimeout(() => { btnText.textContent = 'Save to NeuroResume'; }, 3000);
  }

  // ─── Show Status Popup ────────────────────────────────────────────────────────
  function showStatus(message, type, actions = []) {
    const statusDiv = document.getElementById('nr-status');
    const statusText = document.getElementById('nr-status-text');
    const actionBtns = document.getElementById('nr-action-btns');

    const colors = {
      success: '#10b981',
      error: '#ef4444',
      warning: '#f59e0b',
      info: '#7c3aed'
    };

    statusText.innerHTML = `<span style="color: ${colors[type] || '#f1f5f9'};">${message}</span>`;
    actionBtns.innerHTML = '';

    if (actions.length > 0) {
      actions.forEach(action => {
        const a = document.createElement('a');
        a.href = action.action;
        a.target = '_blank';
        a.style.cssText = `
          background: rgba(124,58,237,0.15);
          border: 1px solid rgba(124,58,237,0.35);
          color: #a78bfa;
          text-decoration: none;
          padding: 4px 10px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 500;
          display: inline-block;
        `;
        a.textContent = action.text;
        actionBtns.appendChild(a);
      });
    }

    statusDiv.style.display = 'block';
    setTimeout(() => { statusDiv.style.display = 'none'; }, 8000);
  }

  // ─── Auto-detect and inject ───────────────────────────────────────────────────
  function init() {
    const platform = detectPlatform();
    if (!platform) return;

    // Wait for job content to load
    const observer = new MutationObserver((mutations, obs) => {
      const platform = detectPlatform();
      if (!platform) return;
      const test = platform.extractor();
      if (test.title || test.company) {
        injectButton();
        obs.disconnect();
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Also try immediately
    setTimeout(injectButton, 1500);
    setTimeout(injectButton, 3000);
  }

  init();

  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'get_job_data') {
      const platform = detectPlatform();
      if (platform) {
        sendResponse({ job: platform.extractor(), platform_name: platform.name });
      } else {
        sendResponse({ job: null });
      }
    }
  });

})();
