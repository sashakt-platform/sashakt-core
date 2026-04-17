from sqlmodel import Session, select

from app.models.organization_settings import (
    DEFAULT_ORGANIZATION_SETTINGS,
    OrganizationSettings,
    OrganizationSettingsPayload,
)


def get_by_org_id(
    *, session: Session, organization_id: int
) -> OrganizationSettings | None:
    return session.exec(
        select(OrganizationSettings).where(
            OrganizationSettings.organization_id == organization_id
        )
    ).first()


def get_payload(
    *, session: Session, organization_id: int
) -> OrganizationSettingsPayload | None:
    """Return the validated settings payload for an org, or None if no row exists."""
    row = get_by_org_id(session=session, organization_id=organization_id)
    if row is None:
        return None
    return OrganizationSettingsPayload.model_validate(row.settings)


def get_or_create(*, session: Session, organization_id: int) -> OrganizationSettings:
    """Fetch the settings row for an org, creating a defaults-backed row if missing."""
    existing = get_by_org_id(session=session, organization_id=organization_id)
    if existing is not None:
        return existing

    row = OrganizationSettings(
        organization_id=organization_id,
        settings=DEFAULT_ORGANIZATION_SETTINGS,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def upsert(
    *,
    session: Session,
    organization_id: int,
    payload: OrganizationSettingsPayload,
) -> OrganizationSettings:
    row = get_by_org_id(session=session, organization_id=organization_id)
    settings_dict = payload.model_dump(mode="json")
    if row is None:
        row = OrganizationSettings(
            organization_id=organization_id,
            settings=settings_dict,
        )
    else:
        row.settings = settings_dict
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
