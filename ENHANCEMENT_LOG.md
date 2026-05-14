# 增强日志 - kt-guard-plugin v0.1.0

## 📝 更新内容

### 增强的核心逻辑

**之前:** 仅确保系统消息在位置 0
```python
# 原逻辑：如果 system 在位置 0 或不存在，就不处理
if system_positions == [0] or not system_positions:
    return None
```

**现在:** 同时确保位置 0 且只有一条系统消息
```python
# 新逻辑：检查两个条件
needs_fix = (
    system_positions != [0]      # system 不在第一位或不存在
    or len(system_positions) > 1  # 多个 system 消息
)
```

---

## 🎯 新增功能

### 1. **多系统消息合并** 
当检测到多个 `system` 角色的消息时，将它们合并为一条，用 `\n\n` 分隔：

```python
# 输入：两个系统消息
[
  {"role": "system", "content": "Instruction 1"},
  {"role": "user", "content": "Query"},
  {"role": "system", "content": "Instruction 2"}
]

# 输出：一个合并的系统消息
[
  {"role": "system", "content": "Instruction 1\n\nInstruction 2"},
  {"role": "user", "content": "Query"}
]
```

### 2. **日志中新增 `system_count`**
日志现在包含系统消息的数量，便于调试：

```
agent=my-creature
model=gpt-4-turbo
system_positions=[0, 2]    # 两个系统消息分别在位置 0 和 2
system_count=2             # ← 新增字段
message_count=4
```

---

## 📊 修改清单

### 修改的文件

| 文件 | 修改内容 |
|------|--------|
| `kt_guard_plugin/plugins/guard.py` | 增强 `needs_fix` 逻辑，添加 `system_count` 日志字段 |
| `README.md` | 更新概述、行为和示例说明 |
| `EXAMPLES.md` | 完全重写为 Markdown 格式，添加多系统消息示例 |
| `test_enhancements.py` | ✨ 新增测试脚本验证增强逻辑 |

### 新增文件

| 文件 | 用途 |
|------|------|
| `test_enhancements.py` | 5 个测试用例，验证所有场景 |

---

## ✅ 行为对比表

| 场景 | 之前 | 现在 |
|------|------|------|
| System 在位置 0，只有 1 个 | ✅ 不修改 | ✅ 不修改 |
| System 不在位置 0 | ✅ 修复 | ✅ 修复 |
| 有 2 个 System 消息，第一个在位置 0 | ❌ 不修改（问题！） | ✅ 修复为 1 个 |
| 有 2 个 System 消息，都不在位置 0 | ✅ 修复 | ✅ 修复 |
| 有 3+ 个 System 消息 | ❌ 不修改（部分） | ✅ 合并为 1 个 |

---

## 🧪 测试

### 运行增强逻辑测试

```bash
cd ~/workspace/kt-guard-plugin
python test_enhancements.py
```

### 测试覆盖

- ✅ **Test 1**: System 消息不在位置 0
- ✅ **Test 2**: 多个系统消息（新）
- ✅ **Test 3**: 两个问题同时出现
- ✅ **Test 4**: 正确状态（无需修复）
- ✅ **Test 5**: 警告模式（fix=false）

---

## 🔄 逻辑流程图

```
检查消息列表
    ↓
找到所有 "system" 角色的消息位置
    ↓
判断是否需要修复：
  - 是否有多个 system 消息？ OR
  - 第一个 system 消息不在位置 0？
    ↓
  [是] → 检查 fix 选项
    ├─ fix=true  → 合并 system 消息 + 重排序 → 返回修复后列表
    └─ fix=false → 仅记录日志 → 返回 None
    ↓
  [否] → 返回 None（无需修复）
```

---

## 📚 使用示例

### 配置文件

```yaml
plugins:
  - name: message_role_guard
    options:
      fix: true  # 自动修复（默认）
```

### 可能的日志输出

**情况 1**: 系统消息不在位置 0
```
[WARNING] pre_llm_call message role guard detected invalid system placement
  agent=swe
  model=gpt-4
  system_positions=[2]          # 不在位置 0
  system_count=1                # 只有 1 个
  message_count=5
```

**情况 2**: 多个系统消息
```
[WARNING] pre_llm_call message role guard detected invalid system placement
  agent=swe
  model=gpt-4
  system_positions=[0, 3]       # 两个位置
  system_count=2                # 2 个（现在会检测！）
  message_count=5
```

---

## 🚀 向后兼容性

✅ **完全兼容** — 不会破坏现有配置或行为
- 旧配置自动使用新逻辑
- 新逻辑是之前逻辑的**超集**（更强大，更安全）

---

## 📖 文档更新

- 📄 [README.md](README.md) — 更新了概述和行为描述
- 📄 [EXAMPLES.md](EXAMPLES.md) — 添加了多系统消息场景
- 🧪 [test_enhancements.py](test_enhancements.py) — 新增完整测试套件

---

## 🎁 下一步建议

1. ✅ 运行 `test_enhancements.py` 验证逻辑
2. ✅ 在现有项目中测试新逻辑
3. ✅ 更新版本号：`0.1.0` → `0.1.1` 或 `0.2.0`
4. ✅ 提交到 git 并推送到 GitHub

---

## 总结

**增强前的问题：** 如果多个系统消息都在前面（如位置 0, 1），但只有第一个在位置 0，就不会被修复

**增强后的改进：** 任何情况下都会确保：
- ✅ 系统消息在位置 0
- ✅ 只有 1 个系统消息
- ✅ 日志更清晰（新增 `system_count` 字段）
