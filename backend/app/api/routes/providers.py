from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi_pagination import Page, paginate
from sqlmodel import select

from app.api.deps import (
    Pagination,
    SessionDep,
    permission_dependency,
)
from app.core.provider_config import provider_config_service
from app.models import Message
from app.models.provider import (
    OrganizationProvider,
    OrganizationProviderCreate,
    OrganizationProviderPublic,
    OrganizationProviderUpdate,
    Provider,
    ProviderCreate,
    ProviderPublic,
    ProviderSyncStatus,
    ProviderType,
    ProviderUpdate,
)
from app.services.data_sync import data_sync_service

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get(
    "/",
    response_model=Page[ProviderPublic],
    dependencies=[Depends(permission_dependency("read_provider"))],
)
def get_providers(
    session: SessionDep,
    params: Pagination = Depends(),
) -> Page[ProviderPublic]:
    """
    Retrieve providers.
    """
    statement = select(Provider).where(Provider.is_active)
    providers = session.exec(statement).all()
    return paginate(providers, params)  # type: ignore[no-any-return]


@router.post(
    "/",
    response_model=ProviderPublic,
    dependencies=[Depends(permission_dependency("create_provider"))],
)
def create_provider(
    *,
    session: SessionDep,
    provider_in: ProviderCreate,
) -> ProviderPublic:
    """
    Create new provider.
    """

    provider = Provider.model_validate(provider_in)
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return ProviderPublic.model_validate(provider)


@router.put(
    "/{provider_id}",
    response_model=ProviderPublic,
    dependencies=[Depends(permission_dependency("update_provider"))],
)
def update_provider(
    provider_id: int,
    *,
    session: SessionDep,
    provider_in: ProviderUpdate,
) -> ProviderPublic:
    """
    Update provider.
    """

    provider = session.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    update_dict = provider_in.model_dump(exclude_unset=True)
    provider.sqlmodel_update(update_dict)
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return ProviderPublic.model_validate(provider)


@router.delete(
    "/{provider_id}",
    response_model=Message,
    dependencies=[Depends(permission_dependency("delete_provider"))],
)
def delete_provider(
    provider_id: int,
    *,
    session: SessionDep,
) -> Message:
    """
    Delete provider.
    """

    provider = session.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider.is_active = False
    session.add(provider)
    session.commit()
    return Message(message="Provider deactivated successfully")


@router.get(
    "/organizations/{organization_id}/providers",
    response_model=list[OrganizationProviderPublic],
    dependencies=[Depends(permission_dependency("read_provider"))],
)
def get_organization_providers(
    organization_id: int,
    session: SessionDep,
) -> list[OrganizationProviderPublic]:
    """
    Retrieve organization providers.
    """

    statement = (
        select(OrganizationProvider)
        .join(Provider)
        .where(
            OrganizationProvider.organization_id == organization_id,
            Provider.is_active,
        )
    )
    org_providers = session.exec(statement).all()
    return [OrganizationProviderPublic.model_validate(op) for op in org_providers]


@router.post(
    "/organizations/{organization_id}/providers",
    response_model=OrganizationProviderPublic,
    dependencies=[Depends(permission_dependency("create_provider"))],
)
def create_organization_provider(
    organization_id: int,
    *,
    session: SessionDep,
    org_provider_in: OrganizationProviderCreate,
) -> OrganizationProviderPublic:
    """
    Create organization provider configuration.
    """

    provider = session.get(Provider, org_provider_in.provider_id)
    if not provider or not provider.is_active:
        raise HTTPException(status_code=404, detail="Provider not found or inactive")

    existing = session.exec(
        select(OrganizationProvider).where(
            OrganizationProvider.organization_id == organization_id,
            OrganizationProvider.provider_id == org_provider_in.provider_id,
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=400, detail="Provider already configured for this organization"
        )

    org_provider = OrganizationProvider(
        organization_id=organization_id,
        provider_id=org_provider_in.provider_id,
        is_enabled=org_provider_in.is_enabled,
    )

    if org_provider_in.config_json:
        try:
            config_data = org_provider_in.config_json.copy()

            # BigQuery-specific: Ensure dataset_id includes organization suffix for isolation
            if provider.provider_type == ProviderType.BIGQUERY:
                dataset_id = config_data.get("dataset_id", "sashakt_data")
                org_suffix = f"_{organization_id}"
                if not dataset_id.endswith(org_suffix):
                    config_data["dataset_id"] = f"{dataset_id}{org_suffix}"

            encrypted_config = provider_config_service.prepare_config_for_storage(
                provider.provider_type, config_data
            )
            org_provider.config_json = encrypted_config
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid configuration: {str(e)}"
            )

    session.add(org_provider)
    session.commit()
    session.refresh(org_provider)
    return OrganizationProviderPublic.model_validate(org_provider)


