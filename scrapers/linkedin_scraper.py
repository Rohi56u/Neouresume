"""
scrapers/linkedin_scraper.py
LinkedIn job scraper using Playwright with stealth mode.
Handles infinite scroll, job detail extraction, anti-bot detection.
"""

import time
import random
import json
from typing import List, Dict, Optional
from datetime import datetime

from .base_scraper import BaseScraper


class LinkedInScraper(BaseScraper):
    """
    Scrapes LinkedIn Jobs using Playwright browser automation.
    Uses stealth techniques to avoid bot detection.
    """

    BASE_URL = "https://www.linkedin.com/jobs/search/"

    def __init__(self):
        super().__init__(delay_range=(3, 7))
        self._playwright = None
        self._browser = None
        self._page = None

    @property
    def platform_name(self) -> str:
        return "LinkedIn"

    # ── Browser Setup ──────────────────────────────────────────────────────────
    def _init_browser(self):
        """Initialize Playwright browser with stealth settings."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "Playwright not installed!\n"
                "Run: pip install playwright && playwright install chromium"
            )

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1920,1080",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )

        # Create context with realistic browser fingerprint
        context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=self._get_random_ua(),
            locale="en-US",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
            }
        )

        # Inject stealth scripts
        context.add_init_script("""
            // Override webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'hi']
            });
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        self._page = context.new_page()

        # Random mouse movement on load
        self._page.add_init_script("""
            document.addEventListener('mousemove', () => {});
        """)

    def _close_browser(self):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    # ── Human-like Interactions ────────────────────────────────────────────────
    def _human_scroll(self, page):
        """Scroll like a human — variable speed, pauses."""
        total_height = page.evaluate("document.body.scrollHeight")
        viewport_height = page.viewport_size["height"]
        current_pos = 0

        while current_pos < total_height:
            scroll_amount = random.randint(200, 500)
            current_pos = min(current_pos + scroll_amount, total_height)
            page.evaluate(f"window.scrollTo(0, {current_pos})")
            time.sleep(random.uniform(0.1, 0.4))

            # Occasionally pause longer (like reading)
            if random.random() < 0.2:
                time.sleep(random.uniform(0.5, 1.5))

    def _human_type(self, element, text: str):
        """Type text with human-like delays."""
        for char in text:
            element.type(char)
            time.sleep(random.uniform(0.05, 0.15))

    # ── Main Scrape ────────────────────────────────────────────────────────────
    def scrape(self, query: str, location: str = "India", max_jobs: int = 20) -> List[Dict]:
        """
        Scrape LinkedIn jobs for given query and location.
        Returns list of normalized job dicts.
        """
        jobs = []

        try:
            self._init_browser()
            page = self._page

            # Build search URL
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            encoded_location = urllib.parse.quote(location)
            url = (
                f"{self.BASE_URL}"
                f"?keywords={encoded_query}"
                f"&location={encoded_location}"
                f"&f_TPR=r604800"  # Last 7 days
                f"&sortBy=R"       # Relevance
            )

            print(f"  [LinkedIn] Navigating to search page...")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self._random_delay()

            # Scroll to load more jobs
            self._human_scroll(page)
            self._random_delay()

            # Get all job cards
            job_cards = page.query_selector_all(".job-search-card, .base-card, [data-entity-urn]")

            if not job_cards:
                # Try alternative selector
                job_cards = page.query_selector_all("li.jobs-search-results__list-item")

            print(f"  [LinkedIn] Found {len(job_cards)} job cards")

            scraped_count = 0
            for card in job_cards[:max_jobs]:
                if scraped_count >= max_jobs:
                    break

                try:
                    job = self._extract_card_data(page, card)
                    if job and job.get("title") and job.get("company"):
                        normalized = self._normalize_job(job)
                        jobs.append(normalized)
                        scraped_count += 1
                        print(f"  [LinkedIn] ✓ {job.get('title')} @ {job.get('company')}")
                except Exception as e:
                    self.errors.append(f"Card extraction error: {str(e)}")
                    continue

                self._random_delay()

        except Exception as e:
            error_msg = f"LinkedIn scraper error: {str(e)}"
            self.errors.append(error_msg)
            print(f"  [LinkedIn] ✗ {error_msg}")
        finally:
            self._close_browser()

        return jobs

    def _extract_card_data(self, page, card) -> Optional[Dict]:
        """Extract data from a single job card and its detail page."""
        try:
            # Get basic info from card
            title_el = card.query_selector(".base-search-card__title, h3.base-card__full-link, .job-card-list__title")
            company_el = card.query_selector(".base-search-card__subtitle, h4.base-card__subtitle, .job-card-container__primary-description")
            location_el = card.query_selector(".job-search-card__location, .job-card-container__metadata-item")
            link_el = card.query_selector("a.base-card__full-link, a[href*='/jobs/view/']")

            title = title_el.inner_text().strip() if title_el else ""
            company = company_el.inner_text().strip() if company_el else ""
            location = location_el.inner_text().strip() if location_el else ""
            url = link_el.get_attribute("href") if link_el else ""

            if not title or not url:
                return None

            # Clean URL — remove tracking params
            if "?" in url:
                url = url.split("?")[0]

            # Click to get full description
            description = ""
            salary = ""
            job_type = ""
            experience = ""

            try:
                if link_el:
                    link_el.click()
                    page.wait_for_selector(".jobs-description, .description__text", timeout=8000)
                    self._random_delay()

                    desc_el = page.query_selector(".jobs-description__content, .description__text, .show-more-less-html__markup")
                    if desc_el:
                        description = desc_el.inner_text()

                    # Try to get metadata
                    criteria = page.query_selector_all(".job-criteria__item, .description__job-criteria-item")
                    for item in criteria:
                        label_el = item.query_selector(".job-criteria__subheader, h3")
                        value_el = item.query_selector(".job-criteria__text, span.description__job-criteria-text")
                        if label_el and value_el:
                            label = label_el.inner_text().strip().lower()
                            value = value_el.inner_text().strip()
                            if "seniority" in label or "experience" in label:
                                experience = value
                            elif "employment" in label or "type" in label:
                                job_type = value
            except Exception:
                pass  # Description fetch failed, still return basic data

            skills = self._extract_skills_from_text(description or title)

            return {
                "platform": "LinkedIn",
                "title": title,
                "company": company,
                "location": location,
                "description": description,
                "url": f"https://www.linkedin.com{url}" if url.startswith("/") else url,
                "salary": salary,
                "job_type": job_type,
                "experience": experience,
                "skills": skills,
                "posted_date": datetime.now().strftime("%Y-%m-%d")
            }

        except Exception as e:
            return None
