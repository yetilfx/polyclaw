# PolyClaw: Polymarket 外科手术级套利引擎 🦞

**PolyClaw** 是一个专为 Polymarket 设计的高性能、模块化套利与对冲工具包。它突破了标准 Web UI 的限制，通过直接交互 Gamma API（事件/市场）和 CLOB API（订单执行），实现毫秒级的市场扫描与精准打击。

---

## 核心功能 (Core Capabilities)

### 1. 统一命令行 (Unified CLI)
所有功能都通过 `polyclaw.py` 统一入口访问，无需运行零散脚本。

### 2. 外科手术级套利 (Surgical Arbitrage)
- **Split Arbitrage**: 利用“聚合市场”与“分量市场”之间的价差（例如：ETH > $2000 vs $2100, $2200...）。
- **NegRisk Arbitrage**: 利用互斥事件组的定价错误（例如：Sum(Prices) < 1.0 或 > 1.0）。
- **原子级执行**: 包含流动性预检、合约 Mint/Merge 交互、以及强健的 CLOB 卖出逻辑（FOK -> IOC -> Limit）。

### 3. AI 智能对冲 (AI-Driven Hedging)
- 利用 LLM 推理市场间的逻辑蕴含关系（Implies / Implied By）。
- 发现非直观的对冲机会（例如：“选举举行” -> “有人当选”）。

---

## 快速开始 (Quick Start)

### 依赖配置
确保项目根目录存在 `.env` 文件，并包含以下变量：
```bash
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
POLYCLAW_PRIVATE_KEY=0xYOUR_PRIVATE_KEY...  # 必须以 0x 开头
CLOB_API_KEY=...
CLOB_API_SECRET=...
CLOB_PASSPHRASE=...
OPENROUTER_API_KEY=... # 用于 AI 对冲扫描
```

### 基础命令
```bash
# 进入脚本目录
cd scripts

# 检查钱包状态 & 余额
uv run python polyclaw.py wallet status

# 审计投资组合 (余额、持仓、最近交易)
uv run python polyclaw.py audit
```

---

## 📖 命令手册 (Command Reference)

### 1. 市场情报 (Market Intelligence)
```bash
# 查看全平台热门市场 (按成交量排序)
uv run python polyclaw.py markets trending

# 关键词搜索市场
uv run python polyclaw.py markets search "election"

# 查看特定市场详情
uv run python polyclaw.py market <market_id>
```

### 2. 套利扫描与执行 (Arbitrage)
专用于发现无风险或低风险套利机会。

```bash
# 扫描特定资产的套利机会 (支持 BTC, ETH, XRP)
# --threshold: 最小利润阈值 (默认 0.01 即 1%)
uv run python polyclaw.py arb scan --query ETH --threshold 0.01

# 执行预定义的套利计划
# --query: 计划ID (扫描时会显示，例如 ETH_1.9k)
# --amount: 总投入资金 (USD)
uv run python polyclaw.py arb execute --query ETH_1.9k --amount 50
```

### 3. AI 对冲发现 (Hedge Discovery)
利用 LLM 分析市场间的逻辑关系，寻找保险策略。

```bash
# 扫描热门市场寻找对冲
uv run python polyclaw.py hedge scan

# 针对特定话题扫描
uv run python polyclaw.py hedge scan --query "Middle East"

# 分析两个特定市场的对冲关系
uv run python polyclaw.py hedge analyze <id1> <id2>
```
参数说明：
- `--min-coverage`: 最小覆盖率阈值 (默认 0.85)
- `--tier`: 包含的逻辑层级 (1=最佳/直接蕴含, 2=高相关)

### 4. 交易与持仓 (Trading & Positions)
```bash
# 快速下单
# 买入 <id> 的 YES/NO
uv run python polyclaw.py buy <market_id> YES 10.5

# 查看当前持仓 (包含未实现盈亏)
uv run python polyclaw.py positions

# 查看特定持仓详情
uv run python polyclaw.py position <market_id>
```

### 5. 钱包管理 (Wallet)
```bash
# 检查状态
uv run python polyclaw.py wallet status

# [重要] 一键授权 CTF Exchange 和 NegRisk Adapter 合约
# 首次交易前必须运行一次
uv run python polyclaw.py wallet approve
```

---

## ⚠️ 关键操作警告 (Critical Warnings)

1.  **NegRisk 合约区分**:
    - **Exchange (`0xC5d563..`)**: 仅用于 CLOB 交易撮合。
    - **Adapter (`0xd91E80..`)**: 仅用于 Mint/Merge/Split 操作。
    - *切勿弄混！向 Exchange 发送 Merge 交易会导致 Gas 浪费且无效果。*

2.  **流动性陷阱**:
    - **高成交量 ≠ 高流动性**。一个市场可能有 $10M 成交量，但当前买单 (Bid) 为空。
    - 套利引擎内置了 `check_liquidity` 预检，但在手动操作时请务必先检查订单簿。

3.  **API 限制**:
    - Gamma API 可能会有数据延迟。
    - CLOB API 对频繁请求有速率限制，请勿过于频繁扫描。

---
*Maintained by the Antigravity Team (Linus Persona).*
