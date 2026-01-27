from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlmodel import func, select

from app.api.deps import CurrentUser, Pagination, SessionDep, permission_dependency
from app.core.provider_config import provider_config_service
from app.models import Message
from app.models.candidate import CandidateTest
from app.models.certificate import (
    Certificate,
    CertificateCreate,
    CertificatePublic,
    CertificateUpdate,
)
from app.models.provider import OrganizationProvider, Provider, ProviderType
from app.models.test import Test
from app.services.google_slides import GoogleSlidesService

router = APIRouter(prefix="/certificate", tags=["Certificate"])


def transform_certificates_to_public(
    items: list[Certificate] | Any,
) -> list[CertificatePublic]:
    result: list[CertificatePublic] = []
    certificate_list: list[Certificate] = (
        list(items) if not isinstance(items, list) else items
    )

    for certificate in certificate_list:
        result.append(CertificatePublic(**certificate.model_dump()))
    return result


@router.post(
    "/",
    response_model=CertificatePublic,
    dependencies=[Depends(permission_dependency("create_certificate"))],
)
def create_certificate(
    certificate_create: CertificateCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Certificate:
    # organization_id should be set to the current user's organization
    certificate = Certificate(
        **certificate_create.model_dump(exclude={"organization_id"}),
        created_by_id=current_user.id,
        organization_id=current_user.organization_id,
    )
    session.add(certificate)
    session.commit()
    session.refresh(certificate)
    return certificate


@router.get(
    "/",
    response_model=Page[CertificatePublic],
    dependencies=[Depends(permission_dependency("read_certificate"))],
)
def get_certificates(
    session: SessionDep,
    current_user: CurrentUser,
    params: Pagination = Depends(),
    name: str | None = None,
) -> Page[CertificatePublic]:
    query = select(Certificate).where(
        Certificate.organization_id == current_user.organization_id,
    )

    if name:
        # escape LIKE pattern special characters to prevent injection
        #  TODO: may be able to use built-in escaping in SQLModel/SQLAlchemy in the future
        safe_name = (
            name.strip()
            .lower()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        query = query.where(
            func.trim(func.lower(Certificate.name)).like(f"%{safe_name}%", escape="\\")
        )

    certificates: Page[CertificatePublic] = paginate(
        session,
        query,  # type: ignore[arg-type]
        params,
        transformer=lambda items: transform_certificates_to_public(items),
    )

    return certificates


@router.get(
    "/{certificate_id}",
    response_model=CertificatePublic,
    dependencies=[Depends(permission_dependency("read_certificate"))],
)
def get_certificate_by_id(
    certificate_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> Certificate:
    certificate = session.get(Certificate, certificate_id)

    if not certificate or certificate.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Certificate not found")

    return certificate


# Update Certificate
@router.put(
    "/{certificate_id}",
    response_model=CertificatePublic,
    dependencies=[Depends(permission_dependency("update_certificate"))],
)
def update_certificate(
    certificate_id: int,
    updated_data: CertificateUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Certificate:
    certificate = session.get(Certificate, certificate_id)

    if not certificate or certificate.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Certificate not found")

    certificate_data = updated_data.model_dump(exclude_unset=True)

    # prevent cross-tenant reassignment by removing organization_id from update
    certificate_data.pop("organization_id", None)
    certificate.sqlmodel_update(certificate_data)

    session.add(certificate)
    session.commit()
    session.refresh(certificate)

    return certificate


# Delete Certificate
@router.delete(
    "/{certificate_id}",
    dependencies=[Depends(permission_dependency("delete_certificate"))],
)
def delete_certificate(
    certificate_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    certificate = session.get(Certificate, certificate_id)

    if not certificate or certificate.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # check for associated tests before deleting
    related_tests = session.exec(
        select(Test).where(Test.certificate_id == certificate_id)
    ).first()

    if related_tests:
        raise HTTPException(
            status_code=400,
            detail="Certificate has associated tests and cannot be deleted",
        )

    session.delete(certificate)
    session.commit()

    return Message(message="Certificate deleted successfully")


@router.get("/download/{token}")
def download_certificate(
    token: str,
    session: SessionDep,
) -> Response:
    """
    Download certificate PDF using a token.
    No authentication required - token is the authentication.
    """
    # Find candidate_test by token in certificate_data
    candidate_test = session.exec(
        select(CandidateTest).where(
            CandidateTest.certificate_data["token"].as_string() == token  # type: ignore[index]
        )
    ).first()

    if not candidate_test or not candidate_test.certificate_data:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # Get certificate data from snapshot
    cert_data = candidate_test.certificate_data

    # Get test and certificate
    test = session.get(Test, candidate_test.test_id)
    if not test or not test.certificate_id:
        raise HTTPException(status_code=404, detail="No certificate for this test")

    certificate = session.get(Certificate, test.certificate_id)
    if not certificate or not certificate.is_active:
        raise HTTPException(status_code=404, detail="Certificate not available")

    # Get Google Slides provider for the organization
    org_provider = session.exec(
        select(OrganizationProvider)
        .join(Provider)
        .where(
            OrganizationProvider.organization_id == test.organization_id,
            Provider.provider_type == ProviderType.GOOGLE_SLIDES,
            OrganizationProvider.is_enabled,
            Provider.is_active,
        )
    ).first()

    if not org_provider or not org_provider.config_json:
        raise HTTPException(
            status_code=503,
            detail="Certificate generation service not configured",
        )

    # Decrypt config and create service
    try:
        config = provider_config_service.get_config_for_use(org_provider.config_json)
        slides_service = GoogleSlidesService(config)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Certificate generation service unavailable",
        )

    # Use data from snapshot
    candidate_name = cert_data.get("candidate_name", "Candidate")
    test_name = cert_data.get("test_name", test.name)
    score_str = cert_data.get("score", "N/A")
    completion_date = cert_data.get("completion_date", "N/A")

    # Generate certificate PDF
    try:
        pdf_bytes = slides_service.generate_certificate_pdf(
            template_url=certificate.url,
            candidate_name=candidate_name,
            test_name=test_name,
            completion_date=completion_date,
            score=score_str,
            certificate_title=f"Certificate - {test_name} - {candidate_name}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Failed to generate certificate",
        )

    # Return PDF as downloadable file
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="certificate_{candidate_test.id}.pdf"'
        },
    )
