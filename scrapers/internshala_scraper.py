"""
scrapers/internshala_scraper.py
Internshala.com job + internship scraper.
Also includes Wellfound (AngelList) scraper for startup jobs.
"""

import requests
import json
import time
import random
import re
import urllib.parse
from typing import List, Dict, Optional
from datetime import datetime

from .base_scraper import BaseScraper


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNSHALA SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

class IntershalaScraper(BaseScraper):
    """
    Scrapes Internshala jobs (great for freshers / entry level).
    Uses their search API which returns JSON.
    """

    BASE_URL = "https://internshala.com"
    JOBS_URL = "https://internshala.com/jobs"

    def __init__(self):
        super().__init__(delay_range=(1, 3))
        self._session = requests.Session()

    @property
    def platform_name(self) -> str:
        return "Internshala"

    def scrape(self, query: str, location: str = "India", max_jobs: int = 20) -> List[Dict]:
        jobs = []

        try:
            headers = self._get_headers(self.BASE_URL)
            headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
            headers["X-Requested-With"] = "XMLHttpRequest"

            # Internshala search endpoint
            query_slug = urllib.parse.quote(query.lower().replace(" ", "-"))
            location_slug = urllib.parse.quote(location.lower().replace(" ", "-"))

            search_url = f"{self.JOBS_URL}/keywords-{query_slug}"

            print(f"  [Internshala] Searching: {query}")

            response = self._session.get(
                search_url,
                headers=headers,
                timeout=15
            )

            if response.status_code == 200:
                jobs = self._parse_response(response.text, max_jobs)
            else:
                self.errors.append(f"Internshala: HTTP {response.status_code}")

        except Exception as e:
            self.errors.append(f"Internshala error: {str(e)}")

        return jobs

    def _parse_response(self, html: str, max_jobs: int) -> List[Dict]:
        """Parse Internshala HTML or JSON response."""
        jobs = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Internshala job containers
            job_cards = soup.find_all("div", class_=lambda x: x and "individual_internship" in str(x))
            if not job_cards:
                job_cards = soup.find_all("div", attrs={"data-internship_id": True})
            if not job_cards:
                job_cards = soup.find_all("div", class_=lambda x: x and "job-internship-card" in str(x))

            print(f"  [Internshala] Found {len(job_cards)} cards")

            for card in job_cards[:max_jobs]:
                try:
                    job = self._parse_card(card)
                    if job and job.get("title"):
                        jobs.append(self._normalize_job(job))
                        print(f"  [Internshala] ✓ {job['title']} @ {job['company']}")
                        self._random_delay()
                except Exception:
                    continue

            # If no cards found via HTML, try JSON embedded in page
            if not jobs:
                jobs = self._extract_json_data(soup, max_jobs)

        except Exception as e:
            self.errors.append(f"Internshala parse error: {str(e)}")

        return jobs

    def _parse_card(self, card) -> Optional[Dict]:
        """Extract job data from Internshala card."""
        try:
            from bs4 import BeautifulSoup

            title_el = card.find(class_=lambda x: x and ("profile" in str(x).lower() or "title" in str(x).lower()))
            company_el = card.find(class_=lambda x: x and "company_name" in str(x).lower())
            location_el = card.find(class_=lambda x: x and ("location_link" in str(x) or "location" in str(x).lower()))
            salary_el = card.find(class_=lambda x: x and ("stipend" in str(x).lower() or "salary" in str(x).lower()))
            duration_el = card.find(class_=lambda x: x and "duration" in str(x).lower())

            title = self._clean_text(title_el.get_text() if title_el else "")
            company = self._clean_text(company_el.get_text() if company_el else "")
            location = self._clean_text(location_el.get_text() if location_el else "Work From Home")
            salary = self._clean_text(salary_el.get_text() if salary_el else "")
            duration = self._clean_text(duration_el.get_text() if duration_el else "")

            # URL
            link = card.find("a", href=True)
            url = ""
            if link:
                href = link["href"]
                url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

            # Description from card content
            desc_parts = [f"Role: {title}", f"Company: {company}"]
            if location:
                desc_parts.append(f"Location: {location}")
            if salary:
                desc_parts.append(f"Compensation: {salary}")
            if duration:
                desc_parts.append(f"Duration: {duration}")

            # Skills from card
            skills_el = card.find_all(class_=lambda x: x and ("skill" in str(x).lower() or "tag" in str(x).lower()))
            skills = [self._clean_text(s.get_text()) for s in skills_el if s.get_text().strip()][:10]

            description = "\n".join(desc_parts)
            all_skills = list(set(skills + self._extract_skills_from_text(description)))

            return {
                "platform": "Internshala",
                "title": title,
                "company": company,
                "location": location or "Remote/Work From Home",
                "salary": salary,
                "description": description,
                "url": url,
                "skills": all_skills,
                "job_type": "Internship/Job",
                "experience": "0-2 years",
                "posted_date": datetime.now().strftime("%Y-%m-%d")
            }
        except Exception:
            return None

    def _extract_json_data(self, soup, max_jobs: int) -> List[Dict]:
        """Try to extract jobs from embedded JSON in page scripts."""
        jobs = []
        for script in soup.find_all("script"):
            text = script.string or ""
            if "internship_meta" in text or "job_meta" in text:
                try:
                    matches = re.findall(r'\{[^{}]*"title"[^{}]*\}', text)
                    for match in matches[:max_jobs]:
                        try:
                            data = json.loads(match)
                            if data.get("title"):
                                jobs.append(self._normalize_job({
                                    "platform": "Internshala",
                                    "title": data.get("title", ""),
                                    "company": data.get("company_name", ""),
                                    "location": data.get("location", ""),
                                    "salary": data.get("stipend", ""),
                                    "description": data.get("description", ""),
                                    "url": data.get("url", ""),
                                    "skills": [],
                                    "job_type": "Internship",
                                    "experience": "0-1 years",
                                    "posted_date": datetime.now().strftime("%Y-%m-%d")
                                }))
                        except Exception:
                            continue
                except Exception:
                    continue
        return jobs


