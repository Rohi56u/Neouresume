"""
appliers/linkedin_applier.py
LinkedIn Easy Apply automation.
Handles: login, Easy Apply modal, multi-step forms, resume upload, submission.
"""

import time
import random
import os
from typing import Dict, Optional
from datetime import datetime

from .base_applier import BaseApplier, ApplyResult, UserProfile, take_screenshot


class LinkedInApplier(BaseApplier):
    """
    Automates LinkedIn Easy Apply flow.
    
    Flow:
    1. Login to LinkedIn (or resume existing session)
    2. Navigate to job URL
    3. Click Easy Apply button
    4. Fill multi-step form (contact info, resume, screening questions)
    5. Submit application
    6. Log result to database
    """

    LOGIN_URL = "https://www.linkedin.com/login"
    SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".linkedin_session.json")

    def __init__(self, profile: UserProfile, headless: bool = True):
        super().__init__(profile, headless)
        self._logged_in = False

    @property
    def platform_name(self) -> str:
        return "LinkedIn"

    # ── Login ──────────────────────────────────────────────────────────────────
    def _restore_session(self) -> bool:
        """Try to restore saved LinkedIn session cookies."""
        if not os.path.exists(self.SESSION_FILE):
            return False
        try:
            import json
            with open(self.SESSION_FILE, "r") as f:
                cookies = json.load(f)
            self._context.add_cookies(cookies)
            self._page.goto("https://www.linkedin.com/feed", wait_until="domcontentloaded", timeout=20000)
            self._human_delay(2000, 3000)
            # Check if still logged in
            if "feed" in self._page.url or "mynetwork" in self._page.url:
                print("  [LinkedIn] Session restored ✓")
                return True
        except Exception:
            pass
        return False

    def _save_session(self):
        """Save LinkedIn session cookies for reuse."""
        try:
            import json
            cookies = self._context.cookies()
            with open(self.SESSION_FILE, "w") as f:
                json.dump(cookies, f)
        except Exception:
            pass

    def _login(self) -> bool:
        """Login to LinkedIn with credentials from profile."""
        if not self.profile.linkedin_email or not self.profile.linkedin_password:
            return False

        try:
            print("  [LinkedIn] Logging in...")
            self._page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
            self._human_delay(1500, 2500)

            # Fill email
            email_field = self._page.query_selector("#username")
            if not email_field:
                return False
            self._human_type(email_field, self.profile.linkedin_email)
            self._human_delay(500, 900)

            # Fill password
            pass_field = self._page.query_selector("#password")
            if not pass_field:
                return False
            self._human_type(pass_field, self.profile.linkedin_password)
            self._human_delay(600, 1000)

            # Click login
            self._safe_click("button[type='submit']")
            self._human_delay(3000, 5000)

            # Check for CAPTCHA or verification
            if self._detect_captcha():
                print("  [LinkedIn] CAPTCHA detected — manual intervention needed")
                return False

            # Check for 2FA or phone verification
            if "checkpoint" in self._page.url or "verification" in self._page.url:
                print("  [LinkedIn] Verification required — check your phone/email")
                time.sleep(30)  # Give user time to verify

            # Check if logged in
            if "feed" in self._page.url or "mynetwork" in self._page.url:
                print("  [LinkedIn] Login successful ✓")
                self._save_session()
                self._logged_in = True
                return True

            print(f"  [LinkedIn] Login failed — URL: {self._page.url}")
            return False

        except Exception as e:
            print(f"  [LinkedIn] Login error: {e}")
            return False

    def _ensure_logged_in(self) -> bool:
        """Ensure we're logged in, restore session or re-login."""
        if self._logged_in:
            return True
        if self._restore_session():
            self._logged_in = True
            return True
        return self._login()

    # ── Apply Flow ─────────────────────────────────────────────────────────────
    def apply(self, job: Dict, resume_pdf_path: str, cover_letter: str = "") -> ApplyResult:
        """Apply to a LinkedIn job via Easy Apply."""
        self._start_timer()
        job_id = job.get("id", 0)
        url = job.get("url", "")
        title = job.get("title", "")
        company = job.get("company", "")

        if not url:
            return ApplyResult("failed", job_id, "LinkedIn", "No job URL provided")

        try:
            self._init_browser()

            # Login check
            if not self._ensure_logged_in():
                return ApplyResult(
                    "failed", job_id, "LinkedIn",
                    "LinkedIn login failed. Add LINKEDIN_EMAIL and LINKEDIN_PASSWORD to .env"
                )

            print(f"  [LinkedIn] Applying to: {title} @ {company}")

            # Navigate to job
            self._page.goto(url, wait_until="domcontentloaded", timeout=25000)
            self._human_delay(2000, 3500)
            self._move_mouse_randomly()

            # Check for CAPTCHA
            if self._detect_captcha():
                screenshot = take_screenshot(self._page, f"captcha_{job_id}")
                return ApplyResult("captcha", job_id, "LinkedIn", "CAPTCHA detected", screenshot, self._get_elapsed())

            # Check if already applied
            if self._detect_already_applied():
                return ApplyResult("already_applied", job_id, "LinkedIn", "Already applied to this job", "", self._get_elapsed())

            # Find Easy Apply button
            easy_apply_btn = self._find_easy_apply_button()
            if not easy_apply_btn:
                screenshot = take_screenshot(self._page, f"no_easy_apply_{job_id}")
                return ApplyResult("skipped", job_id, "LinkedIn", "No Easy Apply button found — may require external application", screenshot, self._get_elapsed())

            # Click Easy Apply
            self._human_click(easy_apply_btn)
            self._human_delay(1500, 2500)

            # Handle multi-step modal
            result = self._handle_apply_modal(job_id, resume_pdf_path, cover_letter)
            return result

        except Exception as e:
            screenshot = take_screenshot(self._page, f"error_{job_id}") if self._page else ""
            return ApplyResult("failed", job_id, "LinkedIn", f"Error: {str(e)}", screenshot, self._get_elapsed())
        finally:
            self._close_browser()

    def _find_easy_apply_button(self):
        """Find the Easy Apply button on job page."""
        selectors = [
            "button.jobs-apply-button",
            "button[aria-label*='Easy Apply']",
            "button.jobs-s-apply button",
            ".jobs-apply-button--top-card button",
            "button:has-text('Easy Apply')",
            ".jobs-apply-button",
        ]
        for selector in selectors:
            try:
                btn = self._page.query_selector(selector)
                if btn and btn.is_visible():
                    text = btn.inner_text().lower()
                    if "easy apply" in text or "apply" in text:
                        return btn
            except Exception:
                continue
        return None

    def _handle_apply_modal(self, job_id: int, resume_pdf_path: str, cover_letter: str) -> ApplyResult:
        """Handle the multi-step Easy Apply modal."""
        max_steps = 8
        step = 0

        while step < max_steps:
            step += 1
            self._human_delay(1000, 2000)

            # Check for modal
            modal = self._page.query_selector(".jobs-easy-apply-modal, [aria-label='Easy Apply']")
            if not modal:
                # Modal may have closed after successful submission
                if self._detect_already_applied() or "submitted" in self._page.content().lower():
                    return ApplyResult("success", job_id, "LinkedIn", f"Application submitted! (Step {step})", "", self._get_elapsed())
                break

            page_content = self._page.content().lower()

            # ── Contact Info Step ──────────────────────────────────────────────
            self._fill_contact_info()

            # ── Resume Upload Step ─────────────────────────────────────────────
            resume_input = self._page.query_selector("input[type='file']")
            if resume_input and resume_pdf_path and os.path.exists(resume_pdf_path):
                try:
                    self._page.set_input_files("input[type='file']", resume_pdf_path)
                    self._human_delay(1000, 2000)
                except Exception:
                    pass

            # ── Cover Letter Step ──────────────────────────────────────────────
            if cover_letter:
                self._fill_cover_letter(cover_letter)

            # ── Answer Screening Questions ─────────────────────────────────────
            self._answer_screening_questions()

            # ── Click Next or Submit ───────────────────────────────────────────
            action = self._click_next_or_submit()

            if action == "submitted":
                screenshot = take_screenshot(self._page, f"success_{job_id}")
                return ApplyResult("success", job_id, "LinkedIn", "Application submitted successfully!", screenshot, self._get_elapsed())
            elif action == "error":
                screenshot = take_screenshot(self._page, f"error_{job_id}")
                return ApplyResult("failed", job_id, "LinkedIn", "Form submission error", screenshot, self._get_elapsed())
            elif action == "none":
                screenshot = take_screenshot(self._page, f"stuck_{job_id}")
                return ApplyResult("failed", job_id, "LinkedIn", f"Could not proceed past step {step}", screenshot, self._get_elapsed())

        screenshot = take_screenshot(self._page, f"maxsteps_{job_id}")
        return ApplyResult("failed", job_id, "LinkedIn", f"Exceeded max steps ({max_steps})", screenshot, self._get_elapsed())

    def _fill_contact_info(self):
        """Fill contact info fields in modal."""
        try:
            fields = {
                "input[id*='phoneNumber'], input[placeholder*='phone'], input[name*='phone']": self.profile.phone,
                "input[id*='firstName'], input[placeholder*='First name']": self.profile.full_name.split()[0] if self.profile.full_name else "",
                "input[id*='lastName'], input[placeholder*='Last name']": self.profile.full_name.split()[-1] if self.profile.full_name else "",
                "input[id*='email'], input[type='email']": self.profile.email,
                "input[id*='city'], input[placeholder*='City']": self.profile.location,
            }
            for selector, value in fields.items():
                if value:
                    try:
                        el = self._page.query_selector(selector)
                        if el and el.is_visible():
                            current = el.input_value() or ""
                            if not current.strip():
                                self._human_type(el, value)
                                self._human_delay(200, 500)
                    except Exception:
                        continue
        except Exception:
            pass

    def _fill_cover_letter(self, cover_letter: str):
        """Fill cover letter textarea if present."""
        try:
            selectors = [
                "textarea[id*='cover'], textarea[placeholder*='cover']",
                "textarea[id*='message'], textarea[placeholder*='message']",
                ".jobs-easy-apply-form-section textarea",
                "textarea",
            ]
            for selector in selectors:
                try:
                    el = self._page.query_selector(selector)
                    if el and el.is_visible():
                        current = el.input_value() or ""
                        if not current.strip():
                            self._human_type(el, cover_letter[:2000])  # LinkedIn has char limits
                            self._human_delay(300, 600)
                            break
                except Exception:
                    continue
        except Exception:
            pass

    def _answer_screening_questions(self):
        """
        Handle common screening questions intelligently.
        Uses profile data for known questions, defaults for unknown.
        """
        try:
            # Dropdowns / Selects
            selects = self._page.query_selector_all("select")
            for select in selects:
                try:
                    if not select.is_visible():
                        continue
                    # Get label text for context
                    parent_text = ""
                    try:
                        parent = select.query_selector("xpath=../..")
                        parent_text = parent.inner_text().lower() if parent else ""
                    except Exception:
                        pass

                    options = select.query_selector_all("option")
                    if len(options) <= 1:
                        continue

                    # Smart selection based on context
                    selected = False
                    if "experience" in parent_text or "years" in parent_text:
                        # Try to match years of experience
                        yoe = self.profile.years_experience or "3"
                        for opt in options:
                            opt_text = opt.inner_text().lower()
                            if yoe in opt_text or str(yoe) in opt_text:
                                select.select_option(value=opt.get_attribute("value") or "")
                                selected = True
                                break
                    elif "notice" in parent_text:
                        for opt in options:
                            opt_text = opt.inner_text().lower()
                            if "immediate" in opt_text or "0" in opt_text:
                                select.select_option(value=opt.get_attribute("value") or "")
                                selected = True
                                break
                    elif "relocat" in parent_text:
                        for opt in options:
                            opt_text = opt.inner_text().lower()
                            if "yes" in opt_text:
                                select.select_option(value=opt.get_attribute("value") or "")
                                selected = True
                                break

                    if not selected and len(options) > 1:
                        # Select first non-empty option as fallback
                        for opt in options[1:]:
                            val = opt.get_attribute("value")
                            if val and val.strip():
                                select.select_option(value=val)
                                break

                    self._human_delay(200, 500)
                except Exception:
                    continue

            # Radio buttons — Yes/No questions
            radio_groups = {}
            radios = self._page.query_selector_all("input[type='radio']")
            for radio in radios:
                try:
                    name = radio.get_attribute("name") or ""
                    if name not in radio_groups:
                        radio_groups[name] = []
                    radio_groups[name].append(radio)
                except Exception:
                    continue

            for name, group in radio_groups.items():
                try:
                    # Check if any in group is already selected
                    already_selected = any(
                        r.evaluate("el => el.checked") for r in group
                    )
                    if already_selected:
                        continue

                    # Get context
                    context_text = ""
                    try:
                        parent = group[0].query_selector("xpath=../../..")
                        context_text = parent.inner_text().lower() if parent else ""
                    except Exception:
                        pass

                    # Smart selection
                    if any(word in context_text for word in ["legally", "authorized", "eligible", "citizen", "work"]):
                        # Select "Yes"
                        for r in group:
                            label = (r.get_attribute("value") or r.get_attribute("id") or "").lower()
                            if "yes" in label or "1" == label or "true" in label:
                                self._human_click(r)
                                break
                        else:
                            if group:
                                self._human_click(group[0])
                    elif any(word in context_text for word in ["sponsor", "visa", "require"]):
                        # Select "No" for sponsorship
                        for r in group:
                            label = (r.get_attribute("value") or "").lower()
                            if "no" in label or "0" == label or "false" in label:
                                self._human_click(r)
                                break
                        else:
                            if len(group) > 1:
                                self._human_click(group[-1])
                    else:
                        # Default: select first option
                        if group:
                            self._human_click(group[0])

                    self._human_delay(200, 400)
                except Exception:
                    continue

            # Text inputs that are screening questions
            text_inputs = self._page.query_selector_all(
                ".jobs-easy-apply-form-element input[type='text']:not([value]), "
                ".jobs-easy-apply-form-element input[type='number']"
            )
            for inp in text_inputs:
                try:
                    if not inp.is_visible():
                        continue
                    current_val = inp.input_value() or ""
                    if current_val.strip():
                        continue

                    # Get label
                    label_text = ""
                    try:
                        label_el = self._page.query_selector(
                            f"label[for='{inp.get_attribute('id')}']"
                        )
                        if label_el:
                            label_text = label_el.inner_text().lower()
                    except Exception:
                        pass

                    # Fill based on context
                    if "salary" in label_text or "ctc" in label_text or "compensation" in label_text:
                        value = self.profile.expected_ctc or "600000"
                    elif "notice" in label_text:
                        value = "0" if "immediate" in self.profile.notice_period.lower() else "30"
                    elif "experience" in label_text or "years" in label_text:
                        value = self.profile.years_experience or "3"
                    elif "website" in label_text or "portfolio" in label_text:
                        value = self.profile.portfolio_url or self.profile.linkedin_url or ""
                    elif "linkedin" in label_text:
                        value = self.profile.linkedin_url or ""
                    elif "github" in label_text:
                        value = self.profile.portfolio_url or ""
                    else:
                        continue  # Skip unknown fields

                    if value:
                        self._human_type(inp, str(value))
                        self._human_delay(200, 500)
                except Exception:
                    continue

        except Exception:
            pass

    def _click_next_or_submit(self) -> str:
        """
        Find and click Next/Submit/Review button in modal.
        Returns: 'next' | 'submitted' | 'error' | 'none'
        """
        # Check for error messages
        error_indicators = [
            ".artdeco-inline-feedback--error",
            "[data-test-form-element-error-message]",
            ".jobs-easy-apply-form-section__warning",
        ]
        for err_sel in error_indicators:
            try:
                err_el = self._page.query_selector(err_sel)
                if err_el and err_el.is_visible():
                    return "error"
            except Exception:
                pass

        # Priority order: Submit > Review > Next > Continue
        button_selectors = [
            ("button[aria-label='Submit application']", "submitted"),
            ("button:has-text('Submit application')", "submitted"),
            ("button[aria-label='Review your application']", "next"),
            ("button:has-text('Review')", "next"),
            ("button[aria-label='Continue to next step']", "next"),
            ("button:has-text('Next')", "next"),
            ("button:has-text('Continue')", "next"),
            (".artdeco-button--primary:has-text('Submit')", "submitted"),
            (".artdeco-button--primary:has-text('Next')", "next"),
            (".artdeco-button--primary", "next"),
        ]

        for selector, action in button_selectors:
            try:
                btn = self._page.query_selector(selector)
                if btn and btn.is_visible() and btn.is_enabled():
                    self._human_click(btn)
                    self._human_delay(1500, 2500)

                    # If submitted, check for confirmation
                    if action == "submitted":
                        self._human_delay(2000, 3000)
                        confirmation_selectors = [
                            "[data-test-modal-id='application-submission-modal']",
                            ".jobs-post-apply-modal",
                            "h2:has-text('Your application was sent')",
                            "h2:has-text('Application submitted')",
                        ]
                        for conf in confirmation_selectors:
                            try:
                                self._page.wait_for_selector(conf, timeout=5000)
                                return "submitted"
                            except Exception:
                                continue
                        # If no confirmation found but we clicked submit, still mark success
                        return "submitted"

                    return "next"
            except Exception:
                continue

        return "none"
