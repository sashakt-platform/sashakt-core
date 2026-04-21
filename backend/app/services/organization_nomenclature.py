from app.models.organization_settings import (
    NOMENCLATURE_DEFAULTS,
    OrganizationSettingsPayload,
)


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
