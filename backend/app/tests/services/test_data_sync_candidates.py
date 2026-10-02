from sqlmodel import Session

from app.models.candidate import Candidate
from app.services.data_sync import DataSyncService
from app.tests.utils.organization import create_random_organization


def test_candidate_export_carries_external_identifier(db: Session) -> None:
    """The external (e.g. Avanti) user id must survive the export.

    candidates.identity only holds the anonymous QR uuid, so if this field is
    dropped there is no key left to join a Sashakt attempt back to the
    external system that launched it.
    """
    organization = create_random_organization(db)
    candidate = Candidate(
        organization_id=organization.id,
        external_identifier="avanti_user_4242",
        is_active=True,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    exported = DataSyncService()._serialize_candidate(candidate)

    assert exported["external_identifier"] == "avanti_user_4242"
