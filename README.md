# NeuroResume — Autonomous AI Career Agent
## Phase 1 + Phase 2: Resume Engine + Job Scraper

---

## What This Does

### Phase 1 — Resume Engine
- Paste your resume + any job description
- Grok-3 rewrites it to perfectly match the JD
- Custom ATS scoring engine (100-point system) loops until score hits your target
- Compiles professional PDF via LaTeX

### Phase 2 — Job Scraper (NEW)
- Scrapes 5 platforms: LinkedIn, Naukri, Indeed, Internshala, Wellfound
- All jobs saved to local SQLite database
- Dashboard with stats, filters, status tracking
- One-click bridge: click "Generate Resume" on any job -> auto-loads into Phase 1

---

## Quick Setup

### Step 1 — Install Python Dependencies
```
pip install -r requirements.txt
```

### Step 2 — Install Playwright Browsers
```
playwright install chromium
```

### Step 3 — Install LaTeX (Windows PowerShell as Admin)
```
winget install tectonic-typesetting.tectonic
```

### Step 4 — Add Grok API Key
```
copy .env.example .env
```
Open .env and add:  GROK_API_KEY=xai-xxxxxxxxxxxxxxxxxxxx
Get key from: https://console.x.ai

### Step 5 — Run
```
streamlit run app.py
```
Opens at: http://localhost:8501

---

## File Structure

```
resume_agent/
├── app.py                      <- Main entry point
├── phase2_app.py               <- Phase 2 UI
├── grok_engine.py              <- Grok-3 API
├── ats_scorer.py               <- ATS scoring engine
├── prompt_template.py          <- Optimization prompts
├── pdf_generator.py            <- LaTeX to PDF
├── scraper_engine.py           <- Scraping orchestrator
├── database.py                 <- SQLite layer
├── scrapers/
│   ├── base_scraper.py
│   ├── linkedin_scraper.py
│   ├── naukri_scraper.py
│   ├── indeed_scraper.py
│   └── internshala_scraper.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## How Phase 1 + Phase 2 Connect

Phase 2 scrapes jobs from 5 platforms
-> Jobs saved in SQLite database
-> Click "Generate Resume" on any job card
-> Job description auto-loads into Phase 1
-> Grok-3 optimizes resume for that exact job
-> ATS loop runs until target score
-> PDF downloaded

---

## ATS Scoring

Keyword Match: 40pts | Section Presence: 20pts | Power Verbs: 15pts | Quantification: 15pts | Contact: 10pts

---

## Troubleshooting

- "GROK_API_KEY not found" -> Create .env from .env.example
- "No LaTeX compiler" -> winget install tectonic-typesetting.tectonic
- "playwright install chromium fails" -> Run PowerShell as Administrator
- "No jobs found" -> Try different keywords, retry after few minutes
- "PDF failed" -> Paste LaTeX code at overleaf.com

---

## Coming Next (Phase 3+)
Auto-apply, Cover letters, Gmail monitoring, Interview prep, Salary intel, Voice interface, Chrome extension
