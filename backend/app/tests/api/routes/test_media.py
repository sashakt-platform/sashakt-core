"""Tests for media API routes and helper functions."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.deps import SessionDep
from app.api.routes.media import find_option, rebuild_options
from app.api.routes.question import (
    enrich_media_with_signed_urls,
    enrich_options_with_signed_urls,
    serialize_options,
)
from app.core.config import settings
from app.models.question import (
    MatrixColumn,
    MatrixMatchOptions,
    Option,
    Question,
    QuestionRevision,
    QuestionType,
)
from app.tests.utils.files import create_test_image
from app.tests.utils.user import get_current_user_data
from app.tests.utils.utils import random_lower_string

MEDIA_PREFIX = f"{settings.API_V1_STR}/media"


# --- Helper: create question with revision in DB ---


def create_question_with_revision(
    db: Session,
    organization_id: int,
    user_id: int,
    options: list[Option] | MatrixMatchOptions | None = None,
) -> tuple[Question, QuestionRevision]:
    """Create a question and revision for testing."""
    if options is None:
        options = [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ]

    question = Question(organization_id=organization_id)
    db.add(question)
    db.commit()
    db.refresh(question)

    revision = QuestionRevision(
        question_id=question.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=options,
        correct_answer=[1],
        is_mandatory=True,
        is_active=True,
        created_by_id=user_id,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)

    question.last_revision_id = revision.id
    db.add(question)
    db.commit()
    db.refresh(question)

    return question, revision


# =====================================================================
# Unit tests for helper functions (no DB needed)
# =====================================================================


class TestFindOption:
    """Tests for find_option helper."""

    def test_find_in_flat_list(self) -> None:
        options: list[Option] = [
            {"id": 1, "key": "A", "value": "Opt 1"},
            {"id": 2, "key": "B", "value": "Opt 2"},
        ]
        items, index, matrix_key = find_option(options, 2)
        assert index == 1
        assert matrix_key is None
        assert items is options

    def test_find_in_matrix_rows(self) -> None:
        options = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Rows",
                items=[
                    {"id": 1, "key": "P", "value": "Item P"},
                    {"id": 2, "key": "Q", "value": "Item Q"},
                ],
            ),
            columns=MatrixColumn(
                label="Cols",
                items=[
                    {"id": 10, "key": "1", "value": "Item 1"},
                ],
            ),
        )
        items, index, matrix_key = find_option(options, 2)
        assert index == 1
        assert matrix_key == "rows"

    def test_find_in_matrix_columns(self) -> None:
        options = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Rows",
                items=[{"id": 1, "key": "P", "value": "Item P"}],
            ),
            columns=MatrixColumn(
                label="Cols",
                items=[
                    {"id": 10, "key": "1", "value": "Item 1"},
                    {"id": 20, "key": "2", "value": "Item 2"},
                ],
            ),
        )
        items, index, matrix_key = find_option(options, 20)
        assert index == 1
        assert matrix_key == "columns"

    def test_not_found_raises_404(self) -> None:
        options: list[Option] = [{"id": 1, "key": "A", "value": "Opt 1"}]
        with pytest.raises(HTTPException) as exc_info:
            find_option(options, 999)
        assert exc_info.value.status_code == 404

    def test_none_options_raises_404(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            find_option(None, 1)
        assert exc_info.value.status_code == 404

    def test_not_found_in_matrix_raises_404(self) -> None:
        options = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Rows",
                items=[{"id": 1, "key": "P", "value": "P"}],
            ),
            columns=MatrixColumn(
                label="Cols",
                items=[{"id": 10, "key": "1", "value": "1"}],
            ),
        )
        with pytest.raises(HTTPException) as exc_info:
            find_option(options, 999)
        assert exc_info.value.status_code == 404


class TestRebuildOptions:
    """Tests for rebuild_options helper."""

    def test_flat_list(self) -> None:
        updated: list[Option] = [{"id": 1, "key": "A", "value": "Updated"}]
        result = rebuild_options(None, updated, None)
        assert result == updated

    def test_matrix_rows(self) -> None:
        original = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Rows",
                items=[{"id": 1, "key": "P", "value": "P"}],
            ),
            columns=MatrixColumn(
                label="Cols",
                items=[{"id": 10, "key": "1", "value": "1"}],
            ),
        )
        updated: list[Option] = [{"id": 1, "key": "P", "value": "Updated"}]
        result = rebuild_options(original, updated, "rows")
        assert isinstance(result, dict)
        assert result["rows"]["items"] == updated
        # Columns unchanged
        assert result["columns"]["items"] == original["columns"]["items"]

    def test_matrix_columns(self) -> None:
        original = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Rows",
                items=[{"id": 1, "key": "P", "value": "P"}],
            ),
            columns=MatrixColumn(
                label="Cols",
                items=[{"id": 10, "key": "1", "value": "1"}],
            ),
        )
        updated: list[Option] = [{"id": 10, "key": "1", "value": "Updated"}]
        result = rebuild_options(original, updated, "columns")
        assert isinstance(result, dict)
        assert result["columns"]["items"] == updated
        assert result["rows"]["items"] == original["rows"]["items"]


class TestSerializeOptions:
    """Tests for serialize_options."""

    def test_none_returns_none(self) -> None:
        assert serialize_options(None) is None

    def test_empty_list_returns_none(self) -> None:
        assert serialize_options([]) is None

    def test_flat_list_passthrough(self) -> None:
        options: list[Option] = [
            {"id": 1, "key": "A", "value": "Opt 1"},
            {"id": 2, "key": "B", "value": "Opt 2"},
        ]
        result = serialize_options(options)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_matrix_match_passthrough(self) -> None:
        options = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Rows",
                items=[{"id": 1, "key": "P", "value": "P"}],
            ),
            columns=MatrixColumn(
                label="Cols",
                items=[{"id": 10, "key": "1", "value": "1"}],
            ),
        )
        result = serialize_options(options)
        assert isinstance(result, dict)
        assert "rows" in result
        assert "columns" in result


class TestEnrichMediaWithSignedUrls:
    """Tests for enrich_media_with_signed_urls."""

    def test_none_media_returns_none(self) -> None:
        assert enrich_media_with_signed_urls(None, None) is None

    def test_no_gcs_service_returns_unchanged(self) -> None:
        media: dict[str, Any] = {"image": {"gcs_path": "some/path"}}
        result = enrich_media_with_signed_urls(media, None)
        assert result == media

    def test_adds_signed_url_to_image(self) -> None:
        gcs_service = MagicMock()
        gcs_service.generate_signed_url.return_value = "https://signed-url.example.com"
        media: dict[str, Any] = {"image": {"gcs_path": "org_1/q_1.png"}}
        result = enrich_media_with_signed_urls(media, gcs_service)
        assert result is not None
        assert result["image"]["url"] == "https://signed-url.example.com"
        gcs_service.generate_signed_url.assert_called_once_with("org_1/q_1.png")

    def test_no_image_key_unchanged(self) -> None:
        gcs_service = MagicMock()
        media: dict[str, Any] = {"external_media": {"provider": "youtube"}}
        result = enrich_media_with_signed_urls(media, gcs_service)
        assert result is not None
        assert "image" not in result
        gcs_service.generate_signed_url.assert_not_called()

    def test_gcs_error_logged_not_raised(self) -> None:
        gcs_service = MagicMock()
        gcs_service.generate_signed_url.side_effect = Exception("GCS error")
        media: dict[str, Any] = {"image": {"gcs_path": "org_1/q_1.png"}}
        result = enrich_media_with_signed_urls(media, gcs_service)
        assert result is not None
        assert "url" not in result["image"]


class TestEnrichOptionsWithSignedUrls:
    """Tests for enrich_options_with_signed_urls."""

    def test_none_returns_none(self) -> None:
        assert enrich_options_with_signed_urls(None, None) is None

    def test_no_gcs_service_returns_unchanged(self) -> None:
        options: list[Option] = [{"id": 1, "key": "A", "value": "Opt"}]
        result = enrich_options_with_signed_urls(options, None)
        assert result == options

    def test_enriches_flat_list_option_media(self) -> None:
        gcs_service = MagicMock()
        gcs_service.generate_signed_url.return_value = "https://signed.example.com"
        options: list[Option] = [
            {
                "id": 1,
                "key": "A",
                "value": "Opt",
                "media": {"image": {"gcs_path": "path.png"}},
            },
        ]
        result = enrich_options_with_signed_urls(options, gcs_service)
        assert result is not None
        assert isinstance(result, list)
        media = result[0].get("media")
        assert media is not None
        assert media["image"]["url"] == "https://signed.example.com"

    def test_enriches_matrix_match_options(self) -> None:
        gcs_service = MagicMock()
        gcs_service.generate_signed_url.return_value = "https://signed.example.com"
        options = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Rows",
                items=[
                    {
                        "id": 1,
                        "key": "P",
                        "value": "P",
                        "media": {"image": {"gcs_path": "row.png"}},
                    },
                ],
            ),
            columns=MatrixColumn(
                label="Cols",
                items=[
                    {
                        "id": 10,
                        "key": "1",
                        "value": "1",
                        "media": {"image": {"gcs_path": "col.png"}},
                    },
                ],
            ),
        )
        result = enrich_options_with_signed_urls(options, gcs_service)
        assert result is not None
        assert isinstance(result, dict)
        row_media = result["rows"]["items"][0].get("media")
        assert row_media is not None
        assert row_media["image"]["url"] == "https://signed.example.com"
        col_media = result["columns"]["items"][0].get("media")
        assert col_media is not None
        assert col_media["image"]["url"] == "https://signed.example.com"
        assert gcs_service.generate_signed_url.call_count == 2

    def test_options_without_media_unchanged(self) -> None:
        gcs_service = MagicMock()
        options: list[Option] = [
            {"id": 1, "key": "A", "value": "Opt"},
        ]
        result = enrich_options_with_signed_urls(options, gcs_service)
        assert result is not None
        assert isinstance(result, list)
        gcs_service.generate_signed_url.assert_not_called()


# =====================================================================
# Integration tests for media API routes (mocked GCS)
# =====================================================================


def _setup_question(
    db: Session,
    client: TestClient,
    token: dict[str, str],
    options: list[Option] | MatrixMatchOptions | None = None,
) -> tuple[Question, QuestionRevision]:
    """Create org + question for media endpoint tests."""
    user_data = get_current_user_data(client, token)
    user_id = user_data["id"]
    org_id = user_data["organization_id"]
    return create_question_with_revision(db, org_id, user_id, options)


def _mock_gcs() -> MagicMock:
    """Create a mock GCS service."""
    gcs = MagicMock()
    gcs.generate_media_path.return_value = "org_1/questions/q_1_abc.png"
    gcs.upload.return_value = "org_1/questions/q_1_abc.png"
    gcs.delete.return_value = True
    return gcs


class TestQuestionImageUpload:
    """Tests for POST /media/questions/{id}/image."""

    @patch("app.api.routes.media.get_gcs_service")
    def test_upload_image(
        self,
        mock_get_gcs: MagicMock,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        mock_get_gcs.return_value = _mock_gcs()
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        img = create_test_image()
        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/image",
            files={"file": ("test.png", img, "image/png")},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200
        data = response.json()
        assert "gcs_path" in data
        assert data["content_type"] == "image/png"
        assert data["size_bytes"] > 0

    def test_upload_image_question_not_found(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        img = create_test_image()
        response = client.post(
            f"{MEDIA_PREFIX}/questions/999999/image",
            files={"file": ("test.png", img, "image/png")},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 404

    @patch("app.api.routes.media.get_gcs_service")
    def test_upload_image_updates_revision_media(
        self,
        mock_get_gcs: MagicMock,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        mock_get_gcs.return_value = _mock_gcs()
        question, revision = _setup_question(db, client, get_user_superadmin_token)

        img = create_test_image()
        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/image",
            files={"file": ("test.png", img, "image/png")},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200

        db.expire_all()
        updated_revision = db.get(QuestionRevision, revision.id)
        assert updated_revision is not None
        assert updated_revision.media is not None
        assert "image" in updated_revision.media


class TestQuestionImageDelete:
    """Tests for DELETE /media/questions/{id}/image."""

    @patch("app.api.routes.media.get_gcs_service")
    def test_delete_image(
        self,
        mock_get_gcs: MagicMock,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        mock_get_gcs.return_value = _mock_gcs()
        question, revision = _setup_question(db, client, get_user_superadmin_token)

        # Set up media on revision
        revision.media = {
            "image": {"gcs_path": "org_1/q_1.png", "content_type": "image/png"}
        }
        db.add(revision)
        db.commit()

        response = client.delete(
            f"{MEDIA_PREFIX}/questions/{question.id}/image",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Image deleted successfully"

        db.expire_all()
        updated_revision = db.get(QuestionRevision, revision.id)
        assert updated_revision is not None
        assert updated_revision.media is None or "image" not in updated_revision.media

    def test_delete_image_no_image(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        response = client.delete(
            f"{MEDIA_PREFIX}/questions/{question.id}/image",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 404


class TestQuestionExternalMedia:
    """Tests for POST/DELETE /media/questions/{id}/external."""

    def test_add_youtube_media(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/external",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "youtube"
        assert data["type"] == "video"
        assert data["embed_url"] is not None

    def test_add_invalid_url(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/external",
            params={"url": "not-a-url"},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 400

    def test_delete_external_media(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, revision = _setup_question(db, client, get_user_superadmin_token)

        revision.media = {
            "external_media": {
                "type": "video",
                "provider": "youtube",
                "url": "https://youtube.com/watch?v=abc",
            }
        }
        db.add(revision)
        db.commit()

        response = client.delete(
            f"{MEDIA_PREFIX}/questions/{question.id}/external",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200

        db.expire_all()
        updated_revision = db.get(QuestionRevision, revision.id)
        assert updated_revision is not None
        assert (
            updated_revision.media is None
            or "external_media" not in updated_revision.media
        )

    def test_delete_external_media_not_found(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        response = client.delete(
            f"{MEDIA_PREFIX}/questions/{question.id}/external",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 404


class TestOptionImageUpload:
    """Tests for POST/DELETE /media/questions/{id}/options/{opt_id}/image."""

    @patch("app.api.routes.media.get_gcs_service")
    def test_upload_option_image(
        self,
        mock_get_gcs: MagicMock,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        mock_get_gcs.return_value = _mock_gcs()
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        img = create_test_image()
        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/1/image",
            files={"file": ("test.png", img, "image/png")},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200
        data = response.json()
        assert "gcs_path" in data

    @patch("app.api.routes.media.get_gcs_service")
    def test_upload_option_image_matrix_match(
        self,
        mock_get_gcs: MagicMock,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        """Test uploading image to a matrix match question option."""
        mock_get_gcs.return_value = _mock_gcs()
        matrix_options = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Column A",
                items=[
                    {"id": 1, "key": "P", "value": "Item P"},
                    {"id": 2, "key": "Q", "value": "Item Q"},
                ],
            ),
            columns=MatrixColumn(
                label="Column B",
                items=[
                    {"id": 10, "key": "1", "value": "Item 1"},
                ],
            ),
        )
        question, revision = _setup_question(
            db, client, get_user_superadmin_token, options=matrix_options
        )

        img = create_test_image()
        # Upload to a row option
        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/1/image",
            files={"file": ("test.png", img, "image/png")},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200

        db.expire_all()
        updated_revision = db.get(QuestionRevision, revision.id)
        assert updated_revision is not None
        assert isinstance(updated_revision.options, dict)
        row_items = updated_revision.options["rows"]["items"]
        assert "media" in row_items[0]

    @patch("app.api.routes.media.get_gcs_service")
    def test_upload_option_image_matrix_column(
        self,
        mock_get_gcs: MagicMock,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        """Test uploading image to a matrix match column option."""
        mock_get_gcs.return_value = _mock_gcs()
        matrix_options = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Rows",
                items=[{"id": 1, "key": "P", "value": "Item P"}],
            ),
            columns=MatrixColumn(
                label="Cols",
                items=[
                    {"id": 10, "key": "1", "value": "Item 1"},
                    {"id": 20, "key": "2", "value": "Item 2"},
                ],
            ),
        )
        question, revision = _setup_question(
            db, client, get_user_superadmin_token, options=matrix_options
        )

        img = create_test_image()
        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/10/image",
            files={"file": ("test.png", img, "image/png")},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200

        db.expire_all()
        updated_revision = db.get(QuestionRevision, revision.id)
        assert updated_revision is not None
        assert isinstance(updated_revision.options, dict)
        col_items = updated_revision.options["columns"]["items"]
        assert "media" in col_items[0]

    def test_upload_option_not_found(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        img = create_test_image()
        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/999/image",
            files={"file": ("test.png", img, "image/png")},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 404


class TestOptionImageDelete:
    """Tests for DELETE /media/questions/{id}/options/{opt_id}/image."""

    @patch("app.api.routes.media.get_gcs_service")
    def test_delete_option_image(
        self,
        mock_get_gcs: MagicMock,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        mock_get_gcs.return_value = _mock_gcs()
        options: list[Option] = [
            {
                "id": 1,
                "key": "A",
                "value": "Opt 1",
                "media": {"image": {"gcs_path": "org_1/opt_1.png"}},
            },
            {"id": 2, "key": "B", "value": "Opt 2"},
        ]
        question, revision = _setup_question(
            db, client, get_user_superadmin_token, options=options
        )

        response = client.delete(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/1/image",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200

        db.expire_all()
        updated_revision = db.get(QuestionRevision, revision.id)
        assert updated_revision is not None
        assert isinstance(updated_revision.options, list)
        assert (
            "media" not in updated_revision.options[0]
            or updated_revision.options[0].get("media") is None
        )

    @patch("app.api.routes.media.get_gcs_service")
    def test_delete_matrix_option_image(
        self,
        mock_get_gcs: MagicMock,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        mock_get_gcs.return_value = _mock_gcs()
        matrix_options = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Rows",
                items=[
                    {
                        "id": 1,
                        "key": "P",
                        "value": "P",
                        "media": {"image": {"gcs_path": "org_1/row.png"}},
                    },
                ],
            ),
            columns=MatrixColumn(
                label="Cols",
                items=[{"id": 10, "key": "1", "value": "1"}],
            ),
        )
        question, revision = _setup_question(
            db, client, get_user_superadmin_token, options=matrix_options
        )

        response = client.delete(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/1/image",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200

        db.expire_all()
        updated_revision = db.get(QuestionRevision, revision.id)
        assert updated_revision is not None
        assert isinstance(updated_revision.options, dict)
        row_item = updated_revision.options["rows"]["items"][0]
        assert "media" not in row_item or row_item.get("media") is None

    def test_delete_option_image_no_media(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        response = client.delete(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/1/image",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 404


class TestOptionExternalMedia:
    """Tests for POST/DELETE /media/questions/{id}/options/{opt_id}/external."""

    def test_add_option_external_media(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/1/external",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "youtube"

    def test_add_matrix_option_external_media(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        matrix_options = MatrixMatchOptions(
            rows=MatrixColumn(
                label="Rows",
                items=[{"id": 1, "key": "P", "value": "P"}],
            ),
            columns=MatrixColumn(
                label="Cols",
                items=[{"id": 10, "key": "1", "value": "1"}],
            ),
        )
        question, revision = _setup_question(
            db, client, get_user_superadmin_token, options=matrix_options
        )

        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/10/external",
            params={"url": "https://vimeo.com/12345"},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200

        db.expire_all()
        updated_revision = db.get(QuestionRevision, revision.id)
        assert updated_revision is not None
        assert isinstance(updated_revision.options, dict)
        col_item = updated_revision.options["columns"]["items"][0]
        col_item_media = col_item.get("media")
        assert col_item_media is not None
        assert "external_media" in col_item_media

    def test_delete_option_external_media(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        options: list[Option] = [
            {
                "id": 1,
                "key": "A",
                "value": "Opt 1",
                "media": {
                    "external_media": {
                        "type": "video",
                        "provider": "youtube",
                        "url": "https://youtube.com/watch?v=abc",
                    }
                },
            },
        ]
        question, revision = _setup_question(
            db, client, get_user_superadmin_token, options=options
        )

        response = client.delete(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/1/external",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200

        db.expire_all()
        updated_revision = db.get(QuestionRevision, revision.id)
        assert updated_revision is not None
        assert isinstance(updated_revision.options, list)
        assert (
            "media" not in updated_revision.options[0]
            or updated_revision.options[0].get("media") is None
        )

    def test_delete_option_external_media_not_found(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        response = client.delete(
            f"{MEDIA_PREFIX}/questions/{question.id}/options/1/external",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 404


class TestPermissions:
    """Tests for permission checks on media endpoints."""

    def test_candidate_cannot_upload(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        get_user_candidate_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        img = create_test_image()
        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/image",
            files={"file": ("test.png", img, "image/png")},
            headers=get_user_candidate_token,
        )
        assert response.status_code in (401, 403)

    def test_candidate_cannot_add_external_media(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        get_user_candidate_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/external",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            headers=get_user_candidate_token,
        )
        assert response.status_code in (401, 403)

    def test_unauthenticated_request(
        self,
        client: TestClient,
        get_user_superadmin_token: dict[str, str],
        db: SessionDep,
    ) -> None:
        question, _ = _setup_question(db, client, get_user_superadmin_token)

        response = client.post(
            f"{MEDIA_PREFIX}/questions/{question.id}/external",
            params={"url": "https://www.youtube.com/watch?v=abc"},
        )
        assert response.status_code == 401
