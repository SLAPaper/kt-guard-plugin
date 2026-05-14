# Examples: Using kt-guard-plugin

## Example 1: Minimal setup (use defaults)

In your creature's `config.yaml`:

```yaml
plugins:
  - name: message_role_guard
```

This enables the plugin with default options:
- `fix: true` — automatically corrects message ordering
- `priority: 1_000_000` — runs very early in `pre_llm_call`

---

## Example 2: With custom options

```yaml
plugins:
  - name: message_role_guard
    options:
      fix: false  # Only log warnings, don't auto-fix
```

Use this if you want to:
- Monitor for message ordering issues without fixing them
- Debug why your messages are being reordered

---

## Example 3: Multiple plugins together

```yaml
plugins:
  - name: budget                    # Track token usage
  - name: sandbox                   # Restrict filesystem access
  - name: message_role_guard        # Ensure ONE system message at position 0
    options:
      fix: true
  - name: compact.auto              # Auto-compact on token overflow
```

---

## Example 4: System message not at position 0

**Input:**
```python
messages = [
    {"role": "user", "content": "Hello"},
    {"role": "system", "content": "You are helpful"},
    {"role": "assistant", "content": "Hi!"}
]
```

**After plugin (fix=true):**
```python
messages = [
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"}
]
```

---

## Example 5: Multiple system messages (NEW!)

**Input:**
```python
messages = [
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "Hello"},
    {"role": "system", "content": "Always be concise"},
    {"role": "assistant", "content": "Hi!"}
]
```

**After plugin (fix=true):**
```python
messages = [
    {"role": "system", "content": "You are helpful\n\nAlways be concise"},
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"}
]
```

**Key behavior:**
- ✅ Multiple system messages are merged with `\n\n` separator
- ✅ Only ONE system message remains
- ✅ System message is placed at position 0

---

## Example 6: Both issues (system not first + multiple)

**Input:**
```python
messages = [
    {"role": "user", "content": "Hello"},
    {"role": "system", "content": "First system"},
    {"role": "system", "content": "Second system"},
    {"role": "assistant", "content": "Hi!"}
]
```

**After plugin (fix=true):**
```python
messages = [
    {"role": "system", "content": "First system\n\nSecond system"},
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"}
]
```

**Result:** Both issues fixed in one pass.

---

## Example 7: Warning-only mode (fix=false)

Same input as Example 5, but with `fix: false`:

```yaml
plugins:
  - name: message_role_guard
    options:
      fix: false
```

**Behavior:**
- ✅ Log warning about invalid system messages
- ❌ Do NOT modify the conversation
- Useful for: Debugging without affecting behavior

---

## Detection Logic

The plugin checks **before each LLM call**:

1. Are there multiple system messages?
2. Is the first system message NOT at position 0?

If either is true → trigger correction (if fix=true)

```
if (system_message_not_at_position_0) OR (multiple_system_messages):
    if (fix_enabled):
        → Merge all system messages + reorder
    else:
        → Just log warning
else:
    → No changes needed
```

---

## Log Output Example

When plugin detects issues:

```
[HH:MM:SS] [plugin.manager] [WARNING]
pre_llm_call message role guard detected invalid system placement
  agent=my-creature
  model=gpt-4-turbo
  system_positions=[0, 2]       ← Two system messages at positions 0 and 2
  system_count=2                ← System message count
  message_count=4
  roles=['system', 'user', 'system', 'assistant']
```