# ═══════════════════════════════════════════════════════════════════════════════
# WELLFOUND (AngelList) SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

class WellfoundScraper(BaseScraper):
    """
    Scrapes Wellfound.com (AngelList Talent) for startup jobs.
    Great for tech startup roles.
    """

    BASE_URL = "https://wellfound.com"
    SEARCH_URL = "https://wellfound.com/jobs"

    def __init__(self):
        super().__init__(delay_range=(2, 4))
        self._session = requests.Session()

    @property
    def platform_name(self) -> str:
        return "Wellfound"

    def scrape(self, query: str, location: str = "Remote", max_jobs: int = 20) -> List[Dict]:
        jobs = []

        try:
            headers = self._get_headers(self.BASE_URL)
            params = {
                "q": query,
                "location": location if location.lower() != "india" else "",
                "remote": "true" if location.lower() in ("remote", "work from home") else "false",
            }

            print(f"  [Wellfound] Searching: {query}")

            response = self._session.get(
                self.SEARCH_URL,
                params=params,
                headers=headers,
                timeout=15
            )

            if response.status_code == 200:
                jobs = self._parse_response(response.text, max_jobs)
            else:
                self.errors.append(f"Wellfound: HTTP {response.status_code}")

        except Exception as e:
            self.errors.append(f"Wellfound error: {str(e)}")

        return jobs

    def _parse_response(self, html: str, max_jobs: int) -> List[Dict]:
        """Parse Wellfound HTML response."""
        jobs = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Look for Next.js data
            next_data = soup.find("script", id="__NEXT_DATA__")
            if next_data and next_data.string:
                try:
                    data = json.loads(next_data.string)
                    jobs = self._extract_from_next_data(data, max_jobs)
                    if jobs:
                        return jobs
                except Exception:
                    pass

            # Fallback: parse HTML cards
            job_cards = soup.find_all("div", class_=lambda x: x and "job" in str(x).lower())

            for card in job_cards[:max_jobs]:
                try:
                    title_el = card.find(["h2", "h3", "a"], class_=lambda x: x and "title" in str(x).lower())
                    company_el = card.find(class_=lambda x: x and "company" in str(x).lower())
                    location_el = card.find(class_=lambda x: x and "location" in str(x).lower())
                    salary_el = card.find(class_=lambda x: x and "salary" in str(x).lower())

                    title = self._clean_text(title_el.get_text() if title_el else "")
                    company = self._clean_text(company_el.get_text() if company_el else "")
                    location = self._clean_text(location_el.get_text() if location_el else "Remote")
                    salary = self._clean_text(salary_el.get_text() if salary_el else "")

                    link = card.find("a", href=True)
                    url = ""
                    if link:
                        href = link["href"]
                        url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                    if title and company:
                        desc = f"Role: {title}\nCompany: {company}\nLocation: {location}"
                        jobs.append(self._normalize_job({
                            "platform": "Wellfound",
                            "title": title,
                            "company": company,
                            "location": location,
                            "salary": salary,
                            "description": desc,
                            "url": url,
                            "skills": self._extract_skills_from_text(title + " " + desc),
                            "job_type": "Full-time",
                            "experience": "",
                            "posted_date": datetime.now().strftime("%Y-%m-%d")
                        }))
                        print(f"  [Wellfound] ✓ {title} @ {company}")
                except Exception:
                    continue

        except Exception as e:
            self.errors.append(f"Wellfound parse error: {str(e)}")

        return jobs

    def _extract_from_next_data(self, data: dict, max_jobs: int) -> List[Dict]:
        """Extract jobs from Next.js page data."""
        jobs = []
        try:
            # Navigate the Next.js data structure
            page_props = data.get("props", {}).get("pageProps", {})
            job_listings = (
                page_props.get("jobs", []) or
                page_props.get("jobListings", []) or
                page_props.get("searchResults", {}).get("jobs", [])
            )

            for item in job_listings[:max_jobs]:
                desc = item.get("description", "") or item.get("jobDescription", "")
                startup = item.get("startup", {}) or {}
                jobs.append(self._normalize_job({
                    "platform": "Wellfound",
                    "title": item.get("title", "") or item.get("role", ""),
                    "company": startup.get("name", "") or item.get("company", ""),
                    "location": item.get("locationNames", ["Remote"])[0] if item.get("locationNames") else "Remote",
                    "salary": item.get("compensation", "") or item.get("salary", ""),
                    "description": self._clean_description(desc),
                    "url": f"{self.BASE_URL}/jobs/{item.get('slug', item.get('id', ''))}",
                    "skills": item.get("skills", [])[:10] or self._extract_skills_from_text(desc),
                    "job_type": "Full-time",
                    "experience": item.get("experience", ""),
                    "posted_date": item.get("createdAt", datetime.now().strftime("%Y-%m-%d"))[:10]
                }))
                print(f"  [Wellfound] ✓ {item.get('title', 'Unknown')}")
        except Exception:
            pass
        return jobs
