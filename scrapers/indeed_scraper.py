"""
scrapers/indeed_scraper.py
Indeed.com job scraper using requests + BeautifulSoup.
Handles Indeed's search result pages and job detail pages.
"""

import requests
import re
import time
import random
import urllib.parse
from typing import List, Dict, Optional
from datetime import datetime

from .base_scraper import BaseScraper


class IndeedScraper(BaseScraper):
    """
    Scrapes Indeed.com job listings.
    Uses requests + BeautifulSoup with rotating user agents.
    """

    BASE_URL = "https://in.indeed.com"
    SEARCH_URL = "https://in.indeed.com/jobs"

    def __init__(self):
        super().__init__(delay_range=(2, 5))
        self._session = requests.Session()

    @property
    def platform_name(self) -> str:
        return "Indeed"

    def _init_session(self):
        self._session.headers.update(self._get_headers(self.BASE_URL))
        try:
            self._session.get(self.BASE_URL, timeout=15)
            time.sleep(random.uniform(1, 2))
        except Exception:
            pass

    def scrape(self, query: str, location: str = "India", max_jobs: int = 20) -> List[Dict]:
        """Scrape Indeed India jobs."""
        jobs = []

        try:
            self._init_session()
            params = {
                "q": query,
                "l": location,
                "sort": "relevance",
                "fromage": "14",    # Last 14 days
                "limit": min(max_jobs, 25),
            }

            print(f"  [Indeed] Searching: {query} in {location}")

            response = self._session.get(
                self.SEARCH_URL,
                params=params,
                timeout=20,
                headers=self._get_headers(self.BASE_URL)
            )

            if response.status_code == 200:
                jobs = self._parse_results(response.text, max_jobs)
            elif response.status_code == 403:
                self.errors.append("Indeed: Access blocked (403). Try again later or use VPN.")
            else:
                self.errors.append(f"Indeed: HTTP {response.status_code}")

        except requests.exceptions.ConnectionError:
            self.errors.append("Indeed: Connection failed")
        except requests.exceptions.Timeout:
            self.errors.append("Indeed: Request timed out")
        except Exception as e:
            self.errors.append(f"Indeed error: {str(e)}")

        return jobs

    def _parse_results(self, html: str, max_jobs: int) -> List[Dict]:
        """Parse Indeed search results HTML."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("Run: pip install beautifulsoup4")

        jobs = []
        soup = BeautifulSoup(html, "html.parser")

        # Indeed job cards
        job_cards = soup.find_all("div", class_=lambda x: x and "job_seen_beacon" in str(x))
        if not job_cards:
            job_cards = soup.find_all("td", class_="resultContent")
        if not job_cards:
            job_cards = soup.find_all("div", attrs={"data-jk": True})

        print(f"  [Indeed] Found {len(job_cards)} job cards")

        for card in job_cards[:max_jobs]:
            try:
                job = self._parse_card(card)
                if job and job.get("title"):
                    normalized = self._normalize_job(job)
                    jobs.append(normalized)
                    print(f"  [Indeed] ✓ {job.get('title')} @ {job.get('company')}")
                    self._random_delay()
            except Exception:
                continue

        return jobs

    def _parse_card(self, card) -> Optional[Dict]:
        """Extract data from single Indeed job card."""
        try:
            from bs4 import BeautifulSoup

            # Title
            title_el = card.find("h2", class_=lambda x: x and "jobTitle" in str(x))
            if not title_el:
                title_el = card.find("a", attrs={"data-jk": True})

            # Company
            company_el = card.find("span", class_=lambda x: x and "companyName" in str(x))
            if not company_el:
                company_el = card.find(attrs={"data-testid": "company-name"})

            # Location
            location_el = card.find("div", class_=lambda x: x and "companyLocation" in str(x))
            if not location_el:
                location_el = card.find(attrs={"data-testid": "text-location"})

            # Salary
            salary_el = card.find("div", class_=lambda x: x and "salary" in str(x).lower())

            # Job snippet / description
            snippet_el = card.find("div", class_=lambda x: x and ("job-snippet" in str(x) or "jobCardShelfContainer" in str(x)))

            title = ""
            if title_el:
                span = title_el.find("span")
                title = self._clean_text(span.get_text() if span else title_el.get_text())

            company = self._clean_text(company_el.get_text() if company_el else "")
            location = self._clean_text(location_el.get_text() if location_el else "")
            salary = self._clean_text(salary_el.get_text() if salary_el else "")
            description = self._clean_text(snippet_el.get_text() if snippet_el else "")

            # Build URL
            job_key = card.get("data-jk", "")
            if not job_key:
                link = card.find("a", attrs={"data-jk": True})
                if link:
                    job_key = link.get("data-jk", "")

            url = f"{self.BASE_URL}/viewjob?jk={job_key}" if job_key else ""

            # Try to get full description
            if job_key and len(description) < 100:
                full_desc = self._fetch_job_detail(job_key)
                if full_desc:
                    description = full_desc

            skills = self._extract_skills_from_text(description)

            return {
                "platform": "Indeed",
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "description": description,
                "url": url,
                "skills": skills,
                "job_type": "",
                "experience": "",
                "posted_date": datetime.now().strftime("%Y-%m-%d")
            }
        except Exception:
            return None

    def _fetch_job_detail(self, job_key: str) -> str:
        """Fetch full job description from job detail page."""
        try:
            self._random_delay()
            url = f"{self.BASE_URL}/viewjob?jk={job_key}"
            response = self._session.get(
                url,
                timeout=15,
                headers=self._get_headers(self.SEARCH_URL)
            )

            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")

                desc_el = soup.find("div", id="jobDescriptionText")
                if not desc_el:
                    desc_el = soup.find("div", class_=lambda x: x and "jobDescription" in str(x))

                if desc_el:
                    return self._clean_description(desc_el.get_text())
        except Exception:
            pass
        return ""
