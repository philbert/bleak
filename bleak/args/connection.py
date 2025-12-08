"""
Connection parameter arguments
-------------------------------
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ConnectionPolicy(Enum):
    """
    High-level policy hint for BLE connection parameters.

    Platforms that cannot set precise connection parameters can use this
    as a hint to select appropriate defaults.

    .. versionadded:: 2.1.0
    """

    FASTEST_RESPONSE = "fastest_response"
    """
    Optimize for fastest possible response time.
    Uses the shortest connection intervals with zero latency.
    Highest power consumption.
    """

    RESPONSIVE = "responsive"
    """
    Optimize for responsive interaction with moderate power usage.
    Short connection intervals with zero latency.
    Higher power consumption than balanced mode.
    """

    BALANCED = "balanced"
    """
    Balance between responsiveness and power consumption.
    Moderate connection intervals with zero latency.
    """

    SLOW_UPDATES = "slow_updates"
    """
    Optimize for infrequent updates with lower power consumption.
    Longer connection intervals with some slave latency.
    Suitable for devices that don't need frequent updates.
    """

    LOWEST_POWER = "lowest_power"
    """
    Optimize for maximum power saving.
    Uses the longest connection intervals with highest slave latency.
    Suitable for battery-sensitive devices with very infrequent updates.
    """


@dataclass
class ConnectionParameters:
    """
    BLE connection parameters for tuning connection behavior.

    This class allows optional control over BLE connection parameters to optimize
    for different use cases (low latency vs. power saving). Support varies by platform.

    If a platform does not support setting connection parameters, these settings
    will be silently ignored.

    Parameters can be specified either through explicit numeric values or through
    a high-level policy. If both are provided, explicit numeric values take precedence.

    Args:
        min_interval_ms: Minimum connection interval in milliseconds.
            Defines the shortest time between connection events.
            Valid range is typically 7.5-4000 ms (Bluetooth spec).

        max_interval_ms: Maximum connection interval in milliseconds.
            Defines the longest time between connection events.
            Valid range is typically 7.5-4000 ms (Bluetooth spec).
            Must be >= min_interval_ms.

        latency: Slave latency (number of connection events).
            Number of consecutive connection events the peripheral can skip
            without losing the connection. Allows the peripheral to save power
            by not responding to every connection event.
            Valid range is typically 0-499.

        supervision_timeout_ms: Supervision timeout in milliseconds.
            Maximum time before the connection is considered lost if no data
            is exchanged. Must be larger than the effective connection interval
            accounting for latency.
            Valid range is typically 100-32000 ms (Bluetooth spec).

        policy: High-level connection policy hint.
            If set without explicit numeric parameters, platform-specific
            defaults for the chosen policy will be used.

        preferred_phys: List of preferred PHY types.
            Options typically include "1m", "2m", "coded".
            Platform support varies. May be ignored on platforms that don't
            support PHY selection.

        preferred_mtu: Preferred MTU size in bytes.
            Maximum transmission unit for ATT protocol.
            Actual MTU is negotiated with the peripheral and may be smaller.
            Platform support varies.

    Example:
        >>> # Power-save mode with explicit parameters
        >>> params = ConnectionParameters(
        ...     min_interval_ms=500,
        ...     max_interval_ms=1000,
        ...     latency=10,
        ...     supervision_timeout_ms=10000
        ... )
        >>>
        >>> # Using policy hint
        >>> params = ConnectionParameters(policy=ConnectionPolicy.LOWEST_POWER)
        >>>
        >>> # Connect with custom parameters
        >>> async with BleakClient(address, connection_parameters=params) as client:
        ...     # Device will use power-save connection parameters
        ...     pass

    .. versionadded:: 2.1.0
    """

    min_interval_ms: Optional[int] = None
    max_interval_ms: Optional[int] = None
    latency: Optional[int] = None
    supervision_timeout_ms: Optional[int] = None
    policy: Optional[ConnectionPolicy] = None
    preferred_phys: Optional[list[str]] = None
    preferred_mtu: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate connection parameters."""
        if self.min_interval_ms is not None and self.max_interval_ms is not None:
            if self.min_interval_ms > self.max_interval_ms:
                raise ValueError(
                    f"min_interval_ms ({self.min_interval_ms}) must be <= "
                    f"max_interval_ms ({self.max_interval_ms})"
                )

        if self.min_interval_ms is not None and self.min_interval_ms < 0:
            raise ValueError(
                f"min_interval_ms must be >= 0, got {self.min_interval_ms}"
            )

        if self.max_interval_ms is not None and self.max_interval_ms < 0:
            raise ValueError(
                f"max_interval_ms must be >= 0, got {self.max_interval_ms}"
            )

        if self.latency is not None and self.latency < 0:
            raise ValueError(f"latency must be >= 0, got {self.latency}")

        if self.supervision_timeout_ms is not None and self.supervision_timeout_ms < 0:
            raise ValueError(
                f"supervision_timeout_ms must be >= 0, got {self.supervision_timeout_ms}"
            )


def get_policy_defaults(policy: ConnectionPolicy) -> ConnectionParameters:
    """
    Get default connection parameters for a given policy.

    Args:
        policy: The connection policy.

    Returns:
        ConnectionParameters with numeric values set according to the policy.

    .. versionadded:: 2.1.0
    """
    if policy == ConnectionPolicy.FASTEST_RESPONSE:
        return ConnectionParameters(
            min_interval_ms=15,
            max_interval_ms=30,
            latency=0,
            supervision_timeout_ms=4000,
            policy=policy,
        )
    elif policy == ConnectionPolicy.RESPONSIVE:
        return ConnectionParameters(
            min_interval_ms=30,
            max_interval_ms=50,
            latency=0,
            supervision_timeout_ms=5000,
            policy=policy,
        )
    elif policy == ConnectionPolicy.BALANCED:
        return ConnectionParameters(
            min_interval_ms=50,
            max_interval_ms=100,
            latency=1,
            supervision_timeout_ms=6000,
            policy=policy,
        )
    elif policy == ConnectionPolicy.SLOW_UPDATES:
        return ConnectionParameters(
            min_interval_ms=100,
            max_interval_ms=200,
            latency=4,
            supervision_timeout_ms=7000,
            policy=policy,
        )
    elif policy == ConnectionPolicy.LOWEST_POWER:
        return ConnectionParameters(
            min_interval_ms=200,
            max_interval_ms=1000,
            latency=8,
            supervision_timeout_ms=8000,
            policy=policy,
        )
    else:
        raise ValueError(f"Unknown policy: {policy}")
