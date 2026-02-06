import re
import uuid
from typing import Any

import httpx
from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore[import-untyped]


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

    def generate_certificate_image(
        self,
        template_url: str,
        candidate_name: str,
        test_name: str,
        completion_date: str,
        score: str,
        size: str = "LARGE",
    ) -> bytes:
        """
        Generate a certificate image from a Google Slides template.

        Flow:
        1. Duplicate the template slide with a unique ID
        2. Replace placeholders on the duplicated slide only
        3. Get thumbnail of the duplicated slide
        4. Delete the duplicated slide

        Args:
            template_url: Google Slides URL of the template
            candidate_name: Name to replace {{candidate_name}}
            test_name: Name to replace {{test_name}}
            completion_date: Date to replace {{completion_date}}
            score: Score to replace {{score}}
            size: Image size - SMALL (200px), MEDIUM (800px), or LARGE (1600px)

        Returns:
            PNG image contents as bytes
        """
        template_id = self.extract_presentation_id(template_url)
        slides = self._get_slides_service()

        # Get the original slide's page ID
        presentation = slides.presentations().get(presentationId=template_id).execute()
        pages = presentation.get("slides", [])
        if not pages:
            raise ValueError("Template presentation has no slides")
        original_page_id = pages[0]["objectId"]

        # Generate a unique ID for the duplicated slide
        new_page_id = f"cert_{uuid.uuid4().hex[:12]}"

        try:
            # 1. Duplicate the template slide
            slides.presentations().batchUpdate(
                presentationId=template_id,
                body={
                    "requests": [
                        {
                            "duplicateObject": {
                                "objectId": original_page_id,
                                "objectIds": {original_page_id: new_page_id},
                            }
                        }
                    ]
                },
            ).execute()

            # 2. Replace placeholders on the duplicated slide only
            replacements = {
                "{{candidate_name}}": candidate_name,
                "{{test_name}}": test_name,
                "{{completion_date}}": completion_date,
                "{{score}}": score,
            }

            replace_requests = [
                {
                    "replaceAllText": {
                        "containsText": {"text": placeholder, "matchCase": True},
                        "replaceText": value,
                        "pageObjectIds": [new_page_id],
                    }
                }
                for placeholder, value in replacements.items()
            ]

            slides.presentations().batchUpdate(
                presentationId=template_id,
                body={"requests": replace_requests},
            ).execute()

            # 3. Get thumbnail of the duplicated slide
            thumbnail = (
                slides.presentations()
                .pages()
                .getThumbnail(
                    presentationId=template_id,
                    pageObjectId=new_page_id,
                    thumbnailProperties_thumbnailSize=size,
                )
                .execute()
            )

            content_url = thumbnail.get("contentUrl")
            if not content_url:
                raise ValueError("Failed to get thumbnail URL")

            # 4. Fetch the image
            with httpx.Client() as client:
                response = client.get(content_url)
                response.raise_for_status()
                return response.content

        finally:
            # Always cleanup: delete the duplicated slide
            try:
                slides.presentations().batchUpdate(
                    presentationId=template_id,
                    body={"requests": [{"deleteObject": {"objectId": new_page_id}}]},
                ).execute()
            except Exception:
                pass  # Don't fail on cleanup
