from sqlmodel import Session, select

from app.core.roles import can_assign_role, get_valid_roles, is_location_scoped_role
from app.models import Role, RoleLocationLevel
from app.tests.utils.role import create_random_role


class TestGetValidRoles:
    """get_valid_roles reads Role.allowed_roles directly, no hardcoded hierarchy."""

    def test_super_admin(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "super_admin")).first()
        assert role is not None
        assert set(get_valid_roles(role)) == {"system_admin"}

    def test_system_admin(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "system_admin")).first()
        assert role is not None
        assert set(get_valid_roles(role)) == {
            "system_admin",
            "state_admin",
            "test_admin",
        }

    def test_state_admin(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "state_admin")).first()
        assert role is not None
        assert set(get_valid_roles(role)) == {"state_admin", "test_admin"}

    def test_test_admin(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "test_admin")).first()
        assert role is not None
        assert get_valid_roles(role) == ["test_admin"]

    def test_candidate(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "candidate")).first()
        assert role is not None
        assert get_valid_roles(role) == []

    def test_custom_role_with_no_allowed_roles(self, db: Session) -> None:
        custom_role = create_random_role(db)
        assert get_valid_roles(custom_role) == []

    def test_custom_role_with_custom_allowed_roles(self, db: Session) -> None:
        custom_role = create_random_role(db)
        custom_role.allowed_roles = ["test_admin"]
        db.add(custom_role)
        db.commit()
        db.refresh(custom_role)
        assert get_valid_roles(custom_role) == ["test_admin"]


class TestCanAssignRole:
    """can_assign_role checks Role.allowed_roles directly, no hardcoded hierarchy."""

    def test_super_admin(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "super_admin")).first()
        assert role is not None
        assert can_assign_role(role, "super_admin") is False
        assert can_assign_role(role, "system_admin") is True
        assert can_assign_role(role, "state_admin") is False
        assert can_assign_role(role, "test_admin") is False
        assert can_assign_role(role, "candidate") is False

    def test_system_admin(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "system_admin")).first()
        assert role is not None
        assert can_assign_role(role, "super_admin") is False
        assert can_assign_role(role, "system_admin") is True
        assert can_assign_role(role, "state_admin") is True
        assert can_assign_role(role, "test_admin") is True
        assert can_assign_role(role, "candidate") is False

    def test_state_admin(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "state_admin")).first()
        assert role is not None
        assert can_assign_role(role, "super_admin") is False
        assert can_assign_role(role, "system_admin") is False
        assert can_assign_role(role, "state_admin") is True
        assert can_assign_role(role, "test_admin") is True
        assert can_assign_role(role, "candidate") is False

    def test_test_admin(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "test_admin")).first()
        assert role is not None
        assert can_assign_role(role, "super_admin") is False
        assert can_assign_role(role, "system_admin") is False
        assert can_assign_role(role, "state_admin") is False
        assert can_assign_role(role, "test_admin") is True
        assert can_assign_role(role, "candidate") is False

    def test_candidate(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "candidate")).first()
        assert role is not None
        assert can_assign_role(role, "super_admin") is False
        assert can_assign_role(role, "system_admin") is False
        assert can_assign_role(role, "state_admin") is False
        assert can_assign_role(role, "test_admin") is False
        assert can_assign_role(role, "candidate") is False

    def test_custom_role_respects_custom_allowed_roles(self, db: Session) -> None:
        custom_role = create_random_role(db)
        custom_role.allowed_roles = ["test_admin"]
        db.add(custom_role)
        db.commit()
        db.refresh(custom_role)
        assert can_assign_role(custom_role, "test_admin") is True
        assert can_assign_role(custom_role, "super_admin") is False


class TestIsLocationScopedRole:
    """is_location_scoped_role must key off role.location_scope alone, never
    the role name, so any role granted a scope behaves as scoped downstream."""

    def test_custom_role_with_state_scope_is_scoped(self) -> None:
        custom_role = Role(
            name="custom_regional_lead",
            label="Custom Regional Lead",
            location_scope=RoleLocationLevel.STATE,
        )
        assert is_location_scoped_role(custom_role) is True

    def test_custom_role_with_district_scope_is_scoped(self) -> None:
        custom_role = Role(
            name="custom_field_coordinator",
            label="Custom Field Coordinator",
            location_scope=RoleLocationLevel.DISTRICT,
        )
        assert is_location_scoped_role(custom_role) is True

    def test_custom_role_without_scope_is_not_scoped(self) -> None:
        custom_role = Role(name="custom_reporter", label="Custom Reporter")
        assert is_location_scoped_role(custom_role) is False


class TestRoleSeedData:
    """Seeded roles must carry allowed_roles/is_restricted per init_roles(),
    while roles created afterwards (custom roles) get non-restricted defaults."""

    def test_super_admin_allowed_roles(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "super_admin")).first()
        assert role is not None
        assert set(role.allowed_roles) == {"system_admin"}

    def test_system_admin_allowed_roles(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "system_admin")).first()
        assert role is not None
        assert set(role.allowed_roles) == {"system_admin", "state_admin", "test_admin"}

    def test_state_admin_allowed_roles(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "state_admin")).first()
        assert role is not None
        assert set(role.allowed_roles) == {"state_admin", "test_admin"}

    def test_test_admin_allowed_roles(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "test_admin")).first()
        assert role is not None
        assert set(role.allowed_roles) == {"test_admin"}

    def test_candidate_allowed_roles(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "candidate")).first()
        assert role is not None
        assert set(role.allowed_roles) == set()

    def test_super_admin_is_restricted(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "super_admin")).first()
        assert role is not None
        assert role.is_restricted is True

    def test_system_admin_is_restricted(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "system_admin")).first()
        assert role is not None
        assert role.is_restricted is True

    def test_state_admin_is_restricted(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "state_admin")).first()
        assert role is not None
        assert role.is_restricted is True

    def test_test_admin_is_restricted(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "test_admin")).first()
        assert role is not None
        assert role.is_restricted is True

    def test_candidate_is_restricted(self, db: Session) -> None:
        role = db.exec(select(Role).where(Role.name == "candidate")).first()
        assert role is not None
        assert role.is_restricted is True

    def test_custom_role_defaults_to_unrestricted_with_no_allowed_roles(
        self, db: Session
    ) -> None:
        custom_role = create_random_role(db)
        assert custom_role.is_restricted is False
        assert custom_role.allowed_roles == []
