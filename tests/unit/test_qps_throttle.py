"""
Test cases for QpsThrottlePlugin process-local per-model throttling.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


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


class _Logger:
    def __init__(self):
        self.info_calls = []
        self.warning_calls = []

    def info(self, *args, **kwargs):
        self.info_calls.append((args, kwargs))

    def warning(self, *args, **kwargs):
        self.warning_calls.append((args, kwargs))

    def debug(self, *args, **kwargs):
        return None


def _install_kohaku_stubs(monkeypatch):
    logger = _Logger()

    base_mod = types.ModuleType("kohakuterrarium.modules.plugin.base")
    base_mod.BasePlugin = _BasePlugin
    base_mod.PluginBlockError = PluginBlockError
    base_mod.PluginContext = PluginContext

    logging_mod = types.ModuleType("kohakuterrarium.utils.logging")
    logging_mod.get_logger = lambda name: logger
    logging_mod._default_log_dir = lambda: Path(".")
    logging_mod._make_log_filename = lambda: "test.log"

    monkeypatch.setitem(
        sys.modules, "kohakuterrarium", types.ModuleType("kohakuterrarium")
    )
    monkeypatch.setitem(
        sys.modules,
        "kohakuterrarium.modules",
        types.ModuleType("kohakuterrarium.modules"),
    )
    monkeypatch.setitem(
        sys.modules,
        "kohakuterrarium.modules.plugin",
        types.ModuleType("kohakuterrarium.modules.plugin"),
    )
    monkeypatch.setitem(sys.modules, "kohakuterrarium.modules.plugin.base", base_mod)
    monkeypatch.setitem(
        sys.modules, "kohakuterrarium.utils", types.ModuleType("kohakuterrarium.utils")
    )
    monkeypatch.setitem(sys.modules, "kohakuterrarium.utils.logging", logging_mod)

    for name in [
        "kt_guard_plugin",
        "kt_guard_plugin.plugins",
        "kt_guard_plugin.plugins.guard",
        "kt_guard_plugin.plugins.message_context_logger",
        "kt_guard_plugin.plugins.qps_throttle",
    ]:
        sys.modules.pop(name, None)

    module = importlib.import_module("kt_guard_plugin.plugins.qps_throttle")
    module._reset_limiters_for_tests()
    return module, logger


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self):
        return self.now

    async def sleep(self, delay):
        self.sleeps.append(delay)


def _plugin(module, clock, **options):
    plugin = module.QpsThrottlePlugin(options=options)
    plugin._now = clock.monotonic
    plugin._sleep = clock.sleep
    return plugin


def test_same_model_concurrent_calls_are_spaced(monkeypatch):
    module, _logger = _install_kohaku_stubs(monkeypatch)
    clock = FakeClock()
    plugin = _plugin(
        module,
        clock,
        default_qps=1.0,
        default_burst=1,
        log_wait_threshold_seconds=0.0,
    )

    async def run_calls():
        await asyncio.gather(
            plugin.pre_llm_call([], model="shared-model"),
            plugin.pre_llm_call([], model="shared-model"),
            plugin.pre_llm_call([], model="shared-model"),
        )

    asyncio.run(run_calls())

    assert clock.sleeps == [1.0, 2.0]


def test_different_models_use_independent_limiters(monkeypatch):
    module, _logger = _install_kohaku_stubs(monkeypatch)
    clock = FakeClock()
    plugin = _plugin(module, clock, default_qps=1.0, default_burst=1)

    async def run_calls():
        await asyncio.gather(
            plugin.pre_llm_call([], model="model-a"),
            plugin.pre_llm_call([], model="model-b"),
        )

    asyncio.run(run_calls())

    assert clock.sleeps == []


def test_per_model_override_and_default_fallback(monkeypatch):
    module, _logger = _install_kohaku_stubs(monkeypatch)
    clock = FakeClock()
    plugin = _plugin(
        module,
        clock,
        default_qps=1.0,
        default_burst=1,
        per_model={"fast-model": {"qps": 2.0, "burst": 1}},
    )

    async def run_calls():
        await plugin.pre_llm_call([], model="fast-model")
        await plugin.pre_llm_call([], model="fast-model")
        await plugin.pre_llm_call([], model="default-model")
        await plugin.pre_llm_call([], model="default-model")

    asyncio.run(run_calls())

    assert clock.sleeps == [0.5, 1.0]


def test_constructor_accepts_options_dict_and_flattened_kwargs(monkeypatch):
    module, _logger = _install_kohaku_stubs(monkeypatch)

    options_plugin = module.QpsThrottlePlugin(options={"default_qps": 2.0})
    flattened_plugin = module.QpsThrottlePlugin(default_qps=2.0)

    assert options_plugin.default_settings.qps == 2.0
    assert flattened_plugin.default_settings.qps == 2.0


def test_option_schema_and_nested_validation(monkeypatch):
    module, _logger = _install_kohaku_stubs(monkeypatch)

    schema = module.QpsThrottlePlugin.option_schema()
    assert schema["per_model"]["type"] == "dict"

    plugin = module.QpsThrottlePlugin(
        options={"per_model": {"gpt-4.1": {"qps": 0.5, "burst": 1}}}
    )
    assert plugin.per_model_settings["gpt-4.1"].qps == 0.5

    with pytest.raises(ValueError):
        module.QpsThrottlePlugin(options={"per_model": {"bad": {"qps": 0}}})

    with pytest.raises(ValueError):
        module.QpsThrottlePlugin(options={"default_qps": 0})


def test_manifest_registers_importable_plugin(monkeypatch):
    module, _logger = _install_kohaku_stubs(monkeypatch)

    manifest = (REPO_ROOT / "kohaku.yaml").read_text(encoding="utf-8")
    assert "name: qps_throttle" in manifest
    assert "module: kt_guard_plugin.plugins.qps_throttle" in manifest
    assert "class: QpsThrottlePlugin" in manifest
    assert getattr(module, "QpsThrottlePlugin")().name == "qps_throttle"
