"""
HCI Management Interface for BlueZ Connection Parameter Control.

This module provides low-level access to the Linux kernel's HCI management
interface for controlling BLE connection parameters.

References:
- https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/mgmt.rst
- https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/net/bluetooth/hci.h
"""

import logging
import socket
import struct
from typing import Optional

logger = logging.getLogger(__name__)

# HCI Management Socket Constants
BTPROTO_HCI = 1
HCI_DEV_NONE = 0xFFFF
HCI_CHANNEL_CONTROL = 3

# Management Commands
MGMT_OP_LOAD_CONN_PARAM = 0x0030

# Address Types
BDADDR_BREDR = 0x00
BDADDR_LE_PUBLIC = 0x01
BDADDR_LE_RANDOM = 0x02


def _bdaddr_to_bytes(address: str, address_type: str = "public") -> tuple[bytes, int]:
    """
    Convert Bluetooth address string to bytes and address type.

    Args:
        address: Bluetooth address in format "XX:XX:XX:XX:XX:XX"
        address_type: "public" or "random"

    Returns:
        Tuple of (address_bytes, address_type_int)
    """
    # Parse address - BlueZ uses reverse byte order
    addr_bytes = bytes.fromhex(address.replace(":", ""))[::-1]

    addr_type = BDADDR_LE_PUBLIC if address_type == "public" else BDADDR_LE_RANDOM

    return addr_bytes, addr_type


def connection_params_to_ble_units(
    min_interval_ms: Optional[int],
    max_interval_ms: Optional[int],
    latency: Optional[int],
    supervision_timeout_ms: Optional[int],
) -> tuple[int, int, int, int]:
    """
    Convert connection parameters from milliseconds to BLE spec units.

    BLE Spec units:
    - Connection interval: 1.25ms units (range: 6-3200, i.e., 7.5ms-4000ms)
    - Slave latency: number of events (range: 0-499)
    - Supervision timeout: 10ms units (range: 10-3200, i.e., 100ms-32000ms)

    Args:
        min_interval_ms: Minimum connection interval in milliseconds
        max_interval_ms: Maximum connection interval in milliseconds
        latency: Slave latency (number of connection events)
        supervision_timeout_ms: Supervision timeout in milliseconds

    Returns:
        Tuple of (min_interval_units, max_interval_units, latency, timeout_units)
        with values clamped to BLE spec ranges.
    """
    # Connection interval: milliseconds to 1.25ms units
    # Spec range: 6 (7.5ms) to 3200 (4000ms)
    min_interval_units = 6  # Default to 7.5ms
    max_interval_units = 3200  # Default to 4000ms

    if min_interval_ms is not None:
        min_interval_units = max(6, min(3200, int(min_interval_ms / 1.25)))

    if max_interval_ms is not None:
        max_interval_units = max(6, min(3200, int(max_interval_ms / 1.25)))

    # Ensure min <= max
    if min_interval_units > max_interval_units:
        min_interval_units, max_interval_units = max_interval_units, min_interval_units

    # Slave latency: already in correct units (number of events)
    # Spec range: 0 to 499
    latency_units = 0 if latency is None else max(0, min(499, latency))

    # Supervision timeout: milliseconds to 10ms units
    # Spec range: 10 (100ms) to 3200 (32000ms)
    timeout_units = 3200  # Default to 32s
    if supervision_timeout_ms is not None:
        timeout_units = max(10, min(3200, int(supervision_timeout_ms / 10)))

    # Validate supervision timeout constraint:
    # timeout must be > (1 + latency) * max_interval * 2
    # This ensures connection isn't lost during normal latency operation
    min_timeout_units = (
        int((1 + latency_units) * max_interval_units * 1.25 / 10 * 2) + 1
    )
    if timeout_units < min_timeout_units:
        logger.debug(
            f"Supervision timeout {timeout_units * 10}ms too short for latency {latency_units} "
            f"and interval {max_interval_units * 1.25}ms. "
            f"Increasing to {min_timeout_units * 10}ms"
        )
        timeout_units = min(3200, min_timeout_units)

    return min_interval_units, max_interval_units, latency_units, timeout_units


async def update_connection_parameters_via_mgmt(
    adapter_id: int,
    device_address: str,
    address_type: str,
    min_interval_ms: int,
    max_interval_ms: int,
    latency: int,
    supervision_timeout_ms: int,
) -> bool:
    """
    Update BLE connection parameters using the HCI management interface.

    This uses the MGMT_OP_LOAD_CONN_PARAM command to suggest connection
    parameters to the kernel. The kernel and controller will use these
    as hints but may not apply them exactly.

    Args:
        adapter_id: HCI adapter index (0 for hci0, 1 for hci1, etc.)
        device_address: Bluetooth device address
        address_type: "public" or "random"
        min_interval_ms: Minimum connection interval in ms
        max_interval_ms: Maximum connection interval in ms
        latency: Slave latency (number of connection events)
        supervision_timeout_ms: Supervision timeout in ms

    Returns:
        True if the command was sent successfully, False otherwise.

    Note:
        This requires CAP_NET_ADMIN capability or root access.
        It will fail gracefully if permissions are insufficient.
    """
    try:
        # Convert parameters to BLE units
        min_int, max_int, lat, timeout = connection_params_to_ble_units(
            min_interval_ms, max_interval_ms, latency, supervision_timeout_ms
        )

        logger.debug(
            f"Setting connection parameters via mgmt: "
            f"adapter={adapter_id}, address={device_address}, "
            f"min_interval={min_int} ({min_int * 1.25}ms), "
            f"max_interval={max_int} ({max_int * 1.25}ms), "
            f"latency={lat}, timeout={timeout} ({timeout * 10}ms)"
        )

        # Create HCI management socket
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_RAW, BTPROTO_HCI)

        try:
            # Bind to the control channel
            sock.bind((adapter_id, HCI_CHANNEL_CONTROL))

            # Convert address to bytes
            addr_bytes, addr_type_val = _bdaddr_to_bytes(device_address, address_type)

            # Build the MGMT command packet
            # Command format for MGMT_OP_LOAD_CONN_PARAM:
            # - param_count (2 bytes)
            # Followed by param_count entries of:
            # - addr (6 bytes)
            # - addr_type (1 byte)
            # - min_interval (2 bytes, little-endian)
            # - max_interval (2 bytes, little-endian)
            # - latency (2 bytes, little-endian)
            # - timeout (2 bytes, little-endian)

            param_count = 1
            param_entry = struct.pack(
                "<6sBHHHH",
                addr_bytes,
                addr_type_val,
                min_int,
                max_int,
                lat,
                timeout,
            )

            params = struct.pack("<H", param_count) + param_entry

            # Management message header:
            # - command_code (2 bytes)
            # - controller_index (2 bytes)
            # - parameter_length (2 bytes)
            header = struct.pack(
                "<HHH",
                MGMT_OP_LOAD_CONN_PARAM,
                adapter_id,
                len(params),
            )

            message = header + params

            # Send the command
            sock.sendall(message)

            logger.debug(
                f"Successfully sent connection parameter update to adapter {adapter_id}"
            )

            return True

        finally:
            sock.close()

    except PermissionError:
        logger.debug(
            "Permission denied accessing HCI management interface. "
            "Connection parameter updates require CAP_NET_ADMIN or root. "
            "Parameters not applied."
        )
        return False

    except OSError as e:
        logger.debug(
            f"Failed to access HCI management interface: {e}. "
            f"Connection parameters not applied."
        )
        return False

    except Exception as e:
        logger.warning(
            f"Unexpected error updating connection parameters via mgmt: {e}",
            exc_info=True,
        )
        return False
