"""
scrapers/base_scraper.py
Base scraper class with anti-detection, rate limiting, and shared utilities.
All platform scrapers inherit from this.
"""

import time
import random
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

# ─── User Agents Pool ────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

# ─── Accept Headers ───────────────────────────────────────────────────────────────
ACCEPT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.
    Provides: rate limiting, anti-detection, result normalization.
    """

    def __init__(self, delay_range: tuple = (2, 5)):
        self.delay_range = delay_range
        self.session = None
        self.results: List[Dict] = []
        self.errors: List[str] = []
        self._request_count = 0

    # ── Anti-Detection Helpers ─────────────────────────────────────────────────
    def _random_delay(self, extra_long: bool = False):
        """Human-like random delay between requests."""
        base_min, base_max = self.delay_range
        if extra_long:
            base_min *= 2
            base_max *= 3
        delay = random.uniform(base_min, base_max)
        # Occasional longer pause to mimic reading
        if random.random() < 0.15:
            delay += random.uniform(2, 5)
        time.sleep(delay)

    def _get_random_ua(self) -> str:
        return random.choice(USER_AGENTS)

    def _get_headers(self, referer: str = "") -> Dict:
        headers = {**ACCEPT_HEADERS}
        headers["User-Agent"] = self._get_random_ua()
        if referer:
            headers["Referer"] = referer
        return headers

    def _increment_request(self):
        self._request_count += 1
        # Every 10 requests, take a longer break
        if self._request_count % 10 == 0:
            self._random_delay(extra_long=True)

    # ── Text Cleaners ──────────────────────────────────────────────────────────
    @staticmethod
    def _clean_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text

    @staticmethod
    def _clean_description(text: str) -> str:
        if not text:
            return ""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        # Remove common junk patterns
        text = re.sub(r'(Apply Now|Easy Apply|Save Job|Report Job)', '', text, flags=re.IGNORECASE)
        return text.strip()

    @staticmethod
    def _extract_skills_from_text(text: str) -> List[str]:
        """Extract tech skills mentioned in job description."""
        KNOWN_SKILLS = [
            "python", "javascript", "typescript", "java", "c++", "c#", "golang", "go",
            "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab",
            "react", "angular", "vue", "node.js", "nodejs", "django", "flask", "fastapi",
            "spring", "express", "next.js", "nextjs", "nuxt",
            "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            "cassandra", "dynamodb", "firebase", "supabase",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
            "ci/cd", "jenkins", "github actions", "gitlab", "git",
            "machine learning", "deep learning", "tensorflow", "pytorch", "sklearn",
            "pandas", "numpy", "spark", "hadoop", "kafka",
            "rest", "graphql", "grpc", "microservices", "api",
            "agile", "scrum", "jira", "confluence", "linux", "bash",
            "html", "css", "tailwind", "bootstrap", "figma",
            "data science", "nlp", "computer vision", "llm"
        ]
        text_lower = text.lower()
        found = []
        for skill in KNOWN_SKILLS:
            if skill in text_lower:
                found.append(skill)
        return list(set(found))

    @staticmethod
    def _normalize_job(raw: Dict) -> Dict:
        """Ensure all jobs have consistent structure."""
        return {
            "platform": raw.get("platform", "unknown"),
            "title": BaseScraper._clean_text(raw.get("title", "")),
            "company": BaseScraper._clean_text(raw.get("company", "")),
            "location": BaseScraper._clean_text(raw.get("location", "")),
            "job_type": BaseScraper._clean_text(raw.get("job_type", "")),
            "experience": BaseScraper._clean_text(raw.get("experience", "")),
            "salary": BaseScraper._clean_text(raw.get("salary", "")),
            "description": BaseScraper._clean_description(raw.get("description", "")),
            "url": raw.get("url", ""),
            "skills": raw.get("skills", []),
            "posted_date": raw.get("posted_date", datetime.now().strftime("%Y-%m-%d")),
        }

    # ── Abstract Methods ───────────────────────────────────────────────────────
    @abstractmethod
    def scrape(self, query: str, location: str, max_jobs: int) -> List[Dict]:
        """
        Main scrape method. Must be implemented by each platform.

        Args:
            query: Job search query (e.g., "Python Developer")
            location: Location filter (e.g., "Bangalore")
            max_jobs: Maximum jobs to scrape

        Returns:
            List of normalized job dicts
        """
        pass

    @property
    @abstractmethod
    def platform_name(self) -> str:
        pass
