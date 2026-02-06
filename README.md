# LLM Adapter for Claw

💪 **AI Context Firewall** - 为 Clawdbot 提供轻量级上下文优化与语义记忆外挂

[![CI/CD](https://github.com/aki66938/llm_adapter_claw/actions/workflows/ci.yml/badge.svg)](https://github.com/aki66938/llm_adapter_claw/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 项目概述

LLM Adapter for Claw（代号：`llm_adapter_claw`）是一个基于**反向代理模式**的上下文优化适配器，在 Clawdbot 与 LLM 提供商之间充当**AI Context Firewall**，实现：

- 🎯 **Token 节约 40-70%** - 精细化上下文管理，减少冗余传输
- 🧠 **语义级记忆检索** - 向量数据库替代文件系统，实现认知记忆
- 🔧 **零侵入集成** - 不修改 Clawdbot 源码，仅通过配置指向代理
- ⚡ **动态上下文组装** - 意图驱动，仅加载当前任务必需信息

---

## 核心特性

| 特性 | 描述 | 状态 |
|------|------|------|
| **透明代理** | 完全兼容 OpenAI/Anthropic API 格式 | 🚧 WIP |
| **Prompt 剪枝** | System Prompt 清洗 + 历史记录智能压缩 | 🚧 WIP |
| **语义记忆** | SQLite-VSS 本地向量库，隐私优先 | 🚧 WIP |
| **意图分类** | 闲聊/代码/检索/工具调用场景识别 | 🚧 WIP |
| **熔断降级** | VectorDB 故障自动回退直连模式 | 🚧 WIP |
| **可观测性** | Prometheus 指标 + 结构化日志 | 🚧 WIP |

---

## 快速开始

### 安装 (使用 uv - 推荐)

```bash
# 克隆仓库
git clone git@github.com:aki66938/llm_adapter_claw.git
cd llm_adapter_claw

# 安装 uv (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 启动服务 (自动处理依赖)
uv run --no-dev python -m llm_adapter_claw
```

### 安装 (使用 pip)

```bash
pip install -e ".[dev]"
python -m llm_adapter_claw

# 或使用 Docker Compose
docker-compose up -d
```

### 配置 Clawdbot

编辑 Clawdbot 配置文件，将 API 端点指向 Adapter：

```json
{
  "llm_provider": "openai",
  "base_url": "http://localhost:8080/v1",
  "api_key": "sk-dummy"
}
```

### 启动服务

```bash
# 使用 uv (推荐 - 无需手动安装依赖)
uv run --no-dev python -m llm_adapter_claw

# 或使用 pip 安装后的命令
llm-adapter-claw
# 或
python -m llm_adapter_claw
```

---

## 架构设计

```
┌─────────────┐     ┌─────────────────────────────────────────────┐     ┌─────────────┐
│  Clawdbot   │────▶│           LLM Adapter (Proxy)               │────▶│     LLM     │
│   (Client)  │◀────│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │◀────│  (Provider) │
└─────────────┘     │  │ Sanitizer│▶│Classifier│▶│Assembler │       │     └─────────────┘
                    │  └─────────┘ └─────────┘ └─────────┘       │
                    │         ▲              │                    │
                    │         └──────────────┘                    │
                    │              Memory Store (SQLite-VSS)       │
                    └─────────────────────────────────────────────┘
```

### 处理管道

1. **Sanitizer** - 结构验证，标记敏感消息（Tool Calls、Attachments）
2. **Intent Classifier** - 意图识别（闲聊/代码/检索/工具调用）
3. **Context Assembler** - 动态加载 System Prompt 模块，语义检索记忆
4. **Validator** - Token 计数对比，结构完整性检查

---

## 开发

### 项目结构

```
llm_adapter_claw/
├── src/llm_adapter_claw/    # 核心源码
│   ├── core/                # 代理核心、管道、分类器
│   ├── memory/              # 向量存储、检索、嵌入
│   ├── models/              # Pydantic 模型
│   └── utils/               # 工具函数
├── tests/                   # 测试套件
├── docs/                    # 设计文档
├── scripts/                 # 辅助脚本
└── .github/workflows/       # CI/CD 配置
```

### 运行测试

```bash
pytest
# 带覆盖率
pytest --cov=src/llm_adapter_claw --cov-report=html
```

### 代码规范

```bash
# 格式化
black src tests

# 检查
ruff check src tests
mypy src
```

---

## API 端点

### 核心端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/v1/chat/completions` | POST | OpenAI 兼容的聊天补全接口 |
| `/health` | GET | 健康检查 |
| `/ready` | GET | 就绪检查 |

### 流量分析与度量

| 端点 | 方法 | 描述 |
|------|------|------|
| `/metrics` | GET | Prometheus 格式指标 |
| `/traffic/stats` | GET | 流量统计概览 (Token 节省、优化率等) |
| `/traffic/recent` | GET | 最近请求明细 (默认10条) |

**流量统计示例：**
```bash
# 查看总体统计
curl http://localhost:8080/traffic/stats
# {"total_requests": 42, "total_tokens_saved": 12500, "avg_savings_pct": 35.2, ...}

# 查看最近请求
curl http://localhost:8080/traffic/recent?n=5
# {"recent_requests": [...]}

# Prometheus 指标
curl http://localhost:8080/metrics
```

### 多LLM提供商配置

支持 OpenAI、Kimi、Qwen、Claude、GLM、SiliconFlow、DeepSeek 等。

**查看可用模板：**
```bash
curl http://localhost:8080/config/providers/templates
```

**从模板创建提供商：**
```bash
curl -X POST http://localhost:8080/config/providers/from-template \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "kimi",
    "provider_id": "my-kimi",
    "api_key": "sk-xxx"
  }'
```

**自定义提供商：**
```bash
curl -X POST http://localhost:8080/config/providers \
  -H "Content-Type: application/json" \
  -d '{
    "id": "custom-openai",
    "name": "Custom OpenAI",
    "base_url": "https://api.custom.com/v1",
    "api_key": "sk-xxx",
    "default_model": "gpt-4"
  }'
```

**使用提供商前缀指定模型：**
```json
{
  "model": "kimi:moonshot-v1-8k",
  "messages": [...]
}
```

**配置管理端点：**

| 端点 | 方法 | 描述 |
|------|------|------|
| `/config/providers/templates` | GET | 列出可用模板 |
| `/config/providers` | GET | 列出所有提供商 |
| `/config/providers` | POST | 创建自定义提供商 |
| `/config/providers/from-template` | POST | 从模板创建 |
| `/config/providers/{id}` | GET | 获取提供商详情 |
| `/config/providers/{id}` | PATCH | 更新提供商 |
| `/config/providers/{id}` | DELETE | 删除提供商 |
| `/config/providers/{id}/default` | POST | 设为默认 |
| `/config/providers/default` | GET | 获取默认提供商 |

### 熔断器与降级

**熔断器状态监控：**
```bash
curl http://localhost:8080/config/circuit-breakers
# {"circuit_breakers": [{"name": "llm_upstream", "state": "closed", ...}]}

# 查看具体熔断器
curl http://localhost:8080/config/circuit-breakers/llm_upstream

# 手动重置熔断器
curl -X POST http://localhost:8080/config/circuit-breakers/llm_upstream/reset

# 重置所有熔断器
curl -X POST http://localhost:8080/config/circuit-breakers/reset-all
```

**熔断器配置（环境变量）：**
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CIRCUIT_BREAKER_THRESHOLD` | 5 | 触发熔断的连续失败次数 |
| `CIRCUIT_BREAKER_TIMEOUT` | 60 | 熔断后恢复等待时间（秒） |

**熔断器工作原理：**
- `CLOSED` - 正常状态，请求正常通过
- `OPEN` - 熔断状态，请求直接拒绝（防止雪崩）
- `HALF_OPEN` - 测试状态，少量请求试探恢复

---

## 文档

- [架构设计](docs/architecture/ARCHITECTURE.md) - 详细架构说明
- [部署指南](docs/deployment/DEPLOYMENT.md) - 生产环境部署
- [配置参考](docs/configuration/CONFIGURATION.md) - 完整配置选项
- [设计文档](docs/) - 原始设计文档

---

## 版本更新记录

| 版本 | 日期 | 变更内容 | 提交者 |
|------|------|----------|--------|
| 0.5.0 | 2026-02-06 | 熔断降级机制：Circuit Breaker、Graceful Degradation、API状态管理 | 阿凯 💪 |
| 0.4.0 | 2026-02-06 | 多LLM提供商支持：OpenAI/Kimi/Qwen/Claude/GLM/硅基流动等，API动态配置 | 阿凯 💪 |
| 0.3.0 | 2026-02-06 | 流量分析与度量：Token 节省统计、Prometheus 指标、uv 启动入口 | 阿凯 💪 |
| 0.2.0 | 2026-02-05 | 核心处理管道：意图分类、上下文组装、请求优化、流式响应| 阿凯 💪 |
| 0.1.0 | 2026-02-05 | 文档补充：添加分析报告、设计方案、风险评估三篇核心设计文档 | 阿凯 💪 |
| 0.1.0 | 2026-02-05 | 项目初始化：基础架构搭建、CI/CD 配置、项目结构创建 | 阿凯 💪 |

---

## 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **HTTP 客户端**: httpx
- **Vector DB**: SQLite-VSS (默认本地)
- **嵌入模型**: sentence-transformers
- **配置管理**: Pydantic Settings
- **监控**: Prometheus Client
- **日志**: structlog

---

## 贡献

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

---

## 许可证

[MIT License](LICENSE)

---

💪 *Built with precision. Optimized for efficiency.*
