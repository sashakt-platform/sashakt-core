from app.core.roles import can_assign_role, get_role_hierarchy, get_valid_roles


class TestRoleHierarchy:
    """Test role hierarchy functions."""

    def test_get_role_hierarchy(self) -> None:
        """Test that role hierarchy returns expected structure."""
        hierarchy = get_role_hierarchy()

        assert isinstance(hierarchy, dict)
        assert "super_admin" in hierarchy
        assert "system_admin" in hierarchy
        assert "state_admin" in hierarchy

        # Super admin should have access to all roles
        assert set(hierarchy["super_admin"]) == {
            "super_admin",
            "system_admin",
            "state_admin",
            "test_admin",
            "candidate",
        }

        # System admin should have access to system_admin and below
        assert set(hierarchy["system_admin"]) == {
            "system_admin",
            "state_admin",
            "test_admin",
            "candidate",
        }

        # State admin should have access to state_admin and below
        assert set(hierarchy["state_admin"]) == {
            "state_admin",
            "test_admin",
            "candidate",
        }

    def test_get_valid_roles_super_admin(self) -> None:
        """Test get_valid_roles for super_admin."""
        valid_roles = get_valid_roles("super_admin")

        assert len(valid_roles) == 5
        assert set(valid_roles) == {
            "super_admin",
            "system_admin",
            "state_admin",
            "test_admin",
            "candidate",
        }

    def test_get_valid_roles_system_admin(self) -> None:
        """Test get_valid_roles for system_admin."""
        valid_roles = get_valid_roles("system_admin")

        assert len(valid_roles) == 4
        assert set(valid_roles) == {
            "system_admin",
            "state_admin",
            "test_admin",
            "candidate",
        }

    def test_get_valid_roles_state_admin(self) -> None:
        """Test get_valid_roles for state_admin."""
        valid_roles = get_valid_roles("state_admin")

        assert len(valid_roles) == 3
        assert set(valid_roles) == {"state_admin", "test_admin", "candidate"}

    def test_get_valid_roles_test_admin(self) -> None:
        """Test get_valid_roles for test_admin (should return empty)."""
        valid_roles = get_valid_roles("test_admin")

        assert valid_roles == []

    def test_get_valid_roles_candidate(self) -> None:
        """Test get_valid_roles for candidate (should return empty)."""
        valid_roles = get_valid_roles("candidate")

        assert valid_roles == []

    def test_get_valid_roles_invalid_role(self) -> None:
        """Test get_valid_roles for invalid role (should return empty)."""
        valid_roles = get_valid_roles("invalid_role")

        assert valid_roles == []

    def test_can_assign_role_super_admin(self) -> None:
        """Test can_assign_role for super_admin."""
        # Super admin can assign all roles
        assert can_assign_role("super_admin", "super_admin") is True
        assert can_assign_role("super_admin", "system_admin") is True
        assert can_assign_role("super_admin", "state_admin") is True
        assert can_assign_role("super_admin", "test_admin") is True
        assert can_assign_role("super_admin", "candidate") is True

    def test_can_assign_role_system_admin(self) -> None:
        """Test can_assign_role for system_admin."""
        # System admin cannot assign super_admin but can assign others
        assert can_assign_role("system_admin", "super_admin") is False
        assert can_assign_role("system_admin", "system_admin") is True
        assert can_assign_role("system_admin", "state_admin") is True
        assert can_assign_role("system_admin", "test_admin") is True
        assert can_assign_role("system_admin", "candidate") is True

    def test_can_assign_role_state_admin(self) -> None:
        """Test can_assign_role for state_admin."""
        # State admin cannot assign super_admin or system_admin
        assert can_assign_role("state_admin", "super_admin") is False
        assert can_assign_role("state_admin", "system_admin") is False
        assert can_assign_role("state_admin", "state_admin") is True
        assert can_assign_role("state_admin", "test_admin") is True
        assert can_assign_role("state_admin", "candidate") is True

    def test_can_assign_role_test_admin(self) -> None:
        """Test can_assign_role for test_admin."""
        # Test admin cannot assign any roles
        assert can_assign_role("test_admin", "super_admin") is False
        assert can_assign_role("test_admin", "system_admin") is False
        assert can_assign_role("test_admin", "state_admin") is False
        assert can_assign_role("test_admin", "test_admin") is False
        assert can_assign_role("test_admin", "candidate") is False

    def test_can_assign_role_candidate(self) -> None:
        """Test can_assign_role for candidate."""
        # Candidate cannot assign any roles
        assert can_assign_role("candidate", "super_admin") is False
        assert can_assign_role("candidate", "system_admin") is False
        assert can_assign_role("candidate", "state_admin") is False
        assert can_assign_role("candidate", "test_admin") is False
        assert can_assign_role("candidate", "candidate") is False

    def test_can_assign_role_invalid_current_role(self) -> None:
        """Test can_assign_role with invalid current role."""
        # Invalid current role cannot assign any roles
        assert can_assign_role("invalid_role", "super_admin") is False
        assert can_assign_role("invalid_role", "candidate") is False

    def test_can_assign_role_invalid_target_role(self) -> None:
        """Test can_assign_role with invalid target role."""
        # Valid current role cannot assign invalid target role
        assert can_assign_role("super_admin", "invalid_role") is False
        assert can_assign_role("state_admin", "invalid_role") is False
