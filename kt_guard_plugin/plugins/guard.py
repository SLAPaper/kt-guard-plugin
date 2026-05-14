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
    priority = 1_000_000

    def __init__(self, *, options: dict[str, Any] | None = None) -> None:
        """Initialize plugin options.

        Args:
            options: Optional plugin configuration. Supported key:
                - fix: Whether to auto-fix invalid message role placement.
        """
        super().__init__()
        opts = options or {}
        self.fix = bool(opts.get("fix", True))
        self.agent_name = ""

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
        
        # 检查是否需要修复：
        # 1. system 不在位置 0，或
        # 2. 没有 system 消息，或
        # 3. 有多个 system 消息
        needs_fix = (
            system_positions != [0]  # system 不在第一位或不存在
            or len(system_positions) > 1  # 多个 system 消息
        )
        
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
