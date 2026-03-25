/**
 * background.js — NeuroResume Extension Service Worker
 * Handles notifications and context menus.
 */

chrome.runtime.onInstalled.addListener(() => {
  // Context menu for right-click on job pages
  chrome.contextMenus.create({
    id: 'neuroresume-save',
    title: '🧠 Save Job to NeuroResume',
    contexts: ['page'],
    documentUrlPatterns: [
      'https://www.linkedin.com/jobs/*',
      'https://www.naukri.com/*',
      'https://in.indeed.com/*',
      'https://www.glassdoor.co.in/*',
      'https://wellfound.com/jobs/*',
      'https://internshala.com/*',
    ]
  });

  chrome.contextMenus.create({
    id: 'neuroresume-open',
    title: '🧠 Open NeuroResume',
    contexts: ['page']
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'neuroresume-save') {
    chrome.tabs.sendMessage(tab.id, { type: 'get_job_data' }, async (response) => {
      if (response && response.job) {
        try {
          await fetch('http://localhost:8502/api/capture-job', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(response.job)
          });
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon48.png',
            title: 'NeuroResume',
            message: `✅ Saved: ${response.job.title} @ ${response.job.company}`
          });
        } catch {
          // Store offline
          const stored = await chrome.storage.local.get('pending_jobs');
          const pending = stored.pending_jobs || [];
          pending.push({ ...response.job, captured_at: new Date().toISOString() });
          await chrome.storage.local.set({ pending_jobs: pending });
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon48.png',
            title: 'NeuroResume',
            message: `📦 Saved locally: ${response.job.title} @ ${response.job.company}`
          });
        }
      }
    });
  }

  if (info.menuItemId === 'neuroresume-open') {
    chrome.tabs.create({ url: 'http://localhost:8501' });
  }
});

// Handle messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'job_captured') {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon48.png',
      title: 'NeuroResume — Job Captured!',
      message: `${message.title} @ ${message.company}`,
      buttons: [
        { title: '⚡ Generate Resume' },
        { title: '📤 Add to Queue' }
      ]
    });
  }
});

chrome.notifications.onButtonClicked.addListener((notifId, btnIndex) => {
  if (btnIndex === 0) {
    chrome.tabs.create({ url: 'http://localhost:8501?tab=phase1' });
  } else if (btnIndex === 1) {
    chrome.tabs.create({ url: 'http://localhost:8501?tab=phase3' });
  }
});
