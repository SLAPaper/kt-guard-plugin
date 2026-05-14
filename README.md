# kt-guard-plugin

A message role guard plugin for KohakuTerrarium that ensures system messages are correctly positioned in LLM conversations.

## Overview

The `MessageRoleGuardPlugin` detects and corrects invalid message ordering in OpenAI-compatible API calls. Many LLM APIs require system messages to be the first element in the conversation, but during complex multi-turn interactions with sub-agents and tool execution, system messages can accidentally get placed in the middle of the conversation.

This plugin:
- Detects when system messages are not at position 0
- Logs warnings with diagnostic information
- Automatically consolidates and repositions system messages (optional)
- Prevents API errors like "System message must be first"

## Installation

### From PyPI (when published)
```bash
pip install kt-guard-plugin
```

### From GitHub (development)
```bash
pip install git+https://github.com/SLAPaper/kt-guard-plugin.git
```

### From Local Source
```bash
git clone https://github.com/SLAPaper/kt-guard-plugin.git
cd kt-guard-plugin
pip install -e .
```

### Via kt CLI (KohakuTerrarium package manager)
```bash
kt install https://github.com/SLAPaper/kt-guard-plugin.git
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

### Programmatic Usage

```python
from kohakuterrarium.core.agent import Agent
from kt_guard_plugin.plugins.guard import MessageRoleGuardPlugin

# Plugin is automatically loaded from config, or manually:
agent = Agent.from_path("path/to/creature")
# Plugin hooks are invoked before LLM calls via PluginContext
```

## Options

- **`fix`** (boolean, default: `true`)
  - If `true`: Automatically consolidates system messages and moves them to position 0
  - If `false`: Only logs warnings, does not modify the conversation

## Behavior

### Detection
The plugin runs in the `pre_llm_call` hook and checks if:
1. System messages exist in the conversation
2. System messages are at position 0 (or no system messages exist)

### Logging
When invalid ordering is detected, the plugin logs a warning with:
- Agent name
- Model being called
- Position(s) of system messages
- First 40 roles in the message sequence
- Total message count

### Auto-Fix (when enabled)
1. Extracts all system messages and combines them with `\n\n`
2. Removes all system messages from their original positions
3. Prepends the combined system message to the conversation
4. Returns the corrected message list

## Examples

### Example 1: Auto-fix enabled (default)

**Input messages:**
```
[
  {"role": "user", "content": "Hello"},
  {"role": "system", "content": "You are helpful"},
  {"role": "assistant", "content": "Hi!"}
]
```

**Output after plugin:**
```
[
  {"role": "system", "content": "You are helpful"},
  {"role": "user", "content": "Hello"},
  {"role": "assistant", "content": "Hi!"}
]
```

### Example 2: Warning only (fix: false)

The plugin logs the warning but returns `None`, leaving the conversation unmodified.

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

- **KohakuTerrarium**: >=0.1.0
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
