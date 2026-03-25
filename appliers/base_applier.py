"""
appliers/base_applier.py
Base class for all platform auto-appliers.
Handles: stealth browser, human simulation, screenshots, error recovery.
All platform appliers (LinkedIn, Naukri, Indeed) inherit from this.
"""

import time
import random
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from datetime import datetime


# ─── Apply Result ────────────────────────────────────────────────────────────────
class ApplyResult:
    def __init__(
        self,
        status: str,           # success | failed | skipped | captcha | already_applied
        job_id: int = 0,
        platform: str = "",
        message: str = "",
        screenshot_path: str = "",
        time_taken: float = 0.0
    ):
        self.status = status
        self.job_id = job_id
        self.platform = platform
        self.message = message
        self.screenshot_path = screenshot_path
        self.time_taken = time_taken
        self.timestamp = datetime.now().isoformat()

    def is_success(self) -> bool:
        return self.status == "success"

    def __repr__(self):
        return f"ApplyResult(status={self.status}, platform={self.platform}, msg={self.message[:60]})"


# ─── User Profile (what we fill into forms) ─────────────────────────────────────
class UserProfile:
    """
    Stores user's personal details for form filling.
    Loaded from .env or user input in UI.
    """
    def __init__(
        self,
        full_name: str = "",
        email: str = "",
        phone: str = "",
        location: str = "",
        linkedin_url: str = "",
        portfolio_url: str = "",
        years_experience: str = "",
        current_ctc: str = "",
        expected_ctc: str = "",
        notice_period: str = "Immediate",
        cover_letter: str = "",
        resume_pdf_path: str = "",
        linkedin_email: str = "",
        linkedin_password: str = "",
    ):
        self.full_name = full_name
        self.email = email
        self.phone = phone
        self.location = location
        self.linkedin_url = linkedin_url
        self.portfolio_url = portfolio_url
        self.years_experience = years_experience
        self.current_ctc = current_ctc
        self.expected_ctc = expected_ctc
        self.notice_period = notice_period
        self.cover_letter = cover_letter
        self.resume_pdf_path = resume_pdf_path
        self.linkedin_email = linkedin_email
        self.linkedin_password = linkedin_password

    @classmethod
    def from_env(cls) -> "UserProfile":
        """Load profile from environment variables."""
        from dotenv import load_dotenv
        load_dotenv()
        return cls(
            full_name=os.getenv("USER_FULL_NAME", ""),
            email=os.getenv("USER_EMAIL", ""),
            phone=os.getenv("USER_PHONE", ""),
            location=os.getenv("USER_LOCATION", ""),
            linkedin_url=os.getenv("USER_LINKEDIN_URL", ""),
            portfolio_url=os.getenv("USER_PORTFOLIO_URL", ""),
            years_experience=os.getenv("USER_YEARS_EXPERIENCE", ""),
            current_ctc=os.getenv("USER_CURRENT_CTC", ""),
            expected_ctc=os.getenv("USER_EXPECTED_CTC", ""),
            notice_period=os.getenv("USER_NOTICE_PERIOD", "Immediate"),
            cover_letter="",
            resume_pdf_path=os.getenv("USER_RESUME_PDF_PATH", ""),
            linkedin_email=os.getenv("LINKEDIN_EMAIL", ""),
            linkedin_password=os.getenv("LINKEDIN_PASSWORD", ""),
        )

    def is_complete(self) -> Tuple[bool, list]:
        """Check if all required fields are filled."""
        required = {
            "Full Name": self.full_name,
            "Email": self.email,
            "Phone": self.phone,
        }
        missing = [k for k, v in required.items() if not v.strip()]
        return len(missing) == 0, missing


