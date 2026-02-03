import io
import re
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import-untyped]


class GoogleSlidesService:
    """Google Slides certificate generation service."""

    SCOPES = [
        "https://www.googleapis.com/auth/presentations",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._slides_service = None
        self._drive_service = None

    def _get_credentials(self) -> service_account.Credentials:
        """Get Google service account credentials from config."""
        credentials_info = {
            "type": self.config["type"],
            "project_id": self.config["project_id"],
            "private_key_id": self.config["private_key_id"],
            "private_key": self.config["private_key"],
            "client_email": self.config["client_email"],
            "client_id": self.config["client_id"],
            "auth_uri": self.config["auth_uri"],
            "token_uri": self.config["token_uri"],
            "auth_provider_x509_cert_url": self.config["auth_provider_x509_cert_url"],
            "client_x509_cert_url": self.config["client_x509_cert_url"],
        }
        return service_account.Credentials.from_service_account_info(  # type: ignore[no-any-return,no-untyped-call]
            credentials_info, scopes=self.SCOPES
        )

    def _get_slides_service(self) -> Any:
        """Get or create Google Slides API service."""
        if self._slides_service is None:
            credentials = self._get_credentials()
            self._slides_service = build("slides", "v1", credentials=credentials)
        return self._slides_service

    def _get_drive_service(self) -> Any:
        """Get or create Google Drive API service."""
        if self._drive_service is None:
            credentials = self._get_credentials()
            self._drive_service = build("drive", "v3", credentials=credentials)
        return self._drive_service

    @staticmethod
    def extract_presentation_id(url: str) -> str:
        """
        Extract presentation ID from Google Slides URL.

        Handles URLs like:
        - https://docs.google.com/presentation/d/PRESENTATION_ID/edit
        - https://docs.google.com/presentation/d/PRESENTATION_ID/edit#slide=id.p
        - https://docs.google.com/presentation/u/0/d/PRESENTATION_ID/edit
        """
        match = re.search(r"/presentation(?:/u/\d+)?/d/([a-zA-Z0-9-_]+)", url)
        if match:
            return match.group(1)
        raise ValueError(f"Could not extract presentation ID from URL: {url}")

    def copy_presentation(self, template_id: str, title: str) -> str:
        """
        Copy a presentation template.

        Args:
            template_id: ID of the template presentation
            title: Title for the new presentation

        Returns:
            ID of the copied presentation
        """
        drive = self._get_drive_service()
        copy = (
            drive.files()
            .copy(fileId=template_id, body={"name": title}, supportsAllDrives=True)
            .execute()
        )
        return str(copy["id"])

    def replace_placeholders(
        self, presentation_id: str, replacements: dict[str, str]
    ) -> None:
        """
        Replace text placeholders in presentation using Google Slides API.

        Args:
            presentation_id: ID of the presentation to modify
            replacements: Dict of placeholder -> replacement value
        """
        slides = self._get_slides_service()

        requests = []
        for placeholder, value in replacements.items():
            requests.append(
                {
                    "replaceAllText": {
                        "containsText": {"text": placeholder, "matchCase": True},
                        "replaceText": value,
                    }
                }
            )

        if requests:
            slides.presentations().batchUpdate(
                presentationId=presentation_id, body={"requests": requests}
            ).execute()

    def export_as_pdf(self, presentation_id: str) -> bytes:
        """
        Export presentation as PDF.

        Args:
            presentation_id: ID of the presentation to export

        Returns:
            PDF file contents as bytes
        """
        drive = self._get_drive_service()
        request = drive.files().export_media(
            fileId=presentation_id, mimeType="application/pdf"
        )

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        fh.seek(0)
        return fh.read()

    def delete_presentation(self, presentation_id: str) -> None:
        """
        Delete a presentation (cleanup after PDF generation).

        For Shared Drives, this moves the file to trash since service accounts
        with Content Manager role cannot permanently delete files.

        Args:
            presentation_id: ID of the presentation to delete
        """
        drive = self._get_drive_service()
        # Use trash (update with trashed=True) instead of delete for Shared Drive compatibility
        drive.files().update(
            fileId=presentation_id,
            body={"trashed": True},
            supportsAllDrives=True,
        ).execute()

    def test_connection(self) -> bool:
        """
        Test if the service account can access Google APIs.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            drive = self._get_drive_service()
            drive.files().list(pageSize=1).execute()
            return True
        except Exception:
            return False

    def generate_certificate_pdf(
        self,
        template_url: str,
        candidate_name: str,
        test_name: str,
        completion_date: str,
        score: str,
        certificate_title: str = "Certificate",
    ) -> bytes:
        """
        Generate a certificate PDF from a Google Slides template.

        Args:
            template_url: Google Slides URL of the template
            candidate_name: Name to replace {{candidate_name}}
            test_name: Name to replace {{test_name}}
            completion_date: Date to replace {{completion_date}}
            score: Score to replace {{score}}
            certificate_title: Title for the copied presentation

        Returns:
            PDF file contents as bytes
        """
        template_id = self.extract_presentation_id(template_url)
        copy_id = None

        try:
            # Copy the template
            copy_id = self.copy_presentation(template_id, certificate_title)

            # Replace placeholders using Google Slides API
            replacements = {
                "{{candidate_name}}": candidate_name,
                "{{test_name}}": test_name,
                "{{completion_date}}": completion_date,
                "{{score}}": score,
            }
            self.replace_placeholders(copy_id, replacements)

            # Export as PDF
            pdf_bytes = self.export_as_pdf(copy_id)

            return pdf_bytes

        finally:
            # Always cleanup the copy
            if copy_id:
                try:
                    self.delete_presentation(copy_id)
                except Exception:
                    pass  # Log but don't fail on cleanup
