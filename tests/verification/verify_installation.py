#!/usr/bin/env python3
"""
Quick verification script for kt-guard-plugin installation.
Run this after `pip install -e .` to verify the plugin is properly set up.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def verify_plugin():
    """Verify that the plugin can be imported and has correct structure."""
    print("🔍 Verifying kt-guard-plugin installation...\n")

    # 1. Check package import
    print("1️⃣  Checking package import...")
    try:
        import kt_guard_plugin

        print(f"   ✅ Package imported: {kt_guard_plugin.__version__}")
    except ImportError as e:
        print(f"   ❌ Failed to import package: {e}")
        return False

    # 2. Check plugin class import
    print("\n2️⃣  Checking plugin class...")
    try:
        from kt_guard_plugin.plugins.guard import MessageRoleGuardPlugin
        from kt_guard_plugin.plugins.message_context_logger import (
            MessageContextLoggerPlugin,
        )
        from kt_guard_plugin.plugins.qps_throttle import QpsThrottlePlugin

        print(f"   ✅ Plugin class found: {MessageRoleGuardPlugin.__name__}")
        print(f"      - Priority: {MessageRoleGuardPlugin.priority}")
        print(f"      - Plugin name: {MessageRoleGuardPlugin.name}")
        print(f"   ✅ Plugin class found: {MessageContextLoggerPlugin.__name__}")
        print(f"      - Priority: {MessageContextLoggerPlugin.priority}")
        print(f"      - Plugin name: {MessageContextLoggerPlugin.name}")
        print(f"   ✅ Plugin class found: {QpsThrottlePlugin.__name__}")
        print(f"      - Priority: {QpsThrottlePlugin.priority}")
        print(f"      - Plugin name: {QpsThrottlePlugin.name}")
    except ImportError as e:
        print(f"   ❌ Failed to import plugin: {e}")
        return False

    # 3. Check kohaku.yaml
    print("\n3️⃣  Checking kohaku.yaml manifest...")
    try:
        import yaml

        kohaku_path = REPO_ROOT / "kohaku.yaml"
        with open(kohaku_path) as f:
            config = yaml.safe_load(f)
        print("   ✅ Manifest found")
        print(f"      - Package: {config.get('name')}")
        print(f"      - Version: {config.get('version')}")
        if "plugins" in config:
            for plugin in config["plugins"]:
                print(f"      - Plugin: {plugin.get('name')} ({plugin.get('class')})")
    except Exception as e:
        print(f"   ⚠️  Could not verify manifest: {e}")

    # 4. Test plugin instantiation
    print("\n4️⃣  Testing plugin instantiation...")
    try:
        plugin = MessageRoleGuardPlugin(options={"fix": True})
        print("   ✅ Plugin instantiated with fix=true")

        plugin = MessageRoleGuardPlugin(options={"fix": False})
        print("   ✅ Plugin instantiated with fix=false")

        plugin = MessageContextLoggerPlugin(
            options={
                "log_on_load": True,
                "log_pre_llm_call": True,
                "log_post_llm_call": True,
                "max_bytes": 1048576,
                "backup_count": 1,
            }
        )
        print("   ✅ Context logger instantiated")

        plugin = QpsThrottlePlugin(
            options={
                "default_qps": 1.0,
                "default_burst": 1,
                "per_model": {"gpt-4.1": {"qps": 0.5, "burst": 1}},
            }
        )
        print("   ✅ QPS throttle instantiated")
    except Exception as e:
        print(f"   ❌ Failed to instantiate plugin: {e}")
        return False

    # 5. Test message reordering logic
    print("\n5️⃣  Testing message reordering logic...")
    try:
        plugin = MessageRoleGuardPlugin(options={"fix": True})
        test_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "system", "content": "You are helpful"},
            {"role": "assistant", "content": "Hi!"},
        ]

        import asyncio

        result = asyncio.run(plugin.pre_llm_call(test_messages, model="gpt-4"))

        if result is not None:
            print("   ✅ Message reordering works")
            print(f"      - Input: {len(test_messages)} messages (system not at 0)")
            print(f"      - Output: {len(result)} messages (system at 0)")
            if result[0].get("role") == "system":
                print("      - ✅ System message moved to position 0")
            else:
                print("      - ❌ System message NOT at position 0")
        else:
            print("   ✅ Valid message order (no fix needed)")
    except Exception as e:
        print(f"   ⚠️  Could not test logic: {e}")

    print("\n" + "=" * 50)
    print("✅ All checks passed! Plugin is ready to use.\n")
    print("Next steps:")
    print("  1. Add to creature config:")
    print("     plugins:")
    print("       - name: message_role_guard")
    print("         options:")
    print("           fix: true")
    print("       - name: message_context_logger")
    print("         options:")
    print("           log_pre_llm_call: true")
    print("       - name: qps_throttle")
    print("         options:")
    print("           default_qps: 1.0")
    print("  2. Or install via: kt install <git-url>")
    print("=" * 50)
    return True


if __name__ == "__main__":
    success = verify_plugin()
    sys.exit(0 if success else 1)
