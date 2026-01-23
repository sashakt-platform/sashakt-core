from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlmodel import func, select

from app.api.deps import CurrentUser, Pagination, SessionDep, permission_dependency
from app.models import Message
from app.models.certificate import (
    Certificate,
    CertificateCreate,
    CertificatePublic,
    CertificateUpdate,
)

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
    certificate = Certificate(
        **certificate_create.model_dump(),
        created_by_id=current_user.id,
    )
    session.add(certificate)
    session.commit()
    session.refresh(certificate)
    return certificate


@router.get("/", response_model=Page[CertificatePublic])
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
        query = query.where(
            func.trim(func.lower(Certificate.name)).like(f"%{name.strip().lower()}%")
        )

    certificates: Page[CertificatePublic] = paginate(
        session,
        query,  # type: ignore[arg-type]
        params,
        transformer=lambda items: transform_certificates_to_public(items),
    )

    return certificates


@router.get("/{certificate_id}", response_model=CertificatePublic)
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
@router.put("/{certificate_id}", response_model=CertificatePublic)
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
    certificate.sqlmodel_update(certificate_data)

    session.add(certificate)
    session.commit()
    session.refresh(certificate)

    return certificate


# Delete Certificate
@router.delete("/{certificate_id}")
def delete_certificate(
    certificate_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    certificate = session.get(Certificate, certificate_id)

    if not certificate or certificate.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Certificate not found")

    session.delete(certificate)
    session.commit()

    return Message(message="Certificate deleted successfully")
