"""Integration tests for connection parameters in BlueZ backend."""

import sys
from unittest.mock import patch

import pytest

# Skip entire module if not on Linux (BlueZ backend requires dbus-fast)
if sys.platform != "linux":
    pytest.skip("BlueZ backend tests require Linux", allow_module_level=True)

from bleak.args.connection import ConnectionParameters, ConnectionPolicy
from bleak.backends.bluezdbus.client import BleakClientBlueZDBus


class TestBlueZConnectionParameters:
    """Test connection parameter handling in BlueZ backend."""

    @pytest.mark.asyncio
    async def test_update_connection_parameters_when_not_connected(self):
        """Test that update_connection_parameters handles not connected gracefully."""
        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF")
        params = ConnectionParameters(
            min_interval_ms=100,
            max_interval_ms=200,
            latency=5,
            supervision_timeout_ms=5000,
        )

        # Should not raise, just log and return
        await client.update_connection_parameters(params)

    @pytest.mark.asyncio
    async def test_apply_connection_parameters_with_explicit_values(self):
        """Test applying explicit connection parameter values."""
        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF")
        client._is_connected = True
        client._device_info = {"Adapter": "/org/bluez/hci0", "AddressType": "public"}

        params = ConnectionParameters(
            min_interval_ms=100,
            max_interval_ms=200,
            latency=5,
            supervision_timeout_ms=5000,
        )

        with patch(
            "bleak.backends.bluezdbus.client.update_connection_parameters_via_mgmt"
        ) as mock_mgmt:
            mock_mgmt.return_value = True

            await client._apply_connection_parameters(params)

            # Verify mgmt function was called with correct parameters
            mock_mgmt.assert_called_once()
            call_args = mock_mgmt.call_args
            assert call_args.kwargs["adapter_id"] == 0  # hci0
            assert call_args.kwargs["device_address"] == "AA:BB:CC:DD:EE:FF"
            assert call_args.kwargs["address_type"] == "public"
            assert call_args.kwargs["min_interval_ms"] == 100
            assert call_args.kwargs["max_interval_ms"] == 200
            assert call_args.kwargs["latency"] == 5
            assert call_args.kwargs["supervision_timeout_ms"] == 5000

    @pytest.mark.asyncio
    async def test_apply_connection_parameters_with_policy(self):
        """Test applying connection parameters using policy."""
        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF")
        client._is_connected = True
        client._device_info = {"Adapter": "/org/bluez/hci1", "AddressType": "random"}

        params = ConnectionParameters(policy=ConnectionPolicy.POWER_SAVE)

        with patch(
            "bleak.backends.bluezdbus.client.update_connection_parameters_via_mgmt"
        ) as mock_mgmt:
            mock_mgmt.return_value = True

            await client._apply_connection_parameters(params)

            # Verify mgmt function was called
            mock_mgmt.assert_called_once()
            call_args = mock_mgmt.call_args

            # Policy defaults should have been applied
            assert call_args.kwargs["adapter_id"] == 1  # hci1
            assert call_args.kwargs["address_type"] == "random"
            # Power save policy should have long intervals and higher latency
            assert call_args.kwargs["min_interval_ms"] >= 100
            assert call_args.kwargs["max_interval_ms"] >= 500
            assert call_args.kwargs["latency"] > 0

    @pytest.mark.asyncio
    async def test_apply_connection_parameters_missing_required_values(self):
        """Test that missing required values are handled gracefully."""
        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF")
        client._is_connected = True
        client._device_info = {"Adapter": "/org/bluez/hci0", "AddressType": "public"}

        # Parameters with no policy and missing values
        params = ConnectionParameters(
            min_interval_ms=100,
            # Missing max_interval_ms, latency, timeout
        )

        with patch(
            "bleak.backends.bluezdbus.client.update_connection_parameters_via_mgmt"
        ) as mock_mgmt:
            await client._apply_connection_parameters(params)

            # Should not call mgmt because parameters are incomplete
            mock_mgmt.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_connection_parameters_policy_with_override(self):
        """Test policy with explicit override of some parameters."""
        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF")
        client._is_connected = True
        client._device_info = {"Adapter": "/org/bluez/hci0", "AddressType": "public"}

        params = ConnectionParameters(
            policy=ConnectionPolicy.BALANCED,
            min_interval_ms=75,  # Override the policy default
        )

        with patch(
            "bleak.backends.bluezdbus.client.update_connection_parameters_via_mgmt"
        ) as mock_mgmt:
            mock_mgmt.return_value = True

            await client._apply_connection_parameters(params)

            mock_mgmt.assert_called_once()
            call_args = mock_mgmt.call_args

            # Our override should be used
            assert call_args.kwargs["min_interval_ms"] == 75
            # Other values should come from BALANCED policy defaults
            assert call_args.kwargs["max_interval_ms"] is not None
            assert call_args.kwargs["latency"] is not None
            assert call_args.kwargs["supervision_timeout_ms"] is not None

    @pytest.mark.asyncio
    async def test_apply_connection_parameters_adapter_extraction_hci0(self):
        """Test extracting adapter ID from hci0 path."""
        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF")
        client._is_connected = True
        client._device_info = {"Adapter": "/org/bluez/hci0", "AddressType": "public"}

        params = ConnectionParameters(policy=ConnectionPolicy.LOW_LATENCY)

        with patch(
            "bleak.backends.bluezdbus.client.update_connection_parameters_via_mgmt"
        ) as mock_mgmt:
            mock_mgmt.return_value = True
            await client._apply_connection_parameters(params)

            assert mock_mgmt.call_args.kwargs["adapter_id"] == 0

    @pytest.mark.asyncio
    async def test_apply_connection_parameters_adapter_extraction_hci5(self):
        """Test extracting adapter ID from hci5 path."""
        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF")
        client._is_connected = True
        client._device_info = {"Adapter": "/org/bluez/hci5", "AddressType": "public"}

        params = ConnectionParameters(policy=ConnectionPolicy.LOW_LATENCY)

        with patch(
            "bleak.backends.bluezdbus.client.update_connection_parameters_via_mgmt"
        ) as mock_mgmt:
            mock_mgmt.return_value = True
            await client._apply_connection_parameters(params)

            assert mock_mgmt.call_args.kwargs["adapter_id"] == 5

    @pytest.mark.asyncio
    async def test_apply_connection_parameters_invalid_adapter_path(self):
        """Test handling of invalid adapter path format."""
        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF")
        client._is_connected = True
        client._device_info = {
            "Adapter": "/org/bluez/invalid_adapter",
            "AddressType": "public",
        }

        params = ConnectionParameters(policy=ConnectionPolicy.LOW_LATENCY)

        with patch(
            "bleak.backends.bluezdbus.client.update_connection_parameters_via_mgmt"
        ) as mock_mgmt:
            await client._apply_connection_parameters(params)

            # Should not call mgmt with invalid adapter path
            mock_mgmt.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_connection_parameters_mgmt_failure(self):
        """Test handling of mgmt interface failure."""
        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF")
        client._is_connected = True
        client._device_info = {"Adapter": "/org/bluez/hci0", "AddressType": "public"}

        params = ConnectionParameters(policy=ConnectionPolicy.LOW_LATENCY)

        with patch(
            "bleak.backends.bluezdbus.client.update_connection_parameters_via_mgmt"
        ) as mock_mgmt:
            mock_mgmt.return_value = False  # Simulate failure

            # Should not raise, just log
            await client._apply_connection_parameters(params)

            mock_mgmt.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_parameters_passed_to_init(self):
        """Test that connection parameters passed to __init__ are stored."""
        params = ConnectionParameters(policy=ConnectionPolicy.POWER_SAVE)

        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF", connection_parameters=params)

        assert client._connection_parameters == params

    @pytest.mark.asyncio
    async def test_public_update_method_calls_internal_helper(self):
        """Test that public update_connection_parameters calls internal helper."""
        client = BleakClientBlueZDBus("AA:BB:CC:DD:EE:FF")
        client._is_connected = True

        params = ConnectionParameters(policy=ConnectionPolicy.BALANCED)

        with patch.object(client, "_apply_connection_parameters") as mock_apply:
            await client.update_connection_parameters(params)

            mock_apply.assert_called_once_with(params)
