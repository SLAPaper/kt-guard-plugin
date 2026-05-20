# kt-guard-plugin

Debugging and guard plugins for KohakuTerrarium LLM conversations.

## Overview

This package provides two plugins:

- `message_role_guard`: detects and optionally repairs invalid `system` message ordering.
- `message_context_logger`: writes full LLM message context to rotating JSONL logs for debugging.

### Message Role Guard

The `MessageRoleGuardPlugin` detects and corrects invalid message ordering in OpenAI-compatible API calls. Many LLM APIs require system messages to be the first element in the conversation, and there should be only ONE system message. During complex multi-turn interactions with sub-agents and tool execution, system messages can accidentally:
- Get placed in the middle of the conversation (not at position 0)
- Be duplicated (multiple system messages present)

This plugin:
- Detects when system messages are not at position 0, or when there are multiple system messages
- Logs warnings with diagnostic information
- Automatically consolidates all system messages into ONE and repositions it at the start (optional)
- Prevents API errors like "System message must be first" and "Multiple system messages"

### Message Context Logger

The `MessageContextLoggerPlugin` records complete runtime LLM context as structured JSONL. It is intended for debugging agent behavior, such as confirming whether:

- System prompts were assembled as expected
- Context files were loaded into the final message list
- Skills or other prompt contributions appear in the outgoing context
- Native tools passed to the provider match expectations
- LLM responses and usage were associated with the expected request

The logger is observation-only. It does not rewrite messages, responses, tools, or control flow.

## Installation

### Via kt CLI (KohakuTerrarium package manager)
```bash
kt install https://github.com/SLAPaper/kt-guard-plugin.git
```

### From Local Source (development)
```bash
git clone https://github.com/SLAPaper/kt-guard-plugin.git
cd kt-guard-plugin
kt install -e .
```

### Programatic Use
```bash
git clone https://github.com/SLAPaper/kt-guard-plugin.git
cd kt-guard-plugin
pip install -e .
```

## Usage

### In a Creature Config

Add to your `config.yaml`:

```yaml
plugins:
  - name: message_role_guard
    options:
      fix: true        # Whether to auto-fix message ordering (default: true)
```

Debug full LLM context:

```yaml
plugins:
  - name: message_context_logger
    options:
      log_on_load: true          # Record plugin load context (default: true)
      log_pre_llm_call: true     # Record full messages/tools before LLM calls (default: true)
      log_post_llm_call: true    # Record response/usage after LLM calls (default: true)
      max_bytes: 10485760        # Rotate after 10 MiB (default)
      backup_count: 5            # Keep 5 rotated backups (default)
```

### Programmatic Usage

```python
from kohakuterrarium.core.agent import Agent
from kt_guard_plugin.plugins.guard import MessageRoleGuardPlugin
from kt_guard_plugin.plugins.message_context_logger import MessageContextLoggerPlugin

# Plugin is automatically loaded from config, or manually:
agent = Agent.from_path("path/to/creature")
# Plugin hooks are invoked before LLM calls via PluginContext
```

## Options

- **`fix`** (boolean, default: `true`)
  - If `true`: Automatically consolidates system messages and moves them to position 0
  - If `false`: Only logs warnings, does not modify the conversation

### `message_context_logger`

- **`log_on_load`** (boolean, default: `true`)
  - If `true`: Writes a `plugin_loaded` event with agent/session/model/working directory and plugin options.
- **`log_pre_llm_call`** (boolean, default: `true`)
  - If `true`: Writes a `pre_llm_call` event with full `messages`, `tools`, roles, system message positions, model, and hook kwargs.
- **`log_post_llm_call`** (boolean, default: `true`)
  - If `true`: Writes a `post_llm_call` event with full response, usage, message summary, roles, system message positions, model, and hook kwargs.
- **`max_bytes`** (integer, default: `10485760`)
  - Maximum JSONL file size before rotation.
- **`backup_count`** (integer, default: `5`)
  - Number of rotated JSONL backups to retain.

## Behavior

### Detection
The plugin runs in the `pre_llm_call` hook and checks if:
1. Multiple system messages exist in the conversation, OR
2. System messages exist but are not at position 0

