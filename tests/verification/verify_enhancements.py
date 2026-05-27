#!/usr/bin/env python3
"""
Test cases for the enhanced MessageRoleGuardPlugin logic.
Run this script to verify that the plugin correctly handles:
1. System message not at position 0
2. Multiple system messages
3. Both issues combined
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kt_guard_plugin.plugins.guard import MessageRoleGuardPlugin


async def test_case_1():
    """Test: System message not at position 0"""
    print("\n" + "=" * 60)
    print("TEST 1: System message not at position 0")
    print("=" * 60)

    plugin = MessageRoleGuardPlugin(options={"fix": True})
    plugin.agent_name = "test-agent"

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "system", "content": "You are helpful"},
        {"role": "assistant", "content": "Hi!"},
    ]

    print(f"Input: {len(messages)} messages")
    print(f"  Roles: {[m['role'] for m in messages]}")

    result = await plugin.pre_llm_call(messages, model="gpt-4")

    if result:
        print(f"\nOutput: {len(result)} messages (MODIFIED)")
        print(f"  Roles: {[m['role'] for m in result]}")
        assert result[0]["role"] == "system", "First message should be system"
        print("✅ PASS: System message moved to position 0")
    else:
        print("❌ FAIL: Should have returned modified messages")
        return False

    return True


async def test_case_2():
    """Test: Multiple system messages"""
    print("\n" + "=" * 60)
    print("TEST 2: Multiple system messages")
    print("=" * 60)

    plugin = MessageRoleGuardPlugin(options={"fix": True})
    plugin.agent_name = "test-agent"

    messages = [
        {"role": "system", "content": "First instruction"},
        {"role": "user", "content": "Hello"},
        {"role": "system", "content": "Second instruction"},
        {"role": "assistant", "content": "Hi!"},
    ]

    print(f"Input: {len(messages)} messages")
    print(f"  Roles: {[m['role'] for m in messages]}")
    print("  System messages: 2 (at positions 0, 2)")

    result = await plugin.pre_llm_call(messages, model="gpt-4")

    if result:
        print(f"\nOutput: {len(result)} messages (MODIFIED)")
        print(f"  Roles: {[m['role'] for m in result]}")

        system_count = sum(1 for m in result if m["role"] == "system")
        assert (
            system_count == 1
        ), f"Should have exactly 1 system message, got {system_count}"
        assert result[0]["role"] == "system", "First message should be system"

        # Check if contents are merged
        if "\n\n" in result[0]["content"]:
            print("\n✅ PASS: Multiple system messages merged with \\n\\n")
            print(f"   Merged content: {result[0]['content']}")
        else:
            print("✅ PASS: Only one system message remains")
            print(f"   Content: {result[0]['content']}")
    else:
        print("❌ FAIL: Should have returned modified messages")
        return False

    return True


async def test_case_3():
    """Test: Both issues combined"""
    print("\n" + "=" * 60)
    print("TEST 3: Both issues - system not first + multiple")
    print("=" * 60)

    plugin = MessageRoleGuardPlugin(options={"fix": True})
    plugin.agent_name = "test-agent"

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "system", "content": "First instruction"},
        {"role": "system", "content": "Second instruction"},
        {"role": "assistant", "content": "Hi!"},
    ]

    print(f"Input: {len(messages)} messages")
    print(f"  Roles: {[m['role'] for m in messages]}")
    print("  System messages: 2 (at positions 1, 2) - NOT at position 0")

    result = await plugin.pre_llm_call(messages, model="gpt-4")

    if result:
        print(f"\nOutput: {len(result)} messages (MODIFIED)")
        print(f"  Roles: {[m['role'] for m in result]}")

        system_count = sum(1 for m in result if m["role"] == "system")
        assert (
            system_count == 1
        ), f"Should have exactly 1 system message, got {system_count}"
        assert result[0]["role"] == "system", "First message should be system"

        print("\n✅ PASS: Both issues fixed in one pass")
        print("   - System message moved to position 0")
        print("   - Multiple messages consolidated to 1")
    else:
        print("❌ FAIL: Should have returned modified messages")
        return False

    return True


async def test_case_4():
    """Test: System message already correct (no fix needed)"""
    print("\n" + "=" * 60)
    print("TEST 4: Correct state - system at 0, only one")
    print("=" * 60)

    plugin = MessageRoleGuardPlugin(options={"fix": True})
    plugin.agent_name = "test-agent"

    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]

    print(f"Input: {len(messages)} messages")
    print(f"  Roles: {[m['role'] for m in messages]}")
    print("  System: 1 at position 0 ✓")

    result = await plugin.pre_llm_call(messages, model="gpt-4")

    if result is None:
        print("\nOutput: None (NO MODIFICATION)")
        print("✅ PASS: Correctly detected no fix needed")
    else:
        print("❌ FAIL: Should return None for correct messages")
        return False

    return True


async def test_case_5():
    """Test: Warning mode (fix=false)"""
    print("\n" + "=" * 60)
    print("TEST 5: Warning mode - fix=false")
    print("=" * 60)

    plugin = MessageRoleGuardPlugin(options={"fix": False})
    plugin.agent_name = "test-agent"

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "system", "content": "First instruction"},
        {"role": "system", "content": "Second instruction"},
    ]

    print(f"Input: {len(messages)} messages")
    print(f"  Roles: {[m['role'] for m in messages]}")
    print("  fix=false (warning only)")

    result = await plugin.pre_llm_call(messages, model="gpt-4")

    if result is None:
        print("\nOutput: None (NO MODIFICATION)")
        print("✅ PASS: Warning mode does not fix, only logs")
    else:
        print("❌ FAIL: Should return None in warning mode")
        return False

    return True


async def main():
    print("\n" + "🧪 Running MessageRoleGuardPlugin Enhancement Tests")

    tests = [
        test_case_1,
        test_case_2,
        test_case_3,
        test_case_4,
        test_case_5,
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            import traceback

            traceback.print_exc()
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
