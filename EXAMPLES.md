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
  - name: qps_throttle              # Smooth model requests before provider calls
    options:
      default_qps: 1.0
      default_burst: 1
  - name: message_role_guard        # Ensure ONE system message at position 0
    options:
      fix: true
  - name: compact.auto              # Auto-compact on token overflow
```

---

## Example 4: QPS throttle with per-model limits

```yaml
plugins:
  - name: qps_throttle
    options:
      default_qps: 1.0
      default_burst: 1
      per_model:
        gpt-4.1:
          qps: 0.5
          burst: 1
        gpt-4.1-mini:
          qps: 2.0
          burst: 2
      log_wait_threshold_seconds: 0.5
      max_wait_seconds: 0.0
```

**Behavior:**
- Calls to `gpt-4.1` are spaced to one request every 2 seconds.
- Calls to `gpt-4.1-mini` may burst up to 2 requests, then refill at 2 QPS.
- Calls to other models use `default_qps: 1.0` and `default_burst: 1`.
- All sessions and sub-agents in the same Python process share the limiter for the same exact model string.

This plugin is preventive backpressure. It waits before the provider call to reduce HTTP 429s, but it does not catch or retry a 429 after the provider has already raised.

---

## Example 5: System message not at position 0

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

## Example 6: Multiple system messages (NEW!)

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

## Example 7: Both issues (system not first + multiple)

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

## Example 8: Warning-only mode (fix=false)

Same input as Example 6, but with `fix: false`:

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