@router.put(
    "/organizations/{organization_id}/providers/{provider_id}",
    response_model=OrganizationProviderPublic,
    dependencies=[Depends(permission_dependency("update_provider"))],
)
def update_organization_provider(
    organization_id: int,
    provider_id: int,
    *,
    session: SessionDep,
    org_provider_in: OrganizationProviderUpdate,
) -> OrganizationProviderPublic:
    """
    Update organization provider configuration.
    """

    org_provider = session.exec(
        select(OrganizationProvider)
        .join(Provider)
        .where(
            OrganizationProvider.organization_id == organization_id,
            OrganizationProvider.provider_id == provider_id,
        )
    ).first()

    if not org_provider:
        raise HTTPException(status_code=404, detail="Organization provider not found")

    update_dict = org_provider_in.model_dump(exclude_unset=True)

    if "config_json" in update_dict and update_dict["config_json"]:
        try:
            config_data = update_dict["config_json"].copy()

            # BigQuery-specific: Ensure dataset_id includes organization suffix for isolation
            if org_provider.provider.provider_type == ProviderType.BIGQUERY:
                dataset_id = config_data.get("dataset_id", "sashakt_data")
                org_suffix = f"_{organization_id}"
                if not dataset_id.endswith(org_suffix):
                    config_data["dataset_id"] = f"{dataset_id}{org_suffix}"

            encrypted_config = provider_config_service.prepare_config_for_storage(
                org_provider.provider.provider_type, config_data
            )
            update_dict["config_json"] = encrypted_config
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid configuration: {str(e)}"
            )

    org_provider.sqlmodel_update(update_dict)
    session.add(org_provider)
    session.commit()
    session.refresh(org_provider)
    return OrganizationProviderPublic.model_validate(org_provider)


@router.delete(
    "/organizations/{organization_id}/providers/{provider_id}",
    response_model=Message,
    dependencies=[Depends(permission_dependency("delete_provider"))],
)
def delete_organization_provider(
    organization_id: int,
    provider_id: int,
    *,
    session: SessionDep,
) -> Message:
    """
    Delete organization provider configuration.
    """

    org_provider = session.exec(
        select(OrganizationProvider).where(
            OrganizationProvider.organization_id == organization_id,
            OrganizationProvider.provider_id == provider_id,
        )
    ).first()

    if not org_provider:
        raise HTTPException(status_code=404, detail="Organization provider not found")

    session.delete(org_provider)
    session.commit()
    return Message(message="Organization provider removed successfully")


@router.post(
    "/organizations/{organization_id}/providers/{provider_id}/test-connection",
    response_model=dict[str, bool],
    dependencies=[Depends(permission_dependency("read_provider"))],
)
def test_provider_connection(
    organization_id: int,
    provider_id: int,
) -> dict[str, bool]:
    """
    Test provider connection for organization.
    """

    success = data_sync_service.test_provider_connection(organization_id, provider_id)
    return {"success": success}


@router.post(
    "/organizations/{organization_id}/providers/{provider_id}/sync",
    response_model=dict[str, Any],
    dependencies=[Depends(permission_dependency("update_provider"))],
)
def trigger_provider_sync(
    organization_id: int,
    incremental: bool = True,
) -> dict[str, Any]:
    """
    Trigger data sync for organization provider.
    """

    try:
        results = data_sync_service.sync_organization_data(organization_id, incremental)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get(
    "/organizations/{organization_id}/providers/status",
    response_model=list[ProviderSyncStatus],
    dependencies=[Depends(permission_dependency("read_provider"))],
)
def get_provider_sync_status(
    organization_id: int,
    session: SessionDep,
) -> list[ProviderSyncStatus]:
    """
    Get sync status for organization providers.
    """

    statement = (
        select(OrganizationProvider, Provider)
        .join(Provider)
        .where(
            OrganizationProvider.organization_id == organization_id,
            Provider.is_active,
        )
    )

    results = session.exec(statement).all()
    status_list = []

    for org_provider, provider in results:
        sync_status = "never_synced"
        if org_provider.last_sync_timestamp:
            sync_status = "success"

        status_list.append(
            ProviderSyncStatus(
                provider_id=provider.id,
                provider_name=provider.name,
                provider_type=provider.provider_type,
                is_enabled=org_provider.is_enabled,
                last_sync_timestamp=org_provider.last_sync_timestamp,
                sync_status=sync_status,
            )
        )

    return status_list
