---
name: switch-models
description: |
  TRIGGER whenever the user asks to 切换模型/换模型/改模型, says switch model/change model, asks to use a specific model (for example `glm-5` or `gpt-5.3-codex`), or asks to view available switchable models. Prefer using this skill even when model switching is only implied.
---

# Switch Models

切换 Claude 使用的模型，并把结果写入用户配置。

## 推荐入口（本地命令优先）

日常人工切换优先使用全局命令：

```bash
switch-claude-model [model-input]
```

行为：

- 启动后展示可用模型（标记当前模型）
- `model-input` 唯一命中时直接切换
- 无输入 / 歧义 / 无效时，终端内按编号选择（支持取消）
- 写入 `~/.claude/settings.json` 的整个 `env`
- 来源为 `~/.claude/settings.model.<selected-model>.json` 的 `env`

## skill 路径定位（兼容层 / 回退）

本 skill 保留原脚本流程用于兼容与回退，不中断现有调用链：

- 一体化：`python3 scripts/switch_model.py switch [model-input]`
- 列表：`python3 scripts/switch_model.py list`
- 直接设置：`python3 scripts/switch_model.py set <model-input>`

## 兼容脚本返回语义（保持不变）

`switch_model.py` 继续保持以下状态与错误码语义：

- 状态：`updated` / `unchanged` / `needs_selection`
- 错误码：`NO_MODELS` / `INVALID_*` / `AMBIGUOUS_MODEL` / `MODEL_SETTINGS_NOT_FOUND`

## 安装全局命令

```bash
python3 scripts/install_switch_claude_model.py
```

默认安装到 `~/.local/bin/switch-claude-model`。
若 PATH 未包含 `~/.local/bin`，安装脚本会打印 shell 配置提示（不会自动修改 rc 文件）。

## 错误处理约定

- `NO_MODELS`：先创建 `settings.model.<model-name>.json`
- `INVALID_SETTINGS_JSON`：先修复 `~/.claude/settings.json`
- `INVALID_MODEL_SETTINGS_JSON`：先修复目标模型配置文件
- `INVALID_MODEL_ENV`：目标模型配置的 `env` 必须是 JSON 对象

## 切换后提示

成功后应明确提示：

- 最终模型
- 更新文件：`~/.claude/settings.json`
- 更新字段：`env`（整对象替换）
- 替换来源：`~/.claude/settings.model.<selected-model>.json`
- 手动重启 Claude 会话
