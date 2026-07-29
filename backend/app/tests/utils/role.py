from sqlmodel import Session, select

from app.core.roles import init_org_roles, init_super_admin_role
from app.models import Role, RoleCreate
from app.tests.utils.organization import create_random_organization
from app.tests.utils.utils import random_lower_string


def get_org_role(session: Session, organization_id: int | None, role_name: str) -> Role:
    """
    Return `role_name`'s copy scoped to `organization_id`, seeding that org's
    default roles first if they don't exist yet.
    """
    assert organization_id is not None
    role = session.exec(
        select(Role).where(
            Role.name == role_name, Role.organization_id == organization_id
        )
    ).first()
    if role is None:
        if role_name == "super_admin":
            init_super_admin_role(session, organization_id)
        else:
            init_org_roles(session, organization_id)
        role = session.exec(
            select(Role).where(
                Role.name == role_name, Role.organization_id == organization_id
            )
        ).first()
    if role is None:
        role = Role(name=role_name, label=role_name, organization_id=organization_id)
        session.add(role)
        session.commit()
        session.refresh(role)
    return role


def create_random_role(session: Session, organization_id: int | None = None) -> Role:
    if organization_id is None:
        organization_id = create_random_organization(session=session).id
        assert organization_id is not None

    name = random_lower_string()
    description = random_lower_string()
    label = random_lower_string()
    role_in = RoleCreate(name=name, description=description, label=label)

    db_role = Role(
        **role_in.model_dump(exclude={"permissions"}),
        organization_id=organization_id,
    )
    session.add(db_role)
    session.commit()
    session.refresh(db_role)

    return db_role
