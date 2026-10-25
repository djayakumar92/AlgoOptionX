"""Fail-closed execution policy for the research application.

This module deliberately has no broker client, network dependency, or order
submission interface. The current application is paper/research only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


class ExecutionPolicyError(ValueError):
    """Raised when configuration requests an unsupported execution mode."""


@dataclass(frozen=True)
class ExecutionPolicy:
    """The only supported mode is PAPER; there is no live-mode escape hatch."""

    mode: str = "PAPER"

    def __post_init__(self) -> None:
        if self.mode != "PAPER":
            raise ExecutionPolicyError(
                "Only PAPER execution mode is supported; live execution is disabled."
            )

    @classmethod
    def from_mapping(cls, value: object) -> "ExecutionPolicy":
        if not isinstance(value, Mapping):
            raise ExecutionPolicyError("The [execution] setting must be a table.")
        unknown = set(value) - {"mode"}
        if unknown:
            names = ", ".join(sorted(str(name) for name in unknown))
            raise ExecutionPolicyError(f"Unsupported execution setting(s): {names}.")
        mode = value.get("mode", "PAPER")
        if not isinstance(mode, str):
            raise ExecutionPolicyError("execution.mode must be the string 'PAPER'.")
        return cls(mode=mode)
