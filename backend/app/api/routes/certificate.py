from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, SessionDep, permission_dependency
from app.models.certificate import Certificate, CertificateCreate, CertificatePublic

router = APIRouter(prefix="/certificate", tags=["Certificate"])


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
