# Copyright 2026 SLAPaper
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Process-local QPS throttling for KohakuTerrarium LLM calls."""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from kohakuterrarium.modules.plugin.base import (
    BasePlugin,
    PluginBlockError,
    PluginContext,
)
from kohakuterrarium.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class _ThrottleSettings:
    qps: float
    burst: int


@dataclass
class _LimiterState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    theoretical_arrival_time: float = 0.0


@dataclass(frozen=True)
class _Reservation:
    accepted: bool
    wait_seconds: float


_LIMITERS: dict[str, _LimiterState] = {}
_LIMITERS_LOCK = threading.Lock()


def _get_limiter(model_key: str) -> _LimiterState:
    with _LIMITERS_LOCK:
        limiter = _LIMITERS.get(model_key)
        if limiter is None:
            limiter = _LimiterState()
            _LIMITERS[model_key] = limiter
        return limiter


def _reset_limiters_for_tests() -> None:
    """Clear process-local limiter state for isolated tests."""
    with _LIMITERS_LOCK:
        _LIMITERS.clear()


class QpsThrottlePlugin(BasePlugin):
    """Delay outgoing LLM calls to keep per-model request QPS bounded."""

    name = "qps_throttle"
    priority = 9_000

    @classmethod
    def option_schema(cls) -> dict[str, dict[str, Any]]:
        """Return runtime-mutable option metadata for UI introspection."""
        return {
            "default_qps": {
                "type": "float",
                "default": 1.0,
                "min": 0.000001,
                "doc": "Default allowed LLM requests per second for unlisted models.",
            },
            "default_burst": {
                "type": "int",
                "default": 1,
                "min": 1,
                "doc": "Default burst size for unlisted models.",
            },
            "per_model": {
                "type": "dict",
                "default": {},
                "doc": "Exact model-name overrides: {'model': {'qps': 0.5, 'burst': 1}}.",
            },
            "log_wait_threshold_seconds": {
                "type": "float",
                "default": 0.5,
                "min": 0.0,
                "doc": "Only log throttle waits at or above this duration.",
            },
            "max_wait_seconds": {
                "type": "float",
                "default": 0.0,
                "min": 0.0,
                "doc": "Maximum wait before blocking the call; 0 means unlimited.",
            },
        }

    def __init__(self, *, options: dict[str, Any] | None = None, **kwargs: Any) -> None:
        """Initialize throttle options.

        Accepts both ``options={...}`` and flattened loader kwargs because
        KohakuTerrarium package loading can instantiate plugins either way.
        """
        super().__init__()
        if options is not None and not isinstance(options, dict):
            raise TypeError("options must be a mapping")

        self.options = {
            key: spec.get("default") for key, spec in self.option_schema().items()
        }
        self.agent_name = ""
        self.model = ""

        merged_options = dict(options or {})
        merged_options.update(kwargs)
        if merged_options:
            self.set_options(merged_options)
        else:
            self.refresh_options()

    def set_options(self, values: dict[str, Any]) -> dict[str, Any]:
        """Validate nested throttle settings before committing options."""
        proposed = dict(getattr(self, "options", {}) or {})
        proposed.update(values or {})
        self._parse_runtime_options(proposed)
        return super().set_options(values)

    def refresh_options(self) -> None:
        """Apply validated option values to runtime fields."""
        parsed = self._parse_runtime_options(self.options)
        self.default_settings = parsed["default_settings"]
        self.per_model_settings = parsed["per_model_settings"]
        self.log_wait_threshold_seconds = parsed["log_wait_threshold_seconds"]
        self.max_wait_seconds = parsed["max_wait_seconds"]

    async def on_load(self, context: PluginContext) -> None:
        """Capture runtime context metadata for logging and model fallback."""
        self.agent_name = str(getattr(context, "agent_name", "") or "")
        self.model = str(getattr(context, "model", "") or "")

    async def pre_llm_call(
        self, messages: list[dict], **kwargs: Any
    ) -> list[dict] | None:
        """Reserve a per-model slot and sleep until it is available."""
        model_key = self._model_key(kwargs.get("model"))
        settings = self._settings_for_model(model_key)
        reservation = await self._reserve(model_key, settings)

        if not reservation.accepted:
            raise PluginBlockError(
                (
                    f"qps throttle wait for model {model_key!r} would exceed "
                    f"max_wait_seconds={self.max_wait_seconds:g}"
                )
            )

        wait_seconds = reservation.wait_seconds
        if wait_seconds <= 0:
            return None

        if wait_seconds >= self.log_wait_threshold_seconds:
            logger.info(
                "qps throttle waiting before LLM call",
                agent=self.agent_name,
                model=model_key,
                qps=settings.qps,
                burst=settings.burst,
                wait_seconds=wait_seconds,
                message_count=len(messages),
            )
        await self._sleep(wait_seconds)
        return None

    async def _reserve(
        self, model_key: str, settings: _ThrottleSettings
    ) -> _Reservation:
        limiter = _get_limiter(model_key)
        async with limiter.lock:
            now = self._now()
            interval = 1.0 / settings.qps
            burst_allowance = interval * max(settings.burst - 1, 0)
            earliest_allowed = limiter.theoretical_arrival_time - burst_allowance
            wait_seconds = max(0.0, earliest_allowed - now)

            if self.max_wait_seconds > 0 and wait_seconds > self.max_wait_seconds:
                logger.warning(
                    "qps throttle blocked LLM call",
                    agent=self.agent_name,
                    model=model_key,
                    qps=settings.qps,
                    burst=settings.burst,
                    wait_seconds=wait_seconds,
                    max_wait_seconds=self.max_wait_seconds,
                )
                return _Reservation(False, wait_seconds)

            effective_time = now + wait_seconds
            limiter.theoretical_arrival_time = (
                max(effective_time, limiter.theoretical_arrival_time) + interval
            )
            return _Reservation(True, wait_seconds)

    def _settings_for_model(self, model_key: str) -> _ThrottleSettings:
        return self.per_model_settings.get(model_key, self.default_settings)

    def _model_key(self, raw_model: Any) -> str:
        model = str(raw_model or self.model or "").strip()
        return model or "unknown"

    def _now(self) -> float:
        return time.monotonic()

    async def _sleep(self, delay: float) -> None:
        await asyncio.sleep(delay)

    def _parse_runtime_options(self, options: dict[str, Any]) -> dict[str, Any]:
        default_settings = _ThrottleSettings(
            qps=self._positive_float(options.get("default_qps", 1.0), "default_qps"),
            burst=self._positive_int(options.get("default_burst", 1), "default_burst"),
        )
        per_model = options.get("per_model", {}) or {}
        if not isinstance(per_model, dict):
            raise ValueError("per_model must be a mapping")
        per_model_settings = {
            str(model): self._settings_from_override(str(model), raw, default_settings)
            for model, raw in per_model.items()
        }
        return {
            "default_settings": default_settings,
            "per_model_settings": per_model_settings,
            "log_wait_threshold_seconds": self._non_negative_float(
                options.get("log_wait_threshold_seconds", 0.5),
                "log_wait_threshold_seconds",
            ),
            "max_wait_seconds": self._non_negative_float(
                options.get("max_wait_seconds", 0.0), "max_wait_seconds"
            ),
        }

    def _settings_from_override(
        self, model: str, raw: Any, default: _ThrottleSettings
    ) -> _ThrottleSettings:
        if not isinstance(raw, dict):
            raise ValueError(f"per_model[{model!r}] must be a mapping")
        return _ThrottleSettings(
            qps=self._positive_float(raw.get("qps", default.qps), f"{model}.qps"),
            burst=self._positive_int(raw.get("burst", default.burst), f"{model}.burst"),
        )

    def _positive_float(self, value: Any, name: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a positive number")
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a positive number") from exc
        if parsed <= 0:
            raise ValueError(f"{name} must be > 0")
        return parsed

    def _non_negative_float(self, value: Any, name: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a non-negative number")
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a non-negative number") from exc
        if parsed < 0:
            raise ValueError(f"{name} must be >= 0")
        return parsed

    def _positive_int(self, value: Any, name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a positive integer")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a positive integer") from exc
        if parsed <= 0:
            raise ValueError(f"{name} must be > 0")
        return parsed
