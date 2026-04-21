from sqlmodel import Session

from app.crud import organization_settings as crud_settings
from app.models.organization_settings import (
    NOMENCLATURE_DEFAULTS,
    OrganizationSettingsPayload,
)
from app.models.test import Test


def resolve_label(settings: OrganizationSettingsPayload, term: str) -> str:
    """Return the org's custom label for `term`, or the built-in default when
    mode is "default" or the value is empty.
    """
    nom = settings.platform_nomenclature
    if nom.mode == "custom":
        custom = getattr(nom.value, term, "")
        if custom:
            return str(custom)
    return NOMENCLATURE_DEFAULTS[term]


def resolve_all(settings: OrganizationSettingsPayload) -> dict[str, str]:
    """Return every tracked term mapped to its resolved label."""
    return {term: resolve_label(settings, term) for term in NOMENCLATURE_DEFAULTS}


def resolve_nomenclature_for_test(session: Session, test: Test) -> dict[str, str]:
    """Return the resolved nomenclature dict for a test's organization.

    Falls back to built-in defaults when the test has no org, or when no
    settings row exists (only possible in tests that bypass the org-create
    auto-init path).
    """
    if test.organization_id is None:
        return dict(NOMENCLATURE_DEFAULTS)
    settings_payload = crud_settings.get_payload(
        session=session, organization_id=test.organization_id
    )
    if settings_payload is None:
        return dict(NOMENCLATURE_DEFAULTS)
    return resolve_all(settings_payload)
