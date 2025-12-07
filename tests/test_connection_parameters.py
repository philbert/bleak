"""Tests for BLE connection parameter tuning API."""

import pytest

from bleak.args.connection import (
    ConnectionParameters,
    ConnectionPolicy,
    get_policy_defaults,
)


class TestConnectionPolicy:
    """Tests for ConnectionPolicy enum."""

    def test_policy_values(self):
        """Test that all expected policy values exist."""
        assert ConnectionPolicy.LOW_LATENCY.value == "low_latency"
        assert ConnectionPolicy.BALANCED.value == "balanced"
        assert ConnectionPolicy.POWER_SAVE.value == "power_save"


class TestConnectionParameters:
    """Tests for ConnectionParameters dataclass."""

    def test_default_construction(self):
        """Test creating ConnectionParameters with no args."""
        params = ConnectionParameters()
        assert params.min_interval_ms is None
        assert params.max_interval_ms is None
        assert params.latency is None
        assert params.supervision_timeout_ms is None
        assert params.policy is None
        assert params.preferred_phys is None
        assert params.preferred_mtu is None

    def test_explicit_numeric_params(self):
        """Test creating ConnectionParameters with explicit numeric values."""
        params = ConnectionParameters(
            min_interval_ms=100,
            max_interval_ms=200,
            latency=5,
            supervision_timeout_ms=5000,
        )
        assert params.min_interval_ms == 100
        assert params.max_interval_ms == 200
        assert params.latency == 5
        assert params.supervision_timeout_ms == 5000

    def test_policy_only(self):
        """Test creating ConnectionParameters with just a policy."""
        params = ConnectionParameters(policy=ConnectionPolicy.POWER_SAVE)
        assert params.policy == ConnectionPolicy.POWER_SAVE
        # Numeric values should still be None when not explicitly set
        assert params.min_interval_ms is None
        assert params.max_interval_ms is None

    def test_policy_with_partial_numeric(self):
        """Test policy with some numeric overrides."""
        params = ConnectionParameters(
            policy=ConnectionPolicy.BALANCED,
            min_interval_ms=75,  # Override default
        )
        assert params.policy == ConnectionPolicy.BALANCED
        assert params.min_interval_ms == 75

    def test_optional_fields(self):
        """Test optional PHY and MTU fields."""
        params = ConnectionParameters(
            preferred_phys=["1m", "2m"],
            preferred_mtu=512,
        )
        assert params.preferred_phys == ["1m", "2m"]
        assert params.preferred_mtu == 512

    def test_validation_min_max_order(self):
        """Test that min_interval must be <= max_interval."""
        with pytest.raises(
            ValueError, match="min_interval_ms.*must be <=.*max_interval_ms"
        ):
            ConnectionParameters(
                min_interval_ms=200,
                max_interval_ms=100,
            )

    def test_validation_negative_min_interval(self):
        """Test that negative min_interval is rejected."""
        with pytest.raises(ValueError, match="min_interval_ms must be >= 0"):
            ConnectionParameters(min_interval_ms=-10)

    def test_validation_negative_max_interval(self):
        """Test that negative max_interval is rejected."""
        with pytest.raises(ValueError, match="max_interval_ms must be >= 0"):
            ConnectionParameters(max_interval_ms=-10)

    def test_validation_negative_latency(self):
        """Test that negative latency is rejected."""
        with pytest.raises(ValueError, match="latency must be >= 0"):
            ConnectionParameters(latency=-1)

    def test_validation_negative_timeout(self):
        """Test that negative supervision_timeout is rejected."""
        with pytest.raises(ValueError, match="supervision_timeout_ms must be >= 0"):
            ConnectionParameters(supervision_timeout_ms=-100)

    def test_valid_equal_min_max(self):
        """Test that min_interval == max_interval is valid."""
        params = ConnectionParameters(
            min_interval_ms=100,
            max_interval_ms=100,
        )
        assert params.min_interval_ms == 100
        assert params.max_interval_ms == 100


class TestPolicyDefaults:
    """Tests for get_policy_defaults function."""

    def test_low_latency_defaults(self):
        """Test LOW_LATENCY policy defaults."""
        params = get_policy_defaults(ConnectionPolicy.LOW_LATENCY)
        assert params.policy == ConnectionPolicy.LOW_LATENCY
        assert params.min_interval_ms is not None
        assert params.max_interval_ms is not None
        assert params.latency is not None
        assert params.supervision_timeout_ms is not None
        # Low latency should have short intervals
        assert params.min_interval_ms < 50
        assert params.max_interval_ms < 100
        # Low latency should have minimal slave latency
        assert params.latency == 0

    def test_balanced_defaults(self):
        """Test BALANCED policy defaults."""
        params = get_policy_defaults(ConnectionPolicy.BALANCED)
        assert params.policy == ConnectionPolicy.BALANCED
        assert params.min_interval_ms is not None
        assert params.max_interval_ms is not None
        assert params.latency is not None
        assert params.supervision_timeout_ms is not None
        # Balanced should have moderate values
        assert 30 < params.min_interval_ms < 200
        assert 50 < params.max_interval_ms < 300

    def test_power_save_defaults(self):
        """Test POWER_SAVE policy defaults."""
        params = get_policy_defaults(ConnectionPolicy.POWER_SAVE)
        assert params.policy == ConnectionPolicy.POWER_SAVE
        assert params.min_interval_ms is not None
        assert params.max_interval_ms is not None
        assert params.latency is not None
        assert params.supervision_timeout_ms is not None
        # Power save should have long intervals
        assert params.min_interval_ms >= 100
        assert params.max_interval_ms >= 500
        # Power save should have higher slave latency
        assert params.latency > 0

    def test_policy_defaults_validation(self):
        """Test that policy defaults pass validation."""
        for policy in [
            ConnectionPolicy.LOW_LATENCY,
            ConnectionPolicy.BALANCED,
            ConnectionPolicy.POWER_SAVE,
        ]:
            params = get_policy_defaults(policy)
            # Should not raise
            assert params.min_interval_ms <= params.max_interval_ms
            assert params.min_interval_ms >= 0
            assert params.latency >= 0
            assert params.supervision_timeout_ms >= 0

    def test_unknown_policy_raises(self):
        """Test that unknown policy raises ValueError."""
        # Create a mock invalid policy value
        with pytest.raises(ValueError, match="Unknown policy"):
            # This is a bit hacky since Enum normally prevents invalid values
            get_policy_defaults("invalid_policy")  # type: ignore
