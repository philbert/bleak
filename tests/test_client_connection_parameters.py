"""Integration tests for connection parameters in BleakClient."""

import pytest

from bleak import BleakClient
from bleak.args.connection import ConnectionParameters, ConnectionPolicy


class TestBleakClientConnectionParameters:
    """Test that BleakClient accepts connection parameters."""

    def test_client_init_with_connection_parameters(self):
        """Test creating BleakClient with connection parameters."""
        params = ConnectionParameters(
            min_interval_ms=100,
            max_interval_ms=200,
            latency=5,
            supervision_timeout_ms=5000,
        )

        # Should not raise
        client = BleakClient(
            "00:11:22:33:44:55",
            connection_parameters=params,
        )

        assert client is not None
        # Backend should have received the parameters
        assert client._backend._connection_parameters == params

    def test_client_init_with_policy(self):
        """Test creating BleakClient with connection policy."""
        params = ConnectionParameters(policy=ConnectionPolicy.POWER_SAVE)

        client = BleakClient(
            "00:11:22:33:44:55",
            connection_parameters=params,
        )

        assert client is not None
        assert client._backend._connection_parameters == params
        assert (
            client._backend._connection_parameters.policy == ConnectionPolicy.POWER_SAVE
        )

    def test_client_init_without_connection_parameters(self):
        """Test backward compatibility - no connection parameters."""
        # Should work exactly as before
        client = BleakClient("00:11:22:33:44:55")

        assert client is not None
        assert client._backend._connection_parameters is None

    def test_update_connection_parameters_method_exists(self):
        """Test that update_connection_parameters method exists."""
        client = BleakClient("00:11:22:33:44:55")

        # Method should exist and be callable
        assert hasattr(client, "update_connection_parameters")
        assert callable(client.update_connection_parameters)

    @pytest.mark.asyncio
    async def test_update_connection_parameters_callable(self):
        """Test that update_connection_parameters can be called."""
        client = BleakClient("00:11:22:33:44:55")
        params = ConnectionParameters(policy=ConnectionPolicy.LOW_LATENCY)

        # Should not raise even when not connected
        # (backends should handle gracefully)
        await client.update_connection_parameters(params)
