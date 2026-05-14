"""
Example: Using kt-guard-plugin in a KohakuTerrarium creature

This shows how to integrate the message_role_guard plugin in your creature config.
"""

# Example 1: Minimal setup (use defaults)
# ========================================
# In your creature's config.yaml:
#
# plugins:
#   - name: message_role_guard
#
# This enables the plugin with default options:
#   - fix: true (automatically corrects message ordering)
#   - priority: 1_000_000 (runs very early in pre_llm_call)


# Example 2: With custom options
# ===============================
# In your creature's config.yaml:
#
# plugins:
#   - name: message_role_guard
#     options:
#       fix: false  # Only log warnings, don't auto-fix
#
# This is useful if you want to:
#   - Monitor for message ordering issues without fixing them
#   - Debug why your messages are being reordered


# Example 3: Multiple plugins together
# =====================================
# In your creature's config.yaml:
#
# plugins:
#   - name: budget                    # Track token usage
#   - name: sandbox                   # Restrict filesystem access
#   - name: message_role_guard        # Ensure system message at position 0
#     options:
#       fix: true
#   - name: compact.auto              # Auto-compact on token overflow
#
# Plugins run in the order specified, so message_role_guard runs
# after budget (tracking) but before compact (which needs clean messages).


# Example 4: Programmatic setup
# ==============================

import asyncio
from kohakuterrarium.core.agent import Agent
from kt_guard_plugin.plugins.guard import MessageRoleGuardPlugin


async def example_with_plugin():
    """Load an agent and use the plugin directly."""
    
    # Load your creature
    agent = Agent.from_path("path/to/your/creature")
    
    # The plugin is loaded automatically from config if specified there.
    # Or, manually register:
    plugin = MessageRoleGuardPlugin(options={"fix": True})
    # (In practice, the PluginManager handles this during agent initialization)
    
    await agent.start()
    await agent.inject_input("Your query here")
    await agent.stop()


# Example 5: Monitoring output
# =============================
# When the plugin detects invalid message ordering, it logs a warning:
#
# [HH:MM:SS] [kohakuterrarium.modules.plugin.manager] [WARNING]
# pre_llm_call message role guard detected invalid system placement
#   agent=my-agent
#   model=gpt-4-turbo
#   system_positions=[5, 12]  <- System messages are NOT at position 0!
#   roles=['system', 'user', 'assistant', ..., 'system', ...]
#   message_count=25
#
# If fix=true, the plugin will reorder and the messages will be corrected.
# If fix=false, the messages stay as-is (but logged for debugging).
