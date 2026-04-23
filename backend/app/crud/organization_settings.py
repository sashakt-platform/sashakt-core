import copy
from typing import Any

from sqlalchemy.exc import IntegrityError
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


def _insert_or_return_existing(
    *,
    session: Session,
    organization_id: int,
    settings_dict: dict[str, Any],
) -> OrganizationSettings:
    """Insert a fresh settings row; on race-loss, return the row that won.

    `organization_id` has a unique constraint, so a concurrent insert from
    another transaction raises IntegrityError. We rollback and re-read.
    """
    row = OrganizationSettings(
        organization_id=organization_id,
        settings=settings_dict,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = get_by_org_id(session=session, organization_id=organization_id)
        if existing is None:
            raise
        return existing
    session.refresh(row)
    return row


def get_or_create(*, session: Session, organization_id: int) -> OrganizationSettings:
    """Fetch the settings row for an org, creating a defaults-backed row if missing.

    Safe under concurrent callers: if two callers race the insert, the loser
    rolls back and returns the winning row instead of raising.
    """
    existing = get_by_org_id(session=session, organization_id=organization_id)
    if existing is not None:
        return existing
    return _insert_or_return_existing(
        session=session,
        organization_id=organization_id,
        settings_dict=copy.deepcopy(DEFAULT_ORGANIZATION_SETTINGS),
    )


def upsert(
    *,
    session: Session,
    organization_id: int,
    payload: OrganizationSettingsPayload,
) -> OrganizationSettings:
    row = get_by_org_id(session=session, organization_id=organization_id)
    settings_dict = payload.model_dump(mode="json")
    if row is None:
        # Insert path — race-safe.
        created = _insert_or_return_existing(
            session=session,
            organization_id=organization_id,
            settings_dict=settings_dict,
        )
        if created.settings == settings_dict:
            return created
        # A concurrent writer won the insert with different data. Fall through
        # to the update path so our caller's payload becomes the final state.
        row = created
    row.settings = settings_dict
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
