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

"""Structured debug logging for LLM message context.

This plugin records full pre/post LLM context as JSONL for runtime debugging.
It is intentionally observation-only: hooks never rewrite messages or
responses, and logging failures do not block the agent.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from kohakuterrarium.modules.plugin.base import BasePlugin, PluginContext
from kohakuterrarium.utils.logging import (
    _default_log_dir,
    _make_log_filename,
    get_logger,
)

logger = get_logger(__name__)


class MessageContextLoggerPlugin(BasePlugin):
    """Write full LLM request/response context to a rotating JSONL log."""

    name = "message_context_logger"
    priority = 10_000

    @classmethod
    def option_schema(cls) -> dict[str, dict[str, Any]]:
        """Return runtime-mutable option metadata for UI introspection."""
        return {
            "log_on_load": {
                "type": "bool",
                "default": True,
                "doc": "Whether to record plugin load context.",
            },
            "log_pre_llm_call": {
                "type": "bool",
                "default": True,
                "doc": "Whether to record full messages/tools before LLM calls.",
            },
            "log_post_llm_call": {
                "type": "bool",
                "default": True,
                "doc": "Whether to record full responses and usage after LLM calls.",
            },
            "max_bytes": {
                "type": "int",
                "default": 10 * 1024 * 1024,
                "min": 1,
                "doc": "Maximum JSONL file size before rotation.",
            },
            "backup_count": {
                "type": "int",
                "default": 5,
                "min": 0,
                "doc": "Number of rotated JSONL backups to retain.",
            },
        }

    def __init__(
        self, *, options: dict[str, Any] | None = None, **kwargs: Any
    ) -> None:
        """Initialize plugin options and the lazy JSONL writer."""
        super().__init__()
        if options is not None and not isinstance(options, dict):
            raise TypeError("options must be a mapping")

        self.options: dict[str, str] = {
            key: spec.get("default", "") for key, spec in self.option_schema().items()
        }
        merged_options = dict(options or {})
        merged_options.update(kwargs)
        if merged_options:
            self.set_options(merged_options)
        else:
            self.refresh_options()

        self.agent_name = ""
        self.session_id = ""
        self.model = ""
        self.working_dir = ""
        self._call_seq = 0
        self._pending_call_ids: deque[str] = deque()
        self._json_logger: logging.Logger | None = None
        self._handler: RotatingFileHandler | None = None
        self._log_path: Path | None = None

    def refresh_options(self) -> None:
        """Apply validated option values to runtime fields."""
        old_rotation = (
            getattr(self, "max_bytes", None),
            getattr(self, "backup_count", None),
        )
        self.log_on_load = bool(self.options.get("log_on_load", True))
        self.log_pre_llm_call = bool(self.options.get("log_pre_llm_call", True))
        self.log_post_llm_call = bool(self.options.get("log_post_llm_call", True))
        self.max_bytes = int(self.options.get("max_bytes", 10 * 1024 * 1024))
        self.backup_count = int(self.options.get("backup_count", 5))
        new_rotation = (self.max_bytes, self.backup_count)
        if old_rotation not in ((None, None), new_rotation):
            self._close_handler()

    async def on_load(self, context: PluginContext) -> None:
        """Capture runtime metadata and optionally write a load event."""
        self.agent_name = str(getattr(context, "agent_name", "") or "")
        self.session_id = str(getattr(context, "session_id", "") or "")
        self.model = str(getattr(context, "model", "") or "")
        working_dir = getattr(context, "working_dir", "") or ""
        self.working_dir = str(working_dir)

        if self.log_on_load:
            self._write_event(
                "plugin_loaded",
                {
                    "context": {
                        "agent_name": self.agent_name,
                        "session_id": self.session_id,
                        "model": self.model,
                        "working_dir": self.working_dir,
                    },
                    "options": self.get_options(),
                    "log_path": str(self._ensure_log_path()),
                },
            )

    async def on_unload(self) -> None:
        """Close the JSONL handler when the plugin unloads."""
        self._close_handler()

    async def pre_llm_call(
        self, messages: list[dict], **kwargs: Any
    ) -> list[dict] | None:
        """Record full outgoing messages and tools before each LLM request."""
        if not self.log_pre_llm_call:
            return None

        call_id = self._next_call_id()
        self._pending_call_ids.append(call_id)
        roles = [message.get("role") for message in messages]
        system_positions = [
            index for index, message in enumerate(messages)
            if message.get("role") == "system"
        ]

        self._write_event(
            "pre_llm_call",
            {
                "call_id": call_id,
                "model": kwargs.get("model", self.model),
                "message_count": len(messages),
                "roles": roles,
                "system_positions": system_positions,
                "tools": kwargs.get("tools"),
                "messages": messages,
                "kwargs": self._jsonable(kwargs),
            },
        )
        return None

    async def post_llm_call(
        self, messages: list[dict], response: str, usage: dict, **kwargs: Any
    ) -> str | None:
        """Record full assistant response and usage after each LLM request."""
        if not self.log_post_llm_call:
            return None

        call_id = self._pending_call_ids.popleft() if self._pending_call_ids else None
        roles = [message.get("role") for message in messages]
        system_positions = [
            index for index, message in enumerate(messages)
            if message.get("role") == "system"
        ]

        self._write_event(
            "post_llm_call",
            {
                "call_id": call_id,
                "model": kwargs.get("model", self.model),
                "message_count": len(messages),
                "roles": roles,
                "system_positions": system_positions,
                "messages": messages,
                "response": response,
                "usage": usage,
                "kwargs": self._jsonable(kwargs),
            },
        )
        return None

    def _next_call_id(self) -> str:
        self._call_seq += 1
        session = self.session_id or "no-session"
        agent = self.agent_name or "unknown-agent"
        return f"{session}:{agent}:{os.getpid()}:{self._call_seq}"

    def _write_event(self, event: str, payload: dict[str, Any]) -> None:
        record = {
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "event": event,
            "plugin": self.name,
            "agent_name": self.agent_name,
            "session_id": self.session_id,
            "pid": os.getpid(),
            **payload,
        }
        try:
            json_logger = self._ensure_json_logger()
            json_logger.info(
                json.dumps(self._jsonable(record), ensure_ascii=False, sort_keys=True)
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "message context logger failed to write event",
                event=event,
                error=str(exc),
                exc_info=True,
            )

    def _ensure_json_logger(self) -> logging.Logger:
        if self._json_logger is not None:
            return self._json_logger

        log_path = self._ensure_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        handler = RotatingFileHandler(
            log_path,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.setLevel(logging.INFO)

        json_logger = logging.getLogger(f"{__name__}.{id(self)}")
        json_logger.handlers.clear()
        json_logger.addHandler(handler)
        json_logger.setLevel(logging.INFO)
        json_logger.propagate = False

        self._handler = handler
        self._json_logger = json_logger
        return json_logger

    def _ensure_log_path(self) -> Path:
        if self._log_path is not None:
            return self._log_path

        base_name = _make_log_filename()
        stem = Path(base_name).stem
        if self.session_id:
            session_hash = hashlib.md5(self.session_id.encode()).hexdigest()[:8]
            stem = f"{stem}_session{session_hash}"
        self._log_path = _default_log_dir() / f"{stem}.message-context.jsonl"
        return self._log_path

    def _close_handler(self) -> None:
        if self._handler is None:
            return
        if self._json_logger is not None:
            self._json_logger.removeHandler(self._handler)
        self._handler.close()
        self._handler = None
        self._json_logger = None

    def _jsonable(self, value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except TypeError:
            pass

        if isinstance(value, dict):
            return {str(key): self._jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._jsonable(item) for item in value]
        if isinstance(value, Path):
            return str(value)
        return repr(value)
