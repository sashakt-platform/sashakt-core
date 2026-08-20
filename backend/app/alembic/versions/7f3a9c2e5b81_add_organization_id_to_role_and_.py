"""add organization_id to role and backfill existing data

Revision ID: 7f3a9c2e5b81
Revises: d8640b20c143
Create Date: 2026-08-16 00:00:00.000000

"""
from alembic import op
from app.core.config import settings
from app.models.organization import Organization
from app.models.role import Role, RolePermission
from app.models.user import User
import sqlalchemy as sa
from sqlmodel import Session, select


# revision identifiers, used by Alembic.
revision = '7f3a9c2e5b81'
down_revision = 'd8640b20c143'
branch_labels = None
depends_on = None


# Expand -> backfill -> contract migration, all in one revision.
# `organization_id` is added nullable so existing rows can be backfilled,
# then tightened to NOT NULL with a (organization_id, name) uniqueness rule
# once every row has a value.
FK_NAME = "role_organization_id_fkey"
UQ_NAME = "role_organization_id_name_key"

ORG_SCOPED_ROLE_NAMES = ("system_admin", "state_admin", "test_admin", "candidate")


def upgrade():
    op.add_column("role", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        FK_NAME,
        "role",
        "organization",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    bind = op.get_bind()
    session = Session(bind=bind)
    _backfill(session)
    session.commit()

    op.alter_column(
        "role", "organization_id", existing_type=sa.INTEGER(), nullable=False
    )
    op.create_unique_constraint(UQ_NAME, "role", ["organization_id", "name"])


def downgrade():
    op.drop_constraint(UQ_NAME, "role", type_="unique")
    op.alter_column(
        "role", "organization_id", existing_type=sa.INTEGER(), nullable=True
    )

    bind = op.get_bind()
    session = Session(bind=bind)
    _revert_backfill(session)
    session.commit()

    op.drop_constraint(FK_NAME, "role", type_="foreignkey")
    op.drop_column("role", "organization_id")


def _backfill(session: Session) -> None:
    """
    Move every role from "one shared row for the whole system" to "one row
    per organization". Runs once against a database that predates per-org
    roles; a no-op on a fresh install where no roles exist yet.
    """
    # super_admin is never cloned — there is exactly one row, ever, and it
    # simply gets pointed at the T4D organization directly.
    super_admin_role = session.exec(
        select(Role).where(Role.name == "super_admin", Role.organization_id.is_(None))
    ).first()
    if super_admin_role is not None:
        t4d_user = session.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).first()
        if t4d_user is None:
            raise RuntimeError(
                "Cannot backfill role.organization_id: no user found for "
                f"settings.FIRST_SUPERUSER ({settings.FIRST_SUPERUSER!r}). "
                "The T4D organization cannot be resolved."
            )
        super_admin_role.organization_id = t4d_user.organization_id
        session.add(super_admin_role)
        session.flush()

    organizations = session.exec(select(Organization)).all()

    for role_name in ORG_SCOPED_ROLE_NAMES:
        old_role = session.exec(
            select(Role).where(
                Role.name == role_name, Role.organization_id.is_(None)
            )
        ).first()
        if old_role is None:
            continue

        old_role_permissions = session.exec(
            select(RolePermission).where(RolePermission.role_id == old_role.id)
        ).all()

        new_role_id_by_org_id: dict[int, int] = {}
        for org in organizations:
            new_role = Role(
                name=old_role.name,
                label=old_role.label,
                description=old_role.description,
                is_active=old_role.is_active,
                is_restricted=old_role.is_restricted,
                location_scope=old_role.location_scope,
                allowed_roles=old_role.allowed_roles,
                organization_id=org.id,
            )
            session.add(new_role)
            session.flush()
            for role_permission in old_role_permissions:
                session.add(
                    RolePermission(
                        role_id=new_role.id,
                        permission_id=role_permission.permission_id,
                    )
                )
            new_role_id_by_org_id[org.id] = new_role.id
        session.flush()

        affected_users = session.exec(
            select(User).where(User.role_id == old_role.id)
        ).all()
        for user in affected_users:
            new_role_id = new_role_id_by_org_id.get(user.organization_id)
            if new_role_id is not None:
                user.role_id = new_role_id
                session.add(user)
        session.flush()

        session.delete(old_role)
        session.flush()

    _backfill_remaining_custom_roles(session)


