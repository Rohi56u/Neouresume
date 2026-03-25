"""
gmail_connector.py
Phase 5 — Gmail API integration.
Handles: OAuth2 flow, email fetching, sending replies, label management,
thread tracking, and batch email processing.

Uses Google Gmail API v1 with offline access for background monitoring.
"""

import os
import json
import base64
import re
import pickle
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ─── OAuth Scopes ────────────────────────────────────────────────────────────────
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]

TOKEN_PATH = os.path.join(os.path.dirname(__file__), ".gmail_token.pickle")
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "gmail_credentials.json")


# ─── Auth Manager ────────────────────────────────────────────────────────────────
class GmailAuth:
    """Handles Gmail OAuth2 authentication flow."""

    def __init__(self):
        self._service = None
        self._creds = None

    def is_configured(self) -> bool:
        """Check if Gmail credentials file exists."""
        return os.path.exists(CREDENTIALS_PATH)

    def is_authenticated(self) -> bool:
        """Check if we have valid tokens."""
        if not os.path.exists(TOKEN_PATH):
            return False
        try:
            with open(TOKEN_PATH, "rb") as f:
                creds = pickle.load(f)
            return creds and creds.valid
        except Exception:
            return False

    def get_auth_url(self) -> str:
        """
        Generate OAuth2 authorization URL for user to visit.
        Used in Streamlit UI to show auth link.
        """
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, GMAIL_SCOPES
            )
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            auth_url, _ = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent"
            )
            return auth_url
        except Exception as e:
            return f"ERROR: {str(e)}"

    def authenticate_with_code(self, auth_code: str) -> bool:
        """Exchange auth code for tokens and save them."""
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, GMAIL_SCOPES
            )
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            flow.fetch_token(code=auth_code.strip())
            creds = flow.credentials
            with open(TOKEN_PATH, "wb") as f:
                pickle.dump(creds, f)
            return True
        except Exception as e:
            print(f"Auth error: {e}")
            return False

    def get_service(self):
        """Get authenticated Gmail API service."""
        if self._service:
            return self._service

        try:
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = None
            if os.path.exists(TOKEN_PATH):
                with open(TOKEN_PATH, "rb") as f:
                    creds = pickle.load(f)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(TOKEN_PATH, "wb") as f:
                        pickle.dump(creds, f)
                else:
                    raise ValueError("Not authenticated. Run auth flow first.")

            self._service = build("gmail", "v1", credentials=creds)
            return self._service

        except ImportError:
            raise ImportError(
                "Google API libraries not installed!\n"
                "Run: pip install google-auth google-auth-oauthlib google-api-python-client"
            )

    def revoke(self):
        """Revoke tokens and logout."""
        if os.path.exists(TOKEN_PATH):
            os.remove(TOKEN_PATH)
        self._service = None
        self._creds = None


