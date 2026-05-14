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

"""Guard plugin that validates and optionally repairs LLM message role order.

This plugin ensures the outgoing message list contains exactly one `system`
message at position 0. When enabled, it can merge multiple system messages and
move them to the first position before the LLM call.
"""

from typing import Any

from kohakuterrarium.modules.plugin.base import BasePlugin, PluginContext
from kohakuterrarium.utils.logging import get_logger

logger = get_logger(__name__)


class MessageRoleGuardPlugin(BasePlugin):
    """Enforce a valid `system` role layout before each LLM request."""

    name = "message_role_guard"
    priority = 1_000  # Make this one of the last pre-LLM plugins to run so it can fix any earlier mistakes.

    @classmethod
    def option_schema(cls) -> dict[str, dict[str, Any]]:
        """Return runtime-mutable option metadata for UI introspection."""
        return {
            "fix": {
                "type": "bool",
                "default": True,
                "doc": (
                    "Whether to automatically fix invalid message ordering. "
                    "If false, only logs warnings."
                ),
            }
        }

    def __init__(
        self, *, options: dict[str, Any] | None = None, **kwargs: Any
    ) -> None:
        """Initialize plugin options.

        Args:
            options: Optional plugin configuration. Supported key:
                - fix: Whether to auto-fix invalid message role placement.
            **kwargs: Flattened options passed by the package loader.
        """
        super().__init__()
        if options is not None and not isinstance(options, dict):
            raise TypeError("options must be a mapping")

        self.options = {"fix": True}
        merged_options = dict(options or {})
        merged_options.update(kwargs)
        if merged_options:
            self.set_options(merged_options)
        else:
            self.refresh_options()
        self.agent_name = ""

    def refresh_options(self) -> None:
        """Apply validated option values to derived runtime fields."""
        self.fix = bool(self.options.get("fix", True))

    async def on_load(self, context: PluginContext) -> None:
        """Capture runtime context metadata when the plugin is loaded."""
        self.agent_name = context.agent_name

    async def pre_llm_call(
        self, messages: list[dict], **kwargs: Any
    ) -> list[dict] | None:
        """Validate system-message placement and optionally repair it.

        Args:
            messages: Outgoing chat messages passed to the provider.
            **kwargs: Extra runtime metadata from the framework.

        Returns:
            None when no mutation is required or auto-fix is disabled.
            A rewritten message list when invalid placement is detected and
            auto-fix is enabled.
        """
        system_positions = [
            i for i, msg in enumerate(messages) if msg.get("role") == "system"
        ]

        # Repair when no system message exists, system is not first,
        # or multiple system messages are present.
        needs_fix = system_positions != [0] or len(system_positions) > 1

        if not needs_fix:
            return None

        roles = [msg.get("role") for msg in messages]
        logger.warning(
            "pre_llm_call message role guard detected invalid system placement",
            agent=self.agent_name,
            model=kwargs.get("model", ""),
            system_positions=system_positions,
            system_count=len(system_positions),
            roles=roles[:40],
            message_count=len(messages),
        )

        if not self.fix:
            return None

        system_contents = [
            str(msg.get("content", ""))
            for msg in messages
            if msg.get("role") == "system" and msg.get("content")
        ]
        non_system = [msg for msg in messages if msg.get("role") != "system"]

        if not system_contents:
            return non_system

        return [
            {"role": "system", "content": "\n\n".join(system_contents)},
            *non_system,
        ]
