"""
Test cases for the MessageContextLoggerPlugin JSONL debug output.
"""

import asyncio
import json
import os
import sys
import types


class _BasePlugin:
    def __init__(self):
        self.options = {}

    @classmethod
    def option_schema(cls):
        return {}

    def set_options(self, values):
        for key, value in values.items():
            if key not in self.option_schema():
                raise ValueError(key)
            self.options[key] = value
        self.refresh_options()
        return dict(self.options)

    def get_options(self):
        return dict(self.options)

    def refresh_options(self):
        return None


class PluginContext:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class PluginBlockError(Exception):
    pass


def _install_kohaku_stubs(tmp_path):
    base_mod = types.ModuleType("kohakuterrarium.modules.plugin.base")
    base_mod.BasePlugin = _BasePlugin
    base_mod.PluginBlockError = PluginBlockError
    base_mod.PluginContext = PluginContext

    logging_mod = types.ModuleType("kohakuterrarium.utils.logging")
    logging_mod.get_logger = lambda name: types.SimpleNamespace(
        info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None
    )
    logging_mod._default_log_dir = lambda: tmp_path
    logging_mod._make_log_filename = lambda: "2026-05-20_110000_pid1_deadbeef.log"

    sys.modules["kohakuterrarium"] = types.ModuleType("kohakuterrarium")
    sys.modules["kohakuterrarium.modules"] = types.ModuleType("kohakuterrarium.modules")
    sys.modules["kohakuterrarium.modules.plugin"] = types.ModuleType(
        "kohakuterrarium.modules.plugin"
    )
    sys.modules["kohakuterrarium.modules.plugin.base"] = base_mod
    sys.modules["kohakuterrarium.utils"] = types.ModuleType("kohakuterrarium.utils")
    sys.modules["kohakuterrarium.utils.logging"] = logging_mod


def test_message_context_logger_writes_full_pre_and_post_events(tmp_path):
    _install_kohaku_stubs(tmp_path)
    from kt_guard_plugin.plugins.message_context_logger import (
        MessageContextLoggerPlugin,
    )

    plugin = MessageContextLoggerPlugin(
        options={
            "log_on_load": True,
            "log_pre_llm_call": True,
            "log_post_llm_call": True,
            "max_bytes": 1024 * 1024,
            "backup_count": 1,
        }
    )
    plugin._log_path = tmp_path / f"message-context-{os.getpid()}.jsonl"

    messages = [
        {"role": "system", "content": "full system prompt"},
        {"role": "user", "content": "full user text"},
    ]
    tools = [{"name": "read_file", "description": "full tool schema"}]

    async def run_hooks():
        await plugin.on_load(
            PluginContext(
                agent_name="debugger",
                session_id="session-1",
                model="test-model",
                working_dir=tmp_path,
            )
        )
        pre_result = await plugin.pre_llm_call(
            messages,
            model="test-model",
            tools=tools,
        )
        post_result = await plugin.post_llm_call(
            messages,
            response="full assistant response",
            usage={"input_tokens": 10, "output_tokens": 3},
            model="test-model",
        )
        await plugin.on_unload()
        return pre_result, post_result

    pre_result, post_result = asyncio.run(run_hooks())

    assert pre_result is None
    assert post_result is None

    events = [
        json.loads(line)
        for line in plugin._log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["event"] for event in events] == [
        "plugin_loaded",
        "pre_llm_call",
        "post_llm_call",
    ]
    assert events[1]["messages"] == messages
    assert events[1]["tools"] == tools
    assert "tools" not in events[1]["kwargs"]
    assert events[1]["system_positions"] == [0]
    assert events[2]["response"] == "full assistant response"
    assert events[2]["usage"] == {"input_tokens": 10, "output_tokens": 3}
    assert "messages" not in events[2]
    assert events[2]["message_summary"] == [
        {
            "index": 0,
            "role": "system",
            "content_type": "str",
            "content_length": len("full system prompt"),
        },
        {
            "index": 1,
            "role": "user",
            "content_type": "str",
            "content_length": len("full user text"),
        },
    ]
    assert events[1]["call_id"] == events[2]["call_id"]
