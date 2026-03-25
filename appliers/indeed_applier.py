"""
appliers/indeed_applier.py
Indeed.com auto-apply automation.
Handles: Easily Apply badge detection, Indeed account login, form filling.
"""

import os
import time
import random
from typing import Dict, Optional

from .base_applier import BaseApplier, ApplyResult, UserProfile, take_screenshot


class IndeedApplier(BaseApplier):
    """
    Automates Indeed 'Easily Apply' job applications.
    Only applies to jobs that have the 'Easily Apply' badge.
    External applications are marked as skipped.
    """

    LOGIN_URL = "https://secure.indeed.com/account/login"
    BASE_URL = "https://in.indeed.com"
    SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".indeed_session.json")

    def __init__(self, profile: UserProfile, headless: bool = True):
        super().__init__(profile, headless)
        self._logged_in = False

    @property
    def platform_name(self) -> str:
        return "Indeed"

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
            page_text = self._page.content().lower()
            if "sign in" not in page_text and "login" not in self._page.url:
                print("  [Indeed] Session restored ✓")
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
        """Login to Indeed."""
        indeed_email = os.getenv("INDEED_EMAIL", self.profile.email)
        indeed_password = os.getenv("INDEED_PASSWORD", "")
        if not indeed_email or not indeed_password:
            return False

        try:
            print("  [Indeed] Logging in...")
            self._page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
            self._human_delay(2000, 3000)

            email_el = self._page.query_selector(
                "input[name='__email'], input[type='email'], input[id*='email']"
            )
            if email_el:
                self._human_type(email_el, indeed_email)
                self._human_delay(500, 900)

                continue_btn = self._page.query_selector("button:has-text('Continue'), button[type='submit']")
                if continue_btn:
                    self._human_click(continue_btn)
                    self._human_delay(2000, 3000)

            pass_el = self._page.query_selector("input[type='password'], input[name='__password']")
            if pass_el:
                self._human_type(pass_el, indeed_password)
                self._human_delay(500, 900)
                signin_btn = self._page.query_selector("button:has-text('Sign in'), button[type='submit']")
                if signin_btn:
                    self._human_click(signin_btn)
                    self._human_delay(3000, 5000)

            if self._detect_captcha():
                return False

            page_text = self._page.content().lower()
            if "sign in" not in page_text:
                print("  [Indeed] Login successful ✓")
                self._save_session()
                self._logged_in = True
                return True

            return False
        except Exception as e:
            print(f"  [Indeed] Login error: {e}")
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
        """Apply to an Indeed job."""
        self._start_timer()
        job_id = job.get("id", 0)
        url = job.get("url", "")
        title = job.get("title", "")
        company = job.get("company", "")

        if not url:
            return ApplyResult("failed", job_id, "Indeed", "No job URL provided")

        try:
            self._init_browser()

            if not self._ensure_logged_in():
                return ApplyResult(
                    "failed", job_id, "Indeed",
                    "Indeed login failed. Add INDEED_EMAIL and INDEED_PASSWORD to .env"
                )

            print(f"  [Indeed] Applying to: {title} @ {company}")

            self._page.goto(url, wait_until="domcontentloaded", timeout=25000)
            self._human_delay(2000, 3500)

            if self._detect_captcha():
                screenshot = take_screenshot(self._page, f"indeed_captcha_{job_id}")
                return ApplyResult("captcha", job_id, "Indeed", "CAPTCHA detected", screenshot, self._get_elapsed())

            if self._detect_already_applied():
                return ApplyResult("already_applied", job_id, "Indeed", "Already applied", "", self._get_elapsed())

            # Check for Easily Apply button
            apply_btn = self._find_apply_button()
            if not apply_btn:
                return ApplyResult(
                    "skipped", job_id, "Indeed",
                    "No 'Easily Apply' button — requires external application",
                    "", self._get_elapsed()
                )

            self._human_click(apply_btn)
            self._human_delay(2000, 3500)

            # Handle application flow
            return self._handle_apply_flow(job_id, resume_pdf_path, cover_letter)

        except Exception as e:
            screenshot = take_screenshot(self._page, f"indeed_error_{job_id}") if self._page else ""
            return ApplyResult("failed", job_id, "Indeed", f"Error: {str(e)}", screenshot, self._get_elapsed())
        finally:
            self._close_browser()

    def _find_apply_button(self):
        """Find Indeed Easily Apply button."""
        selectors = [
            "button.ia-IndeedApplyButton",
            "button[id*='indeedApply']",
            "button:has-text('Apply now')",
            "a.indeed-apply-widget",
            ".jobsearch-IndeedApplyButton-newDesign",
            "span.indeed-apply-widget button",
            "button[class*='indeedApply']",
        ]
        for sel in selectors:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible():
                    return btn
            except Exception:
                continue
        return None

    def _handle_apply_flow(self, job_id: int, resume_pdf_path: str, cover_letter: str) -> ApplyResult:
        """Handle Indeed application form flow."""
        max_steps = 7
        for step in range(1, max_steps + 1):
            self._human_delay(1000, 2000)
            current_url = self._page.url
            page_content = self._page.content().lower()

            # Check for success
            success_indicators = [
                "application submitted", "successfully applied",
                "thank you for applying", "your application has been",
            ]
            if any(ind in page_content for ind in success_indicators):
                screenshot = take_screenshot(self._page, f"indeed_success_{job_id}")
                return ApplyResult("success", job_id, "Indeed", "Application submitted!", screenshot, self._get_elapsed())

            # Check for external redirect
            if "indeed.com" not in current_url and step > 1:
                return ApplyResult(
                    "skipped", job_id, "Indeed",
                    f"Redirected to external site: {current_url[:80]}",
                    "", self._get_elapsed()
                )

            # Fill fields on current step
            self._fill_step_fields(resume_pdf_path, cover_letter)

            # Click Continue/Next/Submit
            action = self._click_next_or_submit_indeed()
            if action == "submitted":
                screenshot = take_screenshot(self._page, f"indeed_submitted_{job_id}")
                return ApplyResult("success", job_id, "Indeed", "Application submitted!", screenshot, self._get_elapsed())
            elif action == "none":
                screenshot = take_screenshot(self._page, f"indeed_stuck_{job_id}")
                return ApplyResult("failed", job_id, "Indeed", f"Stuck at step {step}", screenshot, self._get_elapsed())

        screenshot = take_screenshot(self._page, f"indeed_maxstep_{job_id}")
        return ApplyResult("failed", job_id, "Indeed", "Too many steps", screenshot, self._get_elapsed())

    def _fill_step_fields(self, resume_pdf_path: str, cover_letter: str):
        """Fill all visible fields on current step."""
        # Resume upload
        file_input = self._page.query_selector("input[type='file']")
        if file_input and resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                self._page.set_input_files("input[type='file']", resume_pdf_path)
                self._human_delay(1000, 2000)
            except Exception:
                pass

        # Text fields
        text_fields = {
            "input[name*='name'], input[autocomplete='name']": self.profile.full_name,
            "input[type='email'], input[autocomplete='email']": self.profile.email,
            "input[type='tel'], input[name*='phone']": self.profile.phone,
            "input[name*='city'], input[autocomplete='address-level2']": self.profile.location,
        }
        for sel, val in text_fields.items():
            if val:
                try:
                    el = self._page.query_selector(sel)
                    if el and el.is_visible():
                        curr = el.input_value() or ""
                        if not curr.strip():
                            self._human_type(el, val)
                            self._human_delay(200, 400)
                except Exception:
                    continue

        # Cover letter textarea
        if cover_letter:
            textarea = self._page.query_selector(
                "textarea[name*='message'], textarea[name*='cover'], textarea[class*='cover']"
            )
            if textarea and textarea.is_visible():
                curr = textarea.input_value() or ""
                if not curr.strip():
                    self._human_type(textarea, cover_letter[:2000])
                    self._human_delay(300, 600)

        # Yes/No questions — default to "Yes" for work authorization
        radios = self._page.query_selector_all("input[type='radio']")
        for radio in radios:
            try:
                if radio.evaluate("el => el.checked"):
                    continue
                val = (radio.get_attribute("value") or "").lower()
                parent_text = ""
                try:
                    parent = radio.query_selector("xpath=../../..")
                    parent_text = parent.inner_text().lower()
                except Exception:
                    pass
                # For authorization questions, answer yes
                if any(w in parent_text for w in ["authorized", "legally", "eligible", "work in"]):
                    if "yes" in val or "true" in val:
                        self._human_click(radio)
                        self._human_delay(200, 400)
            except Exception:
                continue

    def _click_next_or_submit_indeed(self) -> str:
        """Click Indeed's Next/Submit/Continue button."""
        submit_patterns = [
            ("button:has-text('Submit your application')", "submitted"),
            ("button:has-text('Submit application')", "submitted"),
            ("button[type='submit']:has-text('Submit')", "submitted"),
            ("button:has-text('Continue')", "next"),
            ("button:has-text('Next')", "next"),
            (".ia-continueButton", "next"),
            ("button[type='submit']", "next"),
        ]
        for sel, action in submit_patterns:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible() and btn.is_enabled():
                    self._human_click(btn)
                    self._human_delay(1500, 2500)
                    if action == "submitted":
                        self._human_delay(2000, 3000)
                    return action
            except Exception:
                continue
        return "none"
