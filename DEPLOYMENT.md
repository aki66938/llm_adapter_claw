# 部署指南

本文档详细介绍如何部署 `llm_adapter_claw` 以及对接 OpenClaw。

## 目录

- [环境要求](#环境要求)
- [部署方式](#部署方式)
  - [方式一：使用 uv（推荐）](#方式一使用-uv推荐)
  - [方式二：使用 Docker](#方式二使用-docker)
  - [方式三：使用 pip](#方式三使用-pip)
- [配置说明](#配置说明)
  - [环境变量](#环境变量)
  - [配置文件](#配置文件)
- [启动服务](#启动服务)
- [对接 OpenClaw](#对接-openclaw)
- [验证部署](#验证部署)
- [故障排查](#故障排查)

---

## 环境要求

- **Python**: 3.10 或更高版本
- **操作系统**: Linux, macOS, Windows (WSL2 推荐)
- **内存**: 最低 512MB，推荐 1GB+
- **磁盘**: 100MB+（不含向量数据库）

---

## 部署方式

### 方式一：使用 uv（推荐）

`uv` 是 Astral 开发的极速 Python 包管理器，支持自动依赖管理。

```bash
# 1. 克隆仓库
git clone https://github.com/aki66938/llm_adapter_claw.git
cd llm_adapter_claw

# 2. 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh
# 或
# curl -LsSf https://astral.sh/uv/install.ps1 | powershell

# 3. 配置并启动（必须设置 LLM API 密钥）
# 方式 A：使用 OpenAI（默认）
export LLM_API_KEY=sk-your-openai-key
uv run --no-dev python -m llm_adapter_claw

# 方式 B：使用其他供应商（如 Kimi）
export LLM_BASE_URL=https://api.moonshot.cn/v1
export LLM_API_KEY=sk-your-kimi-key
export LLM_MODEL=moonshot-v1-8k
uv run --no-dev python -m llm_adapter_claw

# 方式 C：通过配置文件启动（推荐多供应商场景）
# 创建 config.json 后启动
export LLM_API_KEY=sk-your-key
uv run --no-dev python -m llm_adapter_claw
```

**注意**：如果不指定 `LLM_BASE_URL`，默认使用 OpenAI（https://api.openai.com/v1）。启动后可通过 API 动态添加其他供应商。

**可选：启用语义记忆（需要额外依赖）**

```bash
uv run --no-dev --extra memory python -m llm_adapter_claw
```

---

### 方式二：使用 Docker

```bash
# 1. 克隆仓库
git clone https://github.com/aki66938/llm_adapter_claw.git
cd llm_adapter_claw

# 2. 构建镜像
docker build -t llm-adapter-claw .

# 3. 运行容器
docker run -d \
  --name llm-adapter \
  -p 8080:8080 \
  -e LLM_BASE_URL=https://api.openai.com/v1 \
  -e LLM_API_KEY=sk-your-key \
  llm-adapter-claw

# 或使用 docker-compose
docker-compose up -d
```

---

### 方式三：使用 pip

```bash
# 1. 克隆仓库
git clone https://github.com/aki66938/llm_adapter_claw.git
cd llm_adapter_claw

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
# venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 启动服务
python -m llm_adapter_claw
```

---

## 配置说明

### 环境变量

| 变量 | 默认值 | 说明 | 必需 |
|------|--------|------|------|
| `LLM_BASE_URL` | `https://api.openai.com/v1` | 上游 LLM API 地址 | 否 |
| `LLM_API_KEY` | - | LLM API 密钥 | 是 |
| `LLM_MODEL` | `gpt-4` | 默认模型 | 否 |
| `HOST` | `0.0.0.0` | 服务监听地址 | 否 |
| `PORT` | `8080` | 服务端口 | 否 |
| `LOG_LEVEL` | `info` | 日志级别 | 否 |
| `OPTIMIZATION_ENABLED` | `true` | 启用上下文优化 | 否 |
| `MEMORY_ENABLED` | `true` | 启用语义记忆 | 否 |
| `VECTOR_DB_PATH` | `./memory_store/vss.db` | 向量数据库路径 | 否 |
| `MAX_MEMORY_RESULTS` | `3` | 记忆检索数量 | 否 |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | 熔断阈值 | 否 |
| `CIRCUIT_BREAKER_TIMEOUT` | `60` | 熔断恢复时间(秒) | 否 |

**示例：启动时配置环境变量**

```bash
export LLM_BASE_URL=https://api.moonshot.cn/v1
export LLM_API_KEY=sk-your-kimi-key
export LLM_MODEL=moonshot-v1-8k
export PORT=8080

uv run --no-dev python -m llm_adapter_claw
```

---

### 配置文件

**config.json** - 热加载配置（可选）

在项目根目录创建 `config.json`，支持运行时热更新：

```json
{
  "providers": [
    {
      "id": "kimi",
      "name": "Kimi",
      "base_url": "https://api.moonshot.cn/v1",
      "api_key": "sk-your-key",
      "default_model": "moonshot-v1-8k",
      "models": ["moonshot-v1-8k", "moonshot-v1-32k"]
    },
    {
      "id": "openai",
      "name": "OpenAI",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-your-key",
      "default_model": "gpt-4o"
    }
  ]
}
```

**providers.json** - 批量导入（可选）

```json
{
  "providers": [
    {
      "id": "qwen",
      "name": "Qwen",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key": "sk-your-key",
      "default_model": "qwen-max"
    }
  ]
}
```

---

## 启动服务

### 前台启动（调试）

```bash
uv run --no-dev python -m llm_adapter_claw
```

输出示例：
```
INFO:     Started server process [1234]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

### 后台启动

```bash
# 使用 nohup
nohup uv run --no-dev python -m llm_adapter_claw > adapter.log 2>&1 &

# 或使用 systemd（推荐生产环境）
sudo systemctl start llm-adapter-claw
```

### 使用 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  llm-adapter:
    build: .
    ports:
      - "8080:8080"
    environment:
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_MODEL=${LLM_MODEL:-gpt-4}
      - MEMORY_ENABLED=true
    volumes:
      - ./memory_store:/app/memory_store
    restart: unless-stopped
```

启动：
```bash
docker-compose up -d
```

---

## 对接 OpenClaw

### 1. 编辑 OpenClaw 配置

找到 OpenClaw 的配置文件（通常在 `~/.openclaw/openclaw.json` 或项目目录）：

```json
{
  "llm_provider": "openai",
  "base_url": "http://localhost:8080/v1",
  "api_key": "sk-dummy",
  "model": "gpt-4"
}
```

### 2. 关键配置项说明

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `llm_provider` | `openai` | 保持 `openai`，Adapter 兼容 OpenAI 格式 |
| `base_url` | `http://localhost:8080/v1` | 指向 Adapter 服务地址 |
| `api_key` | `sk-dummy` | 任意值（Adapter 不校验，转发给上游） |
| `model` | `gpt-4` 或带前缀 | 模型名称，可加提供商前缀如 `kimi:moonshot-v1-8k` |

### 3. 多提供商配置示例

**使用特定提供商：**

```json
{
  "llm_provider": "openai",
  "base_url": "http://localhost:8080/v1",
  "api_key": "sk-dummy",
  "model": "kimi:moonshot-v1-8k"
}
```

前缀格式：`{provider_id}:{model_name}`

### 4. 验证对接

重启 OpenClaw 后，发送测试消息。观察 Adapter 日志：

```bash
# 查看日志
tail -f adapter.log
```

预期输出：
```
INFO:pipeline.start request_id=xxx model=kimi:moonshot-v1-8k messages=3
INFO:intent.classified intent=chat
INFO:pipeline.complete tokens_saved=150
```

---

## 验证部署

### 1. 健康检查

```bash
curl http://localhost:8080/health
# {"status": "healthy", "version": "0.7.0"}
```

### 2. 查看 API 文档

浏览器访问：
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

### 3. 测试代理

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### 4. 查看流量统计

```bash
curl http://localhost:8080/traffic/stats
```

---

## 故障排查

### 问题：服务无法启动

**检查端口占用：**
```bash
lsof -i :8080
# 更换端口: PORT=8081 uv run --no-dev python -m llm_adapter_claw
```

**检查依赖：**
```bash
uv run --no-dev python -c "import llm_adapter_claw"
```

### 问题：无法连接上游 LLM

**检查网络：**
```bash
curl -I $LLM_BASE_URL
```

**检查 API 密钥：**
```bash
export LLM_API_KEY=your-key
```

### 问题：OpenClaw 无法连接 Adapter

**检查 Adapter 监听地址：**
```bash
# 确保监听 0.0.0.0（所有接口）
export HOST=0.0.0.0
```

**检查防火墙：**
```bash
# Linux
sudo ufw allow 8080
```

### 问题：记忆功能不工作

**检查启用状态：**
```bash
curl http://localhost:8080/config/status
```

**查看日志：**
```bash
# 检查是否有 memory 相关错误
grep -i memory adapter.log
```

---

## 生产环境建议

1. **使用反向代理**（Nginx/Caddy）提供 HTTPS
2. **配置 systemd** 确保服务自动重启
3. **定期备份** `memory_store/` 目录
4. **监控指标** 通过 `/metrics` 端点集成 Prometheus
5. **限制资源** 使用 Docker 内存/CPU 限制

---

## 获取帮助

- **GitHub Issues**: https://github.com/aki66938/llm_adapter_claw/issues
- **API 文档**: http://localhost:8080/docs
- **日志查看**: `tail -f adapter.log`
