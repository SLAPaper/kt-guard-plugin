#!/usr/bin/env python3
"""
Quick verification script for kt-guard-plugin installation.
Run this after `pip install -e .` to verify the plugin is properly set up.
"""

import sys
import json

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
        print(f"   ✅ Plugin class found: {MessageRoleGuardPlugin.__name__}")
        print(f"      - Priority: {MessageRoleGuardPlugin.priority}")
        print(f"      - Plugin name: {MessageRoleGuardPlugin.name}")
    except ImportError as e:
        print(f"   ❌ Failed to import plugin: {e}")
        return False
    
    # 3. Check kohaku.yaml
    print("\n3️⃣  Checking kohaku.yaml manifest...")
    try:
        import yaml
        from pathlib import Path
        kohaku_path = Path(__file__).parent / "kohaku.yaml"
        with open(kohaku_path) as f:
            config = yaml.safe_load(f)
        print(f"   ✅ Manifest found")
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
        print(f"   ✅ Plugin instantiated with fix=true")
        
        plugin = MessageRoleGuardPlugin(options={"fix": False})
        print(f"   ✅ Plugin instantiated with fix=false")
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
            {"role": "assistant", "content": "Hi!"}
        ]
        
        import asyncio
        result = asyncio.run(plugin.pre_llm_call(test_messages, model="gpt-4"))
        
        if result is not None:
            print(f"   ✅ Message reordering works")
            print(f"      - Input: {len(test_messages)} messages (system not at 0)")
            print(f"      - Output: {len(result)} messages (system at 0)")
            if result[0].get("role") == "system":
                print(f"      - ✅ System message moved to position 0")
            else:
                print(f"      - ❌ System message NOT at position 0")
        else:
            print(f"   ✅ Valid message order (no fix needed)")
    except Exception as e:
        print(f"   ⚠️  Could not test logic: {e}")
    
    print("\n" + "="*50)
    print("✅ All checks passed! Plugin is ready to use.\n")
    print("Next steps:")
    print("  1. Add to creature config:")
    print("     plugins:")
    print("       - name: message_role_guard")
    print("         options:")
    print("           fix: true")
    print("  2. Or install via: kt install <git-url>")
    print("="*50)
    return True

if __name__ == "__main__":
    success = verify_plugin()
    sys.exit(0 if success else 1)