# ─── Screenshot Manager ──────────────────────────────────────────────────────────
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def take_screenshot(page, name: str) -> str:
    """Take screenshot and return path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{name}.png"
    path = os.path.join(SCREENSHOT_DIR, filename)
    try:
        page.screenshot(path=path, full_page=False)
        return path
    except Exception:
        return ""


# ─── Base Applier ────────────────────────────────────────────────────────────────
class BaseApplier(ABC):
    """
    Abstract base for all platform auto-appliers.
    Provides: stealth browser, human mouse/keyboard sim, form filling, error handling.
    """

    def __init__(self, profile: UserProfile, headless: bool = True):
        self.profile = profile
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._start_time = None

    # ── Browser Setup ──────────────────────────────────────────────────────────
    def _init_browser(self):
        """Initialize stealth Playwright browser."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "Playwright not installed!\n"
                "Run: pip install playwright && playwright install chromium"
            )

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=random.randint(30, 80),   # Natural slowdown
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1440,900",
                "--disable-extensions",
                "--disable-plugins-discovery",
            ]
        )

        self._context = self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
            # Permissions
            permissions=["geolocation"],
        )

        # Inject stealth scripts into every page
        self._context.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // Fake plugins array
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    return {
                        length: 3,
                        0: { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        1: { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        2: { name: 'Native Client', filename: 'internal-nacl-plugin' },
                    };
                }
            });

            // Fake languages
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

            // Override chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Fix permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        self._page = self._context.new_page()
        self._page.set_default_timeout(30000)

    def _close_browser(self):
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    # ── Human Simulation ───────────────────────────────────────────────────────
    def _human_delay(self, min_ms: int = 500, max_ms: int = 1500):
        """Random human-like pause."""
        time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))

    def _human_type(self, locator, text: str, clear_first: bool = True):
        """Type text with human-like character delays."""
        if clear_first:
            locator.triple_click()
            self._human_delay(100, 300)
            locator.press("Control+a")
            locator.press("Delete")
            self._human_delay(100, 200)

        for char in text:
            locator.type(char, delay=random.randint(40, 140))
            # Occasional typo simulation (very rare)
            if random.random() < 0.005 and char.isalpha():
                wrong = random.choice("qwertyuiopasdfghjklzxcvbnm")
                locator.type(wrong, delay=50)
                self._human_delay(200, 400)
                locator.press("Backspace")

    def _human_click(self, locator):
        """Click with slight offset variation."""
        try:
            box = locator.bounding_box()
            if box:
                x = box["x"] + box["width"] / 2 + random.randint(-3, 3)
                y = box["y"] + box["height"] / 2 + random.randint(-2, 2)
                self._page.mouse.click(x, y)
            else:
                locator.click()
        except Exception:
            locator.click()
        self._human_delay(300, 800)

    def _human_scroll(self, amount: int = 300):
        """Scroll with human randomness."""
        actual = amount + random.randint(-50, 50)
        self._page.mouse.wheel(0, actual)
        self._human_delay(200, 600)

    def _move_mouse_randomly(self):
        """Move mouse to random position (anti-bot)."""
        x = random.randint(100, 1300)
        y = random.randint(100, 800)
        self._page.mouse.move(x, y)
        self._human_delay(100, 300)

    # ── Form Filling Helpers ───────────────────────────────────────────────────
    def _fill_if_empty(self, selector: str, value: str):
        """Fill a field only if it's empty."""
        if not value:
            return
        try:
            el = self._page.query_selector(selector)
            if el:
                current_val = el.input_value() or ""
                if not current_val.strip():
                    self._human_type(el, value)
        except Exception:
            pass

    def _safe_fill(self, selector: str, value: str):
        """Fill a field, suppressing errors."""
        if not value:
            return False
        try:
            self._page.fill(selector, value)
            return True
        except Exception:
            return False

    def _safe_click(self, selector: str, timeout: int = 5000) -> bool:
        """Click element safely."""
        try:
            self._page.click(selector, timeout=timeout)
            return True
        except Exception:
            return False

    def _wait_for_any(self, selectors: list, timeout: int = 10000) -> Optional[str]:
        """Wait for any of the given selectors to appear. Returns matched selector."""
        for selector in selectors:
            try:
                self._page.wait_for_selector(selector, timeout=timeout // len(selectors))
                return selector
            except Exception:
                continue
        return None

    def _detect_captcha(self) -> bool:
        """Check if captcha is present on page."""
        captcha_indicators = [
            "captcha", "recaptcha", "hcaptcha", "verify you are human",
            "robot", "challenge", "security check"
        ]
        page_text = self._page.content().lower()
        return any(indicator in page_text for indicator in captcha_indicators)

    def _detect_already_applied(self) -> bool:
        """Check if already applied to this job."""
        indicators = [
            "already applied", "application submitted", "you applied",
            "application received", "applied on"
        ]
        try:
            page_text = self._page.inner_text("body").lower()
            return any(ind in page_text for ind in indicators)
        except Exception:
            return False

    # ── PDF Upload Helper ──────────────────────────────────────────────────────
    def _upload_resume(self, file_input_selector: str, pdf_path: str) -> bool:
        """Upload resume PDF to file input."""
        if not pdf_path or not os.path.exists(pdf_path):
            return False
        try:
            self._page.set_input_files(file_input_selector, pdf_path)
            self._human_delay(800, 1500)
            return True
        except Exception:
            return False

    # ── Timing ────────────────────────────────────────────────────────────────
    def _start_timer(self):
        self._start_time = time.time()

    def _get_elapsed(self) -> float:
        if self._start_time:
            return round(time.time() - self._start_time, 2)
        return 0.0

    # ── Abstract Methods ───────────────────────────────────────────────────────
    @abstractmethod
    def apply(self, job: Dict, resume_pdf_path: str, cover_letter: str = "") -> ApplyResult:
        """
        Apply to a single job.
        Must be implemented by each platform applier.

        Args:
            job: Job dict from database (id, title, company, url, platform, etc.)
            resume_pdf_path: Path to generated PDF resume
            cover_letter: Cover letter text

        Returns:
            ApplyResult with status and details
        """
        pass

    @property
    @abstractmethod
    def platform_name(self) -> str:
        pass
