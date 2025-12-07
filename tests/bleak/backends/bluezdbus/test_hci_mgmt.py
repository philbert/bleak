"""Tests for HCI Management Interface connection parameter control."""

from bleak.backends.bluezdbus.hci_mgmt import (
    _bdaddr_to_bytes,
    connection_params_to_ble_units,
)


class TestBdaddrToBytes:
    """Tests for Bluetooth address conversion."""

    def test_public_address_conversion(self):
        """Test converting a public Bluetooth address to bytes."""
        addr_bytes, addr_type = _bdaddr_to_bytes("AA:BB:CC:DD:EE:FF", "public")

        # Address should be reversed (little-endian)
        assert addr_bytes == bytes([0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA])
        # Public address type is 1
        assert addr_type == 1

    def test_random_address_conversion(self):
        """Test converting a random Bluetooth address to bytes."""
        addr_bytes, addr_type = _bdaddr_to_bytes("11:22:33:44:55:66", "random")

        # Address should be reversed
        assert addr_bytes == bytes([0x66, 0x55, 0x44, 0x33, 0x22, 0x11])
        # Random address type is 2
        assert addr_type == 2

    def test_lowercase_address(self):
        """Test that lowercase addresses are handled correctly."""
        addr_bytes, addr_type = _bdaddr_to_bytes("aa:bb:cc:dd:ee:ff", "public")
        assert addr_bytes == bytes([0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA])


class TestConnectionParamsToUnits:
    """Tests for connection parameter conversion to BLE spec units."""

    def test_basic_conversion(self):
        """Test basic parameter conversion."""
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=100,
            max_interval_ms=200,
            latency=5,
            supervision_timeout_ms=5000,
        )

        # 100ms / 1.25ms = 80 units
        assert min_int == 80
        # 200ms / 1.25ms = 160 units
        assert max_int == 160
        # Latency is already in correct units
        assert lat == 5
        # 5000ms / 10ms = 500 units
        assert timeout == 500

    def test_minimum_clamping(self):
        """Test that values are clamped to BLE spec minimums."""
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=1,  # Too small, should clamp to 6 units (7.5ms)
            max_interval_ms=5,  # Too small
            latency=0,
            supervision_timeout_ms=50,  # Too small, should clamp to 10 units (100ms)
        )

        assert min_int == 6  # Minimum is 6 units (7.5ms)
        assert max_int == 6  # Also clamped
        assert lat == 0
        assert timeout == 10  # Minimum is 10 units (100ms)

    def test_maximum_clamping(self):
        """Test that values are clamped to BLE spec maximums."""
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=5000,  # Too large, should clamp to 3200 units (4000ms)
            max_interval_ms=10000,  # Too large
            latency=1000,  # Too large, should clamp to 499
            supervision_timeout_ms=50000,  # Too large, should clamp to 3200 units (32000ms)
        )

        assert min_int == 3200  # Maximum is 3200 units (4000ms)
        assert max_int == 3200
        assert lat == 499  # Maximum is 499
        assert timeout == 3200  # Maximum is 3200 units (32000ms)

    def test_min_max_swap(self):
        """Test that min/max are swapped if min > max."""
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=200,
            max_interval_ms=100,  # Smaller than min
            latency=0,
            supervision_timeout_ms=1000,
        )

        # Should be swapped
        assert min_int == 80  # 100ms
        assert max_int == 160  # 200ms

    def test_none_values_use_defaults(self):
        """Test that None values result in sensible defaults."""
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=None,
            max_interval_ms=None,
            latency=None,
            supervision_timeout_ms=None,
        )

        # Defaults should be valid BLE values
        assert 6 <= min_int <= 3200
        assert 6 <= max_int <= 3200
        assert 0 <= lat <= 499
        assert 10 <= timeout <= 3200

    def test_partial_none_values(self):
        """Test mixing None and explicit values."""
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=50,
            max_interval_ms=None,  # Will use default
            latency=10,
            supervision_timeout_ms=None,  # Will use default
        )

        # Explicit values should be converted
        assert min_int == 40  # 50ms / 1.25ms
        assert lat == 10

        # Defaults should still be valid
        assert 6 <= max_int <= 3200
        assert 10 <= timeout <= 3200

    def test_supervision_timeout_constraint(self):
        """Test that supervision timeout satisfies the BLE spec constraint.

        Timeout must be > (1 + latency) * max_interval * 2
        """
        # With moderate latency and interval, timeout should be adjusted
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=100,
            max_interval_ms=200,  # 160 units
            latency=10,
            supervision_timeout_ms=1000,  # Might be too short
        )

        assert max_int == 160  # 200ms / 1.25ms
        assert lat == 10

        # Calculate minimum required timeout
        # (1 + 10) * 160 * 1.25ms * 2 = 4400ms = 440 units
        # So timeout should be at least 440 units
        min_required_timeout = int((1 + lat) * max_int * 1.25 / 10 * 2) + 1
        assert timeout >= min_required_timeout

    def test_supervision_timeout_constraint_exceeds_max(self):
        """Test that supervision timeout is clamped when constraint exceeds spec max.

        When the required timeout based on latency/interval would exceed the
        BLE spec maximum (3200 units = 32000ms), it should be clamped.
        """
        # With very high latency and long interval, required timeout exceeds spec max
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=500,
            max_interval_ms=1000,  # 800 units
            latency=20,
            supervision_timeout_ms=1000,  # Too short, but can't exceed 32000ms
        )

        assert max_int == 800  # 1000ms / 1.25ms
        assert lat == 20

        # Calculate minimum required timeout would be:
        # (1 + 20) * 800 * 1.25ms * 2 = 42000ms = 4200 units
        # But BLE spec max is 3200 units (32000ms)
        # So timeout should be clamped to 3200
        assert timeout == 3200  # Clamped to spec maximum

    def test_negative_values_clamped(self):
        """Test that negative values are clamped to 0/minimum."""
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=-100,
            max_interval_ms=-50,
            latency=-5,
            supervision_timeout_ms=-1000,
        )

        # All should be clamped to valid minimums
        assert min_int == 6  # Minimum interval
        assert max_int == 6
        assert lat == 0  # Latency can be 0
        assert timeout == 10  # Minimum timeout

    def test_power_save_realistic_values(self):
        """Test realistic power-save parameters."""
        # Typical power-save: 500-1000ms interval, latency 15, timeout 12s
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=500,
            max_interval_ms=1000,
            latency=15,
            supervision_timeout_ms=12000,
        )

        assert min_int == 400  # 500ms / 1.25ms
        assert max_int == 800  # 1000ms / 1.25ms
        assert lat == 15
        # Timeout might be adjusted upward due to constraint
        assert timeout >= 1200  # At least 12s

    def test_low_latency_realistic_values(self):
        """Test realistic low-latency parameters."""
        # Typical low-latency: 15-30ms interval, latency 0, timeout 4s
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms=15,
            max_interval_ms=30,
            latency=0,
            supervision_timeout_ms=4000,
        )

        assert min_int == 12  # 15ms / 1.25ms
        assert max_int == 24  # 30ms / 1.25ms
        assert lat == 0
        assert timeout == 400  # 4000ms / 10ms
