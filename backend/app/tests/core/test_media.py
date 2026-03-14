"""Tests for core media validation and parsing utilities."""

import pytest
from fastapi import HTTPException

from app.core.media import (
    ExternalMedia,
    _extract_spotify_info,
    _extract_vimeo_id,
    _extract_youtube_id,
    _is_soundcloud_url,
    build_external_media_dict,
    build_image_media_dict,
    validate_external_media_url,
)

# --- YouTube ID extraction ---


class TestExtractYoutubeId:
    def test_standard_watch_url(self) -> None:
        assert (
            _extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            == "dQw4w9WgXcQ"
        )

    def test_short_url(self) -> None:
        assert _extract_youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self) -> None:
        assert (
            _extract_youtube_id("https://www.youtube.com/embed/dQw4w9WgXcQ")
            == "dQw4w9WgXcQ"
        )

    def test_v_url(self) -> None:
        assert (
            _extract_youtube_id("https://www.youtube.com/v/dQw4w9WgXcQ")
            == "dQw4w9WgXcQ"
        )

    def test_no_match(self) -> None:
        assert _extract_youtube_id("https://example.com/video") is None

    def test_watch_url_with_extra_params(self) -> None:
        assert (
            _extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s")
            == "dQw4w9WgXcQ"
        )


# --- Vimeo ID extraction ---


class TestExtractVimeoId:
    def test_standard_url(self) -> None:
        assert _extract_vimeo_id("https://vimeo.com/123456789") == "123456789"

    def test_no_match(self) -> None:
        assert _extract_vimeo_id("https://example.com/video") is None


# --- SoundCloud URL detection ---


class TestIsSoundcloudUrl:
    def test_main_domain(self) -> None:
        assert _is_soundcloud_url("https://soundcloud.com/artist/track") is True

    def test_subdomain(self) -> None:
        assert _is_soundcloud_url("https://m.soundcloud.com/artist/track") is True

    def test_not_soundcloud(self) -> None:
        assert _is_soundcloud_url("https://example.com") is False

    def test_substring_attack(self) -> None:
        assert _is_soundcloud_url("https://notsoundcloud.com/track") is False

    def test_suffix_attack(self) -> None:
        assert _is_soundcloud_url("https://soundcloud.com.evil.com/track") is False


# --- Spotify info extraction ---


class TestExtractSpotifyInfo:
    def test_track(self) -> None:
        result = _extract_spotify_info("https://open.spotify.com/track/abc123")
        assert result is not None
        assert result["embed_url"] == "https://open.spotify.com/embed/track/abc123"

    def test_album(self) -> None:
        result = _extract_spotify_info("https://open.spotify.com/album/xyz789")
        assert result is not None
        assert result["embed_url"] == "https://open.spotify.com/embed/album/xyz789"

    def test_playlist(self) -> None:
        result = _extract_spotify_info("https://open.spotify.com/playlist/def456")
        assert result is not None
        assert result["embed_url"] == "https://open.spotify.com/embed/playlist/def456"

    def test_no_match(self) -> None:
        assert _extract_spotify_info("https://example.com") is None


# --- validate_external_media_url ---


class TestValidateExternalMediaUrl:
    def test_youtube_url(self) -> None:
        result = validate_external_media_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        assert result.provider == "youtube"
        assert result.type == "video"
        assert result.embed_url == "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert result.thumbnail_url is not None

    def test_vimeo_url(self) -> None:
        result = validate_external_media_url("https://vimeo.com/123456")
        assert result.provider == "vimeo"
        assert result.type == "video"
        assert result.embed_url == "https://player.vimeo.com/video/123456"

    def test_soundcloud_url(self) -> None:
        result = validate_external_media_url("https://soundcloud.com/artist/track")
        assert result.provider == "soundcloud"
        assert result.type == "audio"

    def test_spotify_url(self) -> None:
        result = validate_external_media_url("https://open.spotify.com/track/abc123")
        assert result.provider == "spotify"
        assert result.type == "audio"

    def test_generic_url(self) -> None:
        result = validate_external_media_url("https://example.com/video.mp4")
        assert result.provider == "other"
        assert result.type == "video"

    def test_invalid_scheme(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_external_media_url("ftp://example.com/video")
        assert exc_info.value.status_code == 400

    def test_empty_url(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_external_media_url("")
        assert exc_info.value.status_code == 400

    def test_whitespace_stripped_before_validation(self) -> None:
        result = validate_external_media_url(
            "  https://www.youtube.com/watch?v=dQw4w9WgXcQ  "
        )
        assert result.provider == "youtube"

    def test_whitespace_only_url(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_external_media_url("   ")
        assert exc_info.value.status_code == 400


# --- build helpers ---


class TestBuildMediaDicts:
    def test_build_image_media_dict(self) -> None:
        result = build_image_media_dict(
            gcs_path="org_1/questions/q_1_abc.png",
            content_type="image/png",
            size_bytes=1024,
            alt_text="Test image",
        )
        assert result["gcs_path"] == "org_1/questions/q_1_abc.png"
        assert result["content_type"] == "image/png"
        assert result["size_bytes"] == 1024
        assert result["alt_text"] == "Test image"
        assert "uploaded_at" in result

    def test_build_image_media_dict_no_alt_text(self) -> None:
        result = build_image_media_dict(
            gcs_path="org_1/questions/q_1_abc.png",
            content_type="image/png",
            size_bytes=1024,
        )
        assert result["alt_text"] is None

    def test_build_external_media_dict(self) -> None:
        media = ExternalMedia(
            type="video",
            provider="youtube",
            url="https://youtube.com/watch?v=abc",
            embed_url="https://youtube.com/embed/abc",
            thumbnail_url="https://img.youtube.com/vi/abc/hqdefault.jpg",
        )
        result = build_external_media_dict(media)
        assert result["type"] == "video"
        assert result["provider"] == "youtube"
        assert result["embed_url"] == "https://youtube.com/embed/abc"