### Logging
When invalid state is detected, the plugin logs a warning with:
- Agent name
- Model being called
- Position(s) of system messages
- **Number of system messages** (NEW!)
- First 40 roles in the message sequence
- Total message count

### Debug Context Logs

`message_context_logger` writes JSONL files into the same user log directory used by KohakuTerrarium logging: `config_dir() / "logs"` via `kohakuterrarium.utils.logging._default_log_dir()`.

Filenames follow the framework's timestamp, pid, and working-directory hash style from `_make_log_filename()`, then add a short session hash when `session_id` is available, with a `.message-context.jsonl` suffix:

```text
YYYY-MM-DD_HHMMSS_pid<N>_<pwdhash>_session<sessionhash>.message-context.jsonl
```

Each line is one JSON event. The plugin uses `RotatingFileHandler` with `max_bytes` and `backup_count` so debug logs do not grow without bound.

Because this is a full-context debug logger, `pre_llm_call` message content and `post_llm_call` responses are written in full by default. `post_llm_call` stores only a message summary to avoid duplicating the full input already captured by `pre_llm_call`; correlate the two events with `call_id` when the full input is needed. Use KohakuTerrarium's plugin enable/disable controls to turn the plugin off entirely, or disable individual phases with `log_on_load`, `log_pre_llm_call`, and `log_post_llm_call`.

`priority = 10_000`, so `pre_llm_call` normally runs after most message-mutating plugins and records a late view of the outgoing request. This is a practical ordering choice, not an absolute finalizer; a plugin with a larger priority can still run after it.

### Auto-Fix (when enabled)
1. Extracts ALL system messages (there might be multiple)
2. Combines them with `\n\n` separator into ONE system message
3. Removes all system messages from their original positions
4. Prepends the consolidated system message to the conversation
5. Returns the corrected message list

**Result:** Guarantees exactly ONE system message at position 0

## Examples

See [EXAMPLES.md](EXAMPLES.md) for detailed scenarios including:

- ✅ System message repositioning (not at position 0)
- ✅ Multiple system message consolidation (NEW!)
- ✅ Both issues combined
- ✅ Warning-only mode for debugging
- ✅ Performance notes

Quick example:

**Before:** Multiple system messages scattered
```python
[
  {"role": "system", "content": "Instruction 1"},
  {"role": "user", "content": "Hello"},
  {"role": "system", "content": "Instruction 2"},
  {"role": "assistant", "content": "Hi!"}
]
```

**After plugin:** Single system message at position 0
```python
[
  {"role": "system", "content": "Instruction 1\n\nInstruction 2"},
  {"role": "user", "content": "Hello"},
  {"role": "assistant", "content": "Hi!"}
]
```

## Development

### Local Setup
```bash
git clone https://github.com/SLAPaper/kt-guard-plugin.git
cd kt-guard-plugin
pip install -e ".[dev]"
```

### Testing
```bash
pytest tests/unit/
```

### File Structure
```
kt-guard-plugin/
├── kohaku.yaml           # Package manifest for KohakuTerrarium
├── pyproject.toml        # Python project metadata
├── README.md             # This file
├── LICENSE               # Apache License 2.0
├── kt_guard_plugin/      # Main package
│   └── plugins/
│       ├── __init__.py
│       └── guard.py      # MessageRoleGuardPlugin implementation
└── tests/
    └── unit/             # (Future) unit tests
```

## License

Apache License 2.0 — see [LICENSE](LICENSE) file.

## Contributing

Contributions are welcome! Please open an issue or PR on GitHub.

## Compatibility

- **KohakuTerrarium**: >=1.4.0
- **Python**: >=3.10
- **OpenAI-compatible LLM APIs**: All

## Troubleshooting

### Plugin not loading
- Verify `kohaku.yaml` is in the package root
- Check that the `kt_guard_plugin` package is installed: `pip list | grep kt-guard`
- Ensure the creature config references `message_role_guard` in plugins

### Warnings but no auto-fix
- Check plugin option: `fix: true` in creature config
- Review logs for why the fix was skipped

### Messages still out of order
- If using a custom output module or complex flow, check that plugins run in the expected lifecycle hook (`pre_llm_call`)