# ─── Email Fetcher ────────────────────────────────────────────────────────────────
class GmailFetcher:
    """Fetches and processes emails from Gmail API."""

    # Job-related search queries
    JOB_SEARCH_QUERIES = [
        "subject:(application OR interview OR opportunity OR position OR role OR offer OR shortlisted OR selected OR regret)",
        "subject:(thank you for applying OR your application OR regarding your application)",
        "subject:(interview invitation OR interview request OR schedule an interview)",
        "subject:(we regret OR unfortunately OR position has been filled OR not moving forward)",
        "from:(noreply@linkedin.com OR jobs-noreply@linkedin.com)",
        "from:(no-reply@naukri.com OR naukri)",
        "from:(indeed.com)",
    ]

    def __init__(self, auth: GmailAuth):
        self.auth = auth

    def fetch_job_emails(
        self,
        days_back: int = 30,
        max_results: int = 100,
        progress_callback=None
    ) -> List[Dict]:
        """
        Fetch all job-related emails from Gmail.

        Args:
            days_back: How many days back to search
            max_results: Max emails to fetch
            progress_callback: fn(current, total, subject)

        Returns:
            List of email dicts with full content
        """
        service = self.auth.get_service()
        all_emails = []
        seen_ids = set()

        after_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")

        for query_base in self.JOB_SEARCH_QUERIES:
            query = f"{query_base} after:{after_date}"
            try:
                result = service.users().messages().list(
                    userId="me",
                    q=query,
                    maxResults=min(max_results, 50)
                ).execute()

                messages = result.get("messages", [])
                for i, msg_ref in enumerate(messages):
                    msg_id = msg_ref["id"]
                    if msg_id in seen_ids:
                        continue
                    seen_ids.add(msg_id)

                    try:
                        email_data = self._fetch_full_email(service, msg_id)
                        if email_data:
                            all_emails.append(email_data)
                            if progress_callback:
                                progress_callback(
                                    len(all_emails),
                                    max_results,
                                    email_data.get("subject", "")[:50]
                                )
                    except Exception:
                        continue

            except Exception as e:
                print(f"  Query failed: {query_base[:50]} — {str(e)[:60]}")
                continue

        # Sort by date descending
        all_emails.sort(key=lambda x: x.get("received_at", ""), reverse=True)
        return all_emails[:max_results]

    def _fetch_full_email(self, service, message_id: str) -> Optional[Dict]:
        """Fetch full email with all parts."""
        msg = service.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

        subject = headers.get("Subject", "(No Subject)")
        sender_raw = headers.get("From", "")
        date_str = headers.get("Date", "")
        thread_id = msg.get("threadId", "")

        # Parse sender
        sender_name, sender_email = _parse_sender(sender_raw)

        # Parse date
        received_at = _parse_email_date(date_str)

        # Extract body
        body_text = _extract_body(msg.get("payload", {}))
        snippet = msg.get("snippet", "")

        # Get labels
        labels = msg.get("labelIds", [])

        return {
            "gmail_message_id": message_id,
            "thread_id": thread_id,
            "subject": subject,
            "sender_email": sender_email,
            "sender_name": sender_name,
            "received_at": received_at,
            "body_text": body_text[:5000],  # Cap at 5k chars
            "body_snippet": snippet[:300],
            "labels": labels,
            "is_read": "UNREAD" not in labels,
        }

    def fetch_single_email(self, message_id: str) -> Optional[Dict]:
        """Fetch a single email by ID."""
        service = self.auth.get_service()
        return self._fetch_full_email(service, message_id)

    def mark_as_read(self, message_id: str):
        """Mark email as read in Gmail."""
        try:
            service = self.auth.get_service()
            service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()
        except Exception:
            pass

    def send_reply(self, thread_id: str, to_email: str, subject: str,
                   body: str, original_message_id: str = "") -> bool:
        """
        Send a reply email via Gmail API.

        Args:
            thread_id: Gmail thread ID to reply to
            to_email: Recipient email address
            subject: Email subject (Re: original)
            body: Reply body text
            original_message_id: Original message ID for proper threading

        Returns:
            True if sent successfully
        """
        try:
            service = self.auth.get_service()

            # Build email message
            message = MIMEMultipart("alternative")
            message["to"] = to_email
            message["subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject

            if original_message_id:
                message["In-Reply-To"] = original_message_id
                message["References"] = original_message_id

            # Plain text part
            text_part = MIMEText(body, "plain")
            message.attach(text_part)

            # Encode
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode("utf-8")

            result = service.users().messages().send(
                userId="me",
                body={
                    "raw": raw_message,
                    "threadId": thread_id
                }
            ).execute()

            return bool(result.get("id"))

        except Exception as e:
            print(f"  Send reply error: {e}")
            return False

    def get_thread(self, thread_id: str) -> List[Dict]:
        """Get all messages in a thread."""
        try:
            service = self.auth.get_service()
            thread = service.users().threads().get(
                userId="me",
                id=thread_id,
                format="metadata"
            ).execute()
            messages = []
            for msg in thread.get("messages", []):
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                messages.append({
                    "id": msg["id"],
                    "subject": headers.get("Subject", ""),
                    "from": headers.get("From", ""),
                    "date": headers.get("Date", ""),
                    "snippet": msg.get("snippet", "")
                })
            return messages
        except Exception:
            return []


# ─── Email Parser Helpers ─────────────────────────────────────────────────────────
def _parse_sender(sender_raw: str) -> Tuple[str, str]:
    """Parse 'Name <email>' format."""
    match = re.match(r'^(.+?)\s*<(.+?)>$', sender_raw.strip())
    if match:
        name = match.group(1).strip().strip('"')
        email = match.group(2).strip()
        return name, email
    elif "@" in sender_raw:
        return sender_raw.split("@")[0], sender_raw.strip()
    return sender_raw, sender_raw


def _parse_email_date(date_str: str) -> str:
    """Parse email date to ISO format."""
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        return datetime.now().isoformat()


def _extract_body(payload: dict, max_depth: int = 5) -> str:
    """Recursively extract text body from email payload."""
    if max_depth <= 0:
        return ""

    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data", "")

    if mime_type == "text/plain" and data:
        try:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        except Exception:
            return ""

    if mime_type == "text/html" and data:
        try:
            html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            # Strip HTML tags for plain text
            clean = re.sub(r'<[^>]+>', ' ', html)
            clean = re.sub(r'\s+', ' ', clean).strip()
            return clean
        except Exception:
            return ""

    # Multi-part — recurse into parts
    parts = payload.get("parts", [])
    texts = []
    for part in parts:
        part_text = _extract_body(part, max_depth - 1)
        if part_text:
            texts.append(part_text)
            if len(" ".join(texts)) > 3000:
                break

    return " ".join(texts)