def _backfill_remaining_custom_roles(session: Session) -> None:
    """
    Handle any role that existed before this migration but isn't one of the
    five well-known names (super_admin + the four customizable roles) — e.g.
    a custom role an admin created via `POST /roles/` back when role names
    weren't organization-scoped.

    Unlike the four customizable roles, a custom role is only cloned into the
    organizations that actually have a user holding it — not into every
    organization — since it was never part of the standard seed set. A role
    with no users at all is dead weight (a role can no longer exist without
    an organization) and is simply dropped.
    """
    remaining_roles = session.exec(
        select(Role).where(Role.organization_id.is_(None))
    ).all()

    for old_role in remaining_roles:
        affected_users = session.exec(
            select(User).where(User.role_id == old_role.id)
        ).all()
        org_ids = sorted({user.organization_id for user in affected_users})

        if not org_ids:
            session.delete(old_role)
            session.flush()
            continue

        old_role_permissions = session.exec(
            select(RolePermission).where(RolePermission.role_id == old_role.id)
        ).all()

        new_role_id_by_org_id: dict[int, int] = {}
        for org_id in org_ids:
            new_role = Role(
                name=old_role.name,
                label=old_role.label,
                description=old_role.description,
                is_active=old_role.is_active,
                is_restricted=old_role.is_restricted,
                location_scope=old_role.location_scope,
                allowed_roles=old_role.allowed_roles,
                organization_id=org_id,
            )
            session.add(new_role)
            session.flush()
            for role_permission in old_role_permissions:
                session.add(
                    RolePermission(
                        role_id=new_role.id,
                        permission_id=role_permission.permission_id,
                    )
                )
            new_role_id_by_org_id[org_id] = new_role.id
        session.flush()

        for user in affected_users:
            user.role_id = new_role_id_by_org_id[user.organization_id]
            session.add(user)
        session.flush()

        session.delete(old_role)
        session.flush()


def _revert_backfill(session: Session) -> None:
    """
    Reverse `_backfill`: merge each role name's per-organization copies back
    into a single shared row, re-pointing every user back to it.
    """
    for role_name in ORG_SCOPED_ROLE_NAMES:
        org_scoped_roles = session.exec(
            select(Role).where(Role.name == role_name)
        ).all()
        if not org_scoped_roles:
            continue

        canonical_role = org_scoped_roles[0]
        canonical_permission_ids = {
            role_permission.permission_id
            for role_permission in session.exec(
                select(RolePermission).where(
                    RolePermission.role_id == canonical_role.id
                )
            ).all()
        }

        for role in org_scoped_roles[1:]:
            role_permissions = session.exec(
                select(RolePermission).where(RolePermission.role_id == role.id)
            ).all()
            for role_permission in role_permissions:
                if role_permission.permission_id not in canonical_permission_ids:
                    session.add(
                        RolePermission(
                            role_id=canonical_role.id,
                            permission_id=role_permission.permission_id,
                        )
                    )
                    canonical_permission_ids.add(role_permission.permission_id)

            affected_users = session.exec(
                select(User).where(User.role_id == role.id)
            ).all()
            for user in affected_users:
                user.role_id = canonical_role.id
                session.add(user)
            session.flush()


            session.delete(role)
        session.flush()

    canonical_super_admin = session.exec(
        select(Role).where(Role.name == "super_admin")
    ).first()
    if canonical_super_admin is not None:
        canonical_super_admin.organization_id = None
        session.add(canonical_super_admin)
        session.flush()
