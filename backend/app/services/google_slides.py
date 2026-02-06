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
    ]

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._slides_service = None

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

    def test_connection(self, template_url: str) -> bool:
        """
        Test if the service account can access the template presentation.

        Args:
            template_url: Google Slides URL of the template to test access

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            template_id = self.extract_presentation_id(template_url)
            slides = self._get_slides_service()
            slides.presentations().get(presentationId=template_id).execute()
            return True
        except Exception:
            return False

    def delete_slide(self, template_id: str, page_id: str) -> None:
        """
        Delete a slide from a presentation.

        Args:
            template_id: ID of the presentation
            page_id: ID of the slide to delete
        """
        try:
            slides = self._get_slides_service()
            slides.presentations().batchUpdate(
                presentationId=template_id,
                body={"requests": [{"deleteObject": {"objectId": page_id}}]},
            ).execute()
        except Exception:
            pass  # Don't fail on cleanup

    def generate_certificate_image(
        self,
        template_url: str,
        candidate_name: str,
        test_name: str,
        completion_date: str,
        score: str,
        size: str = "LARGE",
    ) -> tuple[bytes, dict[str, str]]:
        """
        Generate a certificate image from a Google Slides template.

        Flow:
        1. Duplicate the template slide and replace placeholders (single API call)
        2. Get thumbnail of the duplicated slide
        3. Return image and cleanup info (deletion handled by caller in background)

        Args:
            template_url: Google Slides URL of the template
            candidate_name: Name to replace {{candidate_name}}
            test_name: Name to replace {{test_name}}
            completion_date: Date to replace {{completion_date}}
            score: Score to replace {{score}}
            size: Image size - SMALL (200px), MEDIUM (800px), or LARGE (1600px)

        Returns:
            Tuple of (PNG image bytes, cleanup info dict with template_id and page_id)
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

        # Build combined requests: duplicate + all replacements
        replacements = {
            "{{candidate_name}}": candidate_name,
            "{{test_name}}": test_name,
            "{{completion_date}}": completion_date,
            "{{score}}": score,
        }

        requests: list[dict[str, Any]] = [
            {
                "duplicateObject": {
                    "objectId": original_page_id,
                    "objectIds": {original_page_id: new_page_id},
                }
            }
        ]
        for placeholder, value in replacements.items():
            requests.append(
                {
                    "replaceAllText": {
                        "containsText": {"text": placeholder, "matchCase": True},
                        "replaceText": value,
                        "pageObjectIds": [new_page_id],
                    }
                }
            )

        # 1. Duplicate slide and replace placeholders in a single API call
        slides.presentations().batchUpdate(
            presentationId=template_id,
            body={"requests": requests},
        ).execute()

        # 2. Get thumbnail of the duplicated slide
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

        # 3. Fetch the image (with timeout to avoid hanging indefinitely)
        with httpx.Client(timeout=15.0) as client:
            response = client.get(content_url)
            response.raise_for_status()
            image_bytes = response.content

        # Return image and cleanup info (caller handles deletion in background)
        cleanup_info = {"template_id": template_id, "page_id": new_page_id}
        return image_bytes, cleanup_info
