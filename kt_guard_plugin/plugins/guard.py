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

from typing import Any

from kohakuterrarium.modules.plugin.base import BasePlugin, PluginContext
from kohakuterrarium.utils.logging import get_logger

logger = get_logger(__name__)


class MessageRoleGuardPlugin(BasePlugin):
    name = "message_role_guard"
    priority = 1_000_000

    def __init__(self, *, options: dict[str, Any] | None = None) -> None:
        super().__init__()
        opts = options or {}
        self.fix = bool(opts.get("fix", True))
        self.agent_name = ""

    async def on_load(self, context: PluginContext) -> None:
        self.agent_name = context.agent_name

    async def pre_llm_call(
        self, messages: list[dict], **kwargs: Any
    ) -> list[dict] | None:
        system_positions = [
            i for i, msg in enumerate(messages) if msg.get("role") == "system"
        ]
        if system_positions == [0] or not system_positions:
            return None

        roles = [msg.get("role") for msg in messages]
        logger.warning(
            "pre_llm_call message role guard detected invalid system placement",
            agent=self.agent_name,
            model=kwargs.get("model", ""),
            system_positions=system_positions,
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
