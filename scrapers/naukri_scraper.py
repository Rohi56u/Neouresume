"""
scrapers/naukri_scraper.py
Naukri.com job scraper using requests + BeautifulSoup.
Naukri uses a JSON API internally — we tap into that directly.
"""

import requests
import json
import time
import random
import urllib.parse
from typing import List, Dict, Optional
from datetime import datetime

from .base_scraper import BaseScraper


class NaukriScraper(BaseScraper):
    """
    Scrapes Naukri.com using their internal search API.
    Much faster than browser automation for this platform.
    """

    # Naukri's internal JSON search API
    API_URL = "https://www.naukri.com/jobapi/v3/search"
    BASE_URL = "https://www.naukri.com"

    def __init__(self):
        super().__init__(delay_range=(1, 3))
        self._session = requests.Session()

    @property
    def platform_name(self) -> str:
        return "Naukri"

    def _init_session(self):
        """Set up requests session with proper headers."""
        self._session.headers.update({
            "User-Agent": self._get_random_ua(),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.naukri.com/",
            "Origin": "https://www.naukri.com",
            "appid": "109",
            "systemid": "Naukri",
            "Connection": "keep-alive",
        })

        # First visit homepage to get cookies
        try:
            self._session.get(self.BASE_URL, timeout=15)
            time.sleep(random.uniform(1, 2))
        except Exception:
            pass

    def scrape(self, query: str, location: str = "India", max_jobs: int = 20) -> List[Dict]:
        """Scrape Naukri jobs for given query and location."""
        jobs = []

        try:
            self._init_session()

            # Build search URL for Naukri format
            query_slug = query.lower().replace(" ", "-")
            location_slug = location.lower().replace(" ", "-")

            # Naukri API parameters
            params = {
                "noOfResults": min(max_jobs, 20),
                "urlType": "search_by_key_loc",
                "searchType": "adv",
                "keyword": query,
                "location": location,
                "pageNo": 1,
                "sort": "r",
                "typeField": "y",
            }

            # Try the main search page approach (more reliable)
            search_url = f"https://www.naukri.com/{query_slug}-jobs-in-{location_slug}"

            print(f"  [Naukri] Searching: {query} in {location}")

            response = self._session.get(
                search_url,
                timeout=20,
                headers={
                    **self._get_headers(self.BASE_URL),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
            )

            if response.status_code == 200:
                jobs = self._parse_html_response(response.text, max_jobs)
            else:
                # Fallback: Try API endpoint
                jobs = self._try_api_fallback(query, location, max_jobs)

        except requests.exceptions.ConnectionError:
            self.errors.append("Naukri: Connection failed — check internet connection")
        except requests.exceptions.Timeout:
            self.errors.append("Naukri: Request timed out")
        except Exception as e:
            self.errors.append(f"Naukri scraper error: {str(e)}")
            print(f"  [Naukri] ✗ {str(e)}")

        return jobs

    def _parse_html_response(self, html: str, max_jobs: int) -> List[Dict]:
        """Parse Naukri HTML response to extract jobs."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("BeautifulSoup not installed! Run: pip install beautifulsoup4")

        jobs = []
        soup = BeautifulSoup(html, "html.parser")

        # Naukri job cards
        job_cards = soup.find_all("article", class_=lambda x: x and "jobTuple" in x)

        if not job_cards:
            # Try alternative selector
            job_cards = soup.find_all("div", class_=lambda x: x and "job-tuple" in str(x).lower())

        if not job_cards:
            # Try JSON embedded in page
            return self._extract_from_json_ld(soup, max_jobs)

        print(f"  [Naukri] Found {len(job_cards)} job cards")

        for card in job_cards[:max_jobs]:
            try:
                job = self._parse_card(card)
                if job:
                    normalized = self._normalize_job(job)
                    jobs.append(normalized)
                    print(f"  [Naukri] ✓ {job.get('title')} @ {job.get('company')}")
                    self._random_delay()
            except Exception as e:
                continue

        return jobs

    def _parse_card(self, card) -> Optional[Dict]:
        """Extract data from a single Naukri job card."""
        try:
            # Title
            title_el = card.find("a", class_=lambda x: x and "title" in str(x).lower())
            if not title_el:
                title_el = card.find("a", {"title": True})

            # Company
            company_el = card.find(class_=lambda x: x and "comp-name" in str(x).lower())
            if not company_el:
                company_el = card.find("a", class_=lambda x: x and "subTitle" in str(x))

            # Location
            location_el = card.find(class_=lambda x: x and "loc" in str(x).lower())

            # Experience
            exp_el = card.find(class_=lambda x: x and "exp" in str(x).lower())

            # Salary
            sal_el = card.find(class_=lambda x: x and "sal" in str(x).lower())

            # Skills
            skills_el = card.find(class_=lambda x: x and "skill" in str(x).lower())

            title = self._clean_text(title_el.get_text() if title_el else "")
            company = self._clean_text(company_el.get_text() if company_el else "")
            location = self._clean_text(location_el.get_text() if location_el else "")
            experience = self._clean_text(exp_el.get_text() if exp_el else "")
            salary = self._clean_text(sal_el.get_text() if sal_el else "")
            skills_text = skills_el.get_text() if skills_el else ""
            skills = [s.strip() for s in skills_text.split(",") if s.strip()][:10]

            url = ""
            if title_el and title_el.get("href"):
                url = title_el["href"]
                if not url.startswith("http"):
                    url = self.BASE_URL + url

            description = self._build_description_from_card(card)
            all_skills = list(set(skills + self._extract_skills_from_text(description)))

            return {
                "platform": "Naukri",
                "title": title,
                "company": company,
                "location": location,
                "experience": experience,
                "salary": salary,
                "description": description,
                "url": url,
                "skills": all_skills,
                "job_type": "Full-time",
                "posted_date": datetime.now().strftime("%Y-%m-%d")
            }
        except Exception:
            return None

    def _build_description_from_card(self, card) -> str:
        """Build a description from available card data."""
        parts = []
        # Look for job description snippets
        desc_el = card.find(class_=lambda x: x and ("desc" in str(x).lower() or "desc" in str(x)))
        if desc_el:
            parts.append(desc_el.get_text(separator="\n"))

        tags_el = card.find_all(class_=lambda x: x and "tag" in str(x).lower())
        for tag in tags_el:
            text = tag.get_text().strip()
            if text:
                parts.append(text)

        return "\n".join(parts)

    def _extract_from_json_ld(self, soup, max_jobs: int) -> List[Dict]:
        """Extract jobs from JSON-LD structured data in page."""
        jobs = []
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string or "{}")
                if isinstance(data, list):
                    items = data
                elif data.get("@type") == "ItemList":
                    items = data.get("itemListElement", [])
                else:
                    items = [data] if data.get("@type") == "JobPosting" else []

                for item in items[:max_jobs]:
                    if isinstance(item, dict):
                        jp = item.get("item", item)
                        if jp.get("@type") == "JobPosting":
                            desc = jp.get("description", "")
                            jobs.append(self._normalize_job({
                                "platform": "Naukri",
                                "title": jp.get("title", ""),
                                "company": jp.get("hiringOrganization", {}).get("name", "") if isinstance(jp.get("hiringOrganization"), dict) else str(jp.get("hiringOrganization", "")),
                                "location": jp.get("jobLocation", {}).get("address", {}).get("addressLocality", "") if isinstance(jp.get("jobLocation"), dict) else "",
                                "description": self._clean_description(desc),
                                "url": jp.get("url", ""),
                                "salary": "",
                                "job_type": jp.get("employmentType", ""),
                                "experience": "",
                                "skills": self._extract_skills_from_text(desc),
                                "posted_date": jp.get("datePosted", datetime.now().strftime("%Y-%m-%d"))
                            }))
            except Exception:
                continue
        return jobs

    def _try_api_fallback(self, query: str, location: str, max_jobs: int) -> List[Dict]:
        """Try Naukri's JSON API as fallback."""
        try:
            api_params = {
                "noOfResults": max_jobs,
                "urlType": "search_by_key_loc",
                "searchType": "adv",
                "keyword": query,
                "location": location,
                "pageNo": 1,
            }
            headers = {
                **self._get_headers(self.BASE_URL),
                "Accept": "application/json",
                "appid": "109",
                "systemid": "Naukri",
            }
            response = self._session.get(
                self.API_URL,
                params=api_params,
                headers=headers,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                job_details = data.get("jobDetails", [])
                jobs = []
                for item in job_details[:max_jobs]:
                    desc = item.get("jobDescription", "")
                    jobs.append(self._normalize_job({
                        "platform": "Naukri",
                        "title": item.get("title", ""),
                        "company": item.get("companyName", ""),
                        "location": ", ".join(item.get("placeholders", [{}])[0].get("label", "").split(",")[:2]) if item.get("placeholders") else "",
                        "description": self._clean_description(desc),
                        "url": f"https://www.naukri.com/{item.get('jobId', '')}",
                        "salary": item.get("salary", ""),
                        "job_type": "Full-time",
                        "experience": item.get("experience", ""),
                        "skills": item.get("tagsAndSkills", "").split(",")[:10] if item.get("tagsAndSkills") else [],
                        "posted_date": datetime.now().strftime("%Y-%m-%d")
                    }))
                print(f"  [Naukri] API fallback: {len(jobs)} jobs found")
                return jobs
        except Exception as e:
            self.errors.append(f"Naukri API fallback failed: {str(e)}")
        return []
