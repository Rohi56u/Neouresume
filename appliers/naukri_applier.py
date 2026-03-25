"""
appliers/naukri_applier.py
Naukri.com auto-apply automation.
Handles: login, job apply modal, resume upload, profile-based form filling.
"""

import time
import random
import os
from typing import Dict, Optional

from .base_applier import BaseApplier, ApplyResult, UserProfile, take_screenshot


class NaukriApplier(BaseApplier):
    """
    Automates Naukri.com job applications.

    Flow:
    1. Login to Naukri
    2. Navigate to job URL
    3. Click Apply button
    4. Handle apply modal / redirect
    5. Fill form if required
    6. Submit
    """

    LOGIN_URL = "https://www.naukri.com/nlogin/login"
    BASE_URL = "https://www.naukri.com"
    SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".naukri_session.json")

    def __init__(self, profile: UserProfile, headless: bool = True):
        super().__init__(profile, headless)
        self._logged_in = False

    @property
    def platform_name(self) -> str:
        return "Naukri"

    # ── Session Management ─────────────────────────────────────────────────────
    def _restore_session(self) -> bool:
        if not os.path.exists(self.SESSION_FILE):
            return False
        try:
            import json
            with open(self.SESSION_FILE, "r") as f:
                cookies = json.load(f)
            self._context.add_cookies(cookies)
            self._page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=20000)
            self._human_delay(1500, 2500)
            # Check if logged in — Naukri shows username or profile icon
            page_content = self._page.content().lower()
            if "naukri.com" in self._page.url and ("logout" in page_content or "profile" in page_content):
                print("  [Naukri] Session restored ✓")
                return True
        except Exception:
            pass
        return False

    def _save_session(self):
        try:
            import json
            cookies = self._context.cookies()
            with open(self.SESSION_FILE, "w") as f:
                json.dump(cookies, f)
        except Exception:
            pass

    def _login(self) -> bool:
        """Login to Naukri."""
        if not self.profile.email or not self.profile.linkedin_password:
            return False

        # Naukri uses email + password (same as general profile password)
        naukri_password = os.getenv("NAUKRI_PASSWORD", self.profile.linkedin_password)

        try:
            print("  [Naukri] Logging in...")
            self._page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
            self._human_delay(1500, 2500)

            # Fill email
            email_sel = "input[placeholder*='email'], input[name*='email'], #usernameField"
            email_el = self._page.query_selector(email_sel)
            if email_el:
                self._human_type(email_el, self.profile.email)
                self._human_delay(400, 800)

            # Fill password
            pass_sel = "input[type='password'], input[placeholder*='password'], #passwordField"
            pass_el = self._page.query_selector(pass_sel)
            if pass_el:
                self._human_type(pass_el, naukri_password)
                self._human_delay(400, 800)

            # Click login
            login_btn = self._page.query_selector(
                "button[type='submit'], button:has-text('Login'), "
                "input[type='submit'], .loginButton"
            )
            if login_btn:
                self._human_click(login_btn)
                self._human_delay(3000, 5000)

            if self._detect_captcha():
                print("  [Naukri] CAPTCHA detected")
                return False

            # Verify login
            page_text = self._page.content().lower()
            if "logout" in page_text or "my naukri" in page_text or "/mnjuser/" in self._page.url:
                print("  [Naukri] Login successful ✓")
                self._save_session()
                self._logged_in = True
                return True

            print(f"  [Naukri] Login failed — URL: {self._page.url}")
            return False

        except Exception as e:
            print(f"  [Naukri] Login error: {e}")
            return False

    def _ensure_logged_in(self) -> bool:
        if self._logged_in:
            return True
        if self._restore_session():
            self._logged_in = True
            return True
        return self._login()

    # ── Apply Flow ─────────────────────────────────────────────────────────────
    def apply(self, job: Dict, resume_pdf_path: str, cover_letter: str = "") -> ApplyResult:
        """Apply to a Naukri job."""
        self._start_timer()
        job_id = job.get("id", 0)
        url = job.get("url", "")
        title = job.get("title", "")
        company = job.get("company", "")

        if not url:
            return ApplyResult("failed", job_id, "Naukri", "No job URL provided")

        try:
            self._init_browser()

            if not self._ensure_logged_in():
                return ApplyResult(
                    "failed", job_id, "Naukri",
                    "Naukri login failed. Add USER_EMAIL and NAUKRI_PASSWORD to .env"
                )

            print(f"  [Naukri] Applying to: {title} @ {company}")

            # Navigate to job
            self._page.goto(url, wait_until="domcontentloaded", timeout=25000)
            self._human_delay(2000, 3500)

            if self._detect_captcha():
                screenshot = take_screenshot(self._page, f"naukri_captcha_{job_id}")
                return ApplyResult("captcha", job_id, "Naukri", "CAPTCHA detected", screenshot, self._get_elapsed())

            if self._detect_already_applied():
                return ApplyResult("already_applied", job_id, "Naukri", "Already applied", "", self._get_elapsed())

            # Find Apply button
            apply_btn = self._find_apply_button()
            if not apply_btn:
                screenshot = take_screenshot(self._page, f"naukri_no_apply_{job_id}")
                return ApplyResult("skipped", job_id, "Naukri", "Apply button not found", screenshot, self._get_elapsed())

            self._human_click(apply_btn)
            self._human_delay(2000, 3500)

            # Handle what comes after clicking apply
            result = self._handle_post_apply_click(job_id, resume_pdf_path, cover_letter)
            return result

        except Exception as e:
            screenshot = take_screenshot(self._page, f"naukri_error_{job_id}") if self._page else ""
            return ApplyResult("failed", job_id, "Naukri", f"Error: {str(e)}", screenshot, self._get_elapsed())
        finally:
            self._close_browser()

    def _find_apply_button(self):
        """Find Apply button on Naukri job page."""
        selectors = [
            "button#apply-button",
            "button.apply-button",
            "a#apply-button",
            "button:has-text('Apply')",
            ".apply-btn",
            "[class*='applyBtn']",
            "button[contains(text(), 'Apply')]",
            "div.apply-button-container button",
        ]
        for sel in selectors:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible():
                    text = btn.inner_text().lower()
                    if "apply" in text and "email" not in text:
                        return btn
            except Exception:
                continue
        return None

    def _handle_post_apply_click(self, job_id: int, resume_pdf_path: str, cover_letter: str) -> ApplyResult:
        """Handle Naukri apply flow after clicking Apply button."""
        current_url = self._page.url
        page_content = self._page.content().lower()

        # Check for external application redirect
        if "naukri.com" not in current_url:
            return ApplyResult(
                "skipped", job_id, "Naukri",
                f"External application — redirected to {current_url[:80]}",
                "", self._get_elapsed()
            )

        # Check for modal
        modal_selectors = [
            ".apply-modal",
            ".applyModal",
            "#apply-modal",
            "[class*='applyModal']",
            ".popup-container",
        ]
        modal_found = False
        for sel in modal_selectors:
            try:
                modal = self._page.wait_for_selector(sel, timeout=5000)
                if modal:
                    modal_found = True
                    break
            except Exception:
                continue

        if modal_found:
            return self._handle_apply_modal(job_id, resume_pdf_path, cover_letter)

        # Check if application was auto-submitted (some Naukri jobs do this)
        success_indicators = [
            "application submitted",
            "applied successfully",
            "your application",
            "successfully applied",
        ]
        if any(ind in page_content for ind in success_indicators):
            screenshot = take_screenshot(self._page, f"naukri_success_{job_id}")
            return ApplyResult("success", job_id, "Naukri", "Application submitted!", screenshot, self._get_elapsed())

        # Try to find and fill form on page
        return self._fill_apply_form(job_id, resume_pdf_path, cover_letter)

    def _handle_apply_modal(self, job_id: int, resume_pdf_path: str, cover_letter: str) -> ApplyResult:
        """Handle Naukri apply modal."""
        self._human_delay(1000, 2000)

        # Upload resume if file input exists
        file_input = self._page.query_selector("input[type='file']")
        if file_input and resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                self._page.set_input_files("input[type='file']", resume_pdf_path)
                self._human_delay(1000, 2000)
            except Exception:
                pass

        # Fill message/cover letter
        if cover_letter:
            textarea = self._page.query_selector(
                "textarea[placeholder*='message'], textarea[placeholder*='cover'], textarea"
            )
            if textarea:
                self._human_type(textarea, cover_letter[:1000])
                self._human_delay(300, 600)

        # Click Submit/Apply in modal
        submit_selectors = [
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button[type='submit']",
            ".apply-btn-modal",
            "button.apply-button",
        ]
        for sel in submit_selectors:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible():
                    self._human_click(btn)
                    self._human_delay(2000, 3000)
                    screenshot = take_screenshot(self._page, f"naukri_submitted_{job_id}")
                    return ApplyResult("success", job_id, "Naukri", "Application submitted!", screenshot, self._get_elapsed())
            except Exception:
                continue

        screenshot = take_screenshot(self._page, f"naukri_modal_fail_{job_id}")
        return ApplyResult("failed", job_id, "Naukri", "Could not submit modal form", screenshot, self._get_elapsed())

    def _fill_apply_form(self, job_id: int, resume_pdf_path: str, cover_letter: str) -> ApplyResult:
        """Fill inline apply form on Naukri job page."""
        # Fill basic fields
        field_map = {
            "input[name*='name'], input[placeholder*='name']": self.profile.full_name,
            "input[name*='email'], input[placeholder*='email'], input[type='email']": self.profile.email,
            "input[name*='phone'], input[placeholder*='phone'], input[type='tel']": self.profile.phone,
            "input[name*='experience'], input[placeholder*='experience']": self.profile.years_experience,
            "input[name*='ctc'], input[placeholder*='ctc']": self.profile.current_ctc,
        }

        for selector, value in field_map.items():
            if value:
                try:
                    el = self._page.query_selector(selector)
                    if el and el.is_visible():
                        current = el.input_value() or ""
                        if not current.strip():
                            self._human_type(el, str(value))
                            self._human_delay(200, 400)
                except Exception:
                    continue

        # Upload resume
        file_input = self._page.query_selector("input[type='file']")
        if file_input and resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                self._page.set_input_files("input[type='file']", resume_pdf_path)
                self._human_delay(1000, 2000)
            except Exception:
                pass

        # Cover letter
        if cover_letter:
            textarea = self._page.query_selector("textarea")
            if textarea:
                self._human_type(textarea, cover_letter[:1000])
                self._human_delay(300, 600)

        # Submit
        submit_btn = self._page.query_selector(
            "button[type='submit'], button:has-text('Submit'), button:has-text('Apply')"
        )
        if submit_btn and submit_btn.is_visible():
            self._human_click(submit_btn)
            self._human_delay(2000, 3000)
            screenshot = take_screenshot(self._page, f"naukri_form_submitted_{job_id}")
            return ApplyResult("success", job_id, "Naukri", "Form submitted!", screenshot, self._get_elapsed())

        screenshot = take_screenshot(self._page, f"naukri_no_submit_{job_id}")
        return ApplyResult("failed", job_id, "Naukri", "No submit button found", screenshot, self._get_elapsed())
