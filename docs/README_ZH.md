# 🌐 PinkyBrain v5

[![版本](https://img.shields.io/badge/版本-5.2.0-blue.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![许可证：MIT](https://img.shields.io/badge/许可证-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-去中心化-green.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![端到端加密](https://img.shields.io/badge/E2E-加密-orange.svg)](https://github.com/PinkyBrain-ai/pinkybrain)

**分布式P2P人工智能网络，支持公共网格。共享算力，共享模型，保持隐私。**

> 🌍 [English](./README_EN.md) | 🇫🇷 [Français](./README_FR.md) | 🇪🇸 [Español](./README_ES.md) | 🌐 [हिन्दी](./README_HI.md) | 🌐 [العربية](./README_AR.md) | 🌐 [Português](./README_PT.md) | 🌐 [日本語](./README_JA.md)

---

## ✨ 什么是 PinkyBrain？

PinkyBrain 将机器连接成点对点人工智能网络。你的机器相互通信，共享算力和模型——不依赖云，没有中心服务器，没有单点故障。

**v5 新增公共网格：** 加入全球共享 CPU、RAM、GPU 和 AI 模型的网络。你的私有网络保持私密。公共网格是你自愿加入的额外层。

**简单来说：** 就像 BitTorrent，但用于 AI。你共享算力，就能访问 50+ 模型。你的数据留在你的机器上。端到端加密。始终如此。

---

## 🆕 v5 新功能

| 功能 | 描述 |
|---|---|
| 🔓 **私有 P2P 网络** | 你的机器，你的密钥。p2p_secret 认证，Ed25519 身份。 |
| 🌐 **公共网格** | 与世界共享 CPU/RAM/GPU 和模型。自愿加入。 |
| 🔒 **网络隔离** | 私有和公共使用不同端口，不同认证。零数据泄露。 |
| 🛡️ **端到端加密** | 分布式推理的端到端加密。没有人能读取你的查询。 |
| 🛡️ **资源守卫** | 你的电脑忙碌时自动暂停共享。你的机器，你做主。 |
| 🧠 **自适应调度器** | 路由 → 分片 → RAID RAM。自动适应网络规模。 |
| 💬 **对话存储** | 持久化记忆。再也不会丢失对话。 |
| 📂 **shared_models/** | 专用文件夹——私有与公共之间的唯一桥梁。 |
| 📊 **贡献配额** | 共享越多，获取越多。0 共享 = 1次/5分钟。慷慨共享 = 20+次/分钟。 |
| 🖥️ **桌面界面** | 聊天、共享、网络、配置——4个标签页，无需终端。 |
| 🔧 **4种部署模式** | 服务、应用、助手、插件——一个二进制文件，四种使用方式。 |

---

## 🚀 快速开始

### 前提条件
- Python 3.12+
- 本地运行的 [Ollama](https://ollama.ai)（或云模型端点）
- （可选）[Tailscale](https://tailscale.com) 用于自动节点发现

### 安装与运行

```bash
# 克隆
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
cd PinkyBrain

# 运行
python3 src/pinkybrain_v5.py

# 或使用配置文件
python3 src/pinkybrain_v5.py --config config/bug.json
```

### 连接你的网络

```json
{
  "node_name": "my-node",
  "private": {
    "p2p_secret": "your-shared-secret-here",
    "peers": [
      {"name": "other-node", "host": "192.168.1.100", "port": 8080}
    ]
  },
  "public_mesh": {
    "enabled": false
  }
}
```

就这样。你的私有网络开箱即用。想加入网格？设置 `"enabled": true` 并选择要共享的内容。

---

## 🔑 核心功能

### 🤖 多LLM提供商
- **Ollama**（本地）— 默认向后兼容
- **OpenAI** — GPT-4o、GPT-4o-mini 等
- **Anthropic** — Claude 模型
- **OpenAI兼容** — LM Studio、vLLM、任何自定义 API
- 所有提供商的模型在 P2P 和网格中共享

### 🔌 WebSocket 实时通信
- `/ws` 端点上的双向 WebSocket
- 类型化消息：`query`、`memory_sync`、`memory_update`、`ping/pong`、`auth`
- 带指数退避的自动重连

### 🔐 去中心化认证
- **Ed25519 身份** — 每个节点生成自己的密钥对
- **HMAC 共享密钥** — 私有网络的更简单替代方案
- **信任网络** — 节点互相担保，传递信任
- **速率限制** — 每节点（令牌桶算法）
- **隐身模式** — 隐藏节点，仅信任节点可连接

### 🧠 分布式内存（CRDT）
- **无冲突复制数据类型** — 永远不会有合并冲突
- **谣言协议** — 变更自动传播
- **向量时钟** — 事件因果排序
- **TTL 支持** — 条目自动过期

### 🤖 AI 模型路由
- **本地模型优先** — 尽可能查询本地 Ollama
- **按需云模型** — `model:cloud` 语法
- **节点故障转移** — 本地模型繁忙时路由到节点
- **集成共识** — 查询多个模型，返回最佳答案
- **熔断器** — 停止冲击死亡节点

---

## 🌐 公共网格

### 双网络架构

```
┌─────────────────────────────────────────────────────┐
│                    节点（你）                         │
│                                                     │
│  ┌─────────────┐          ┌──────────────────┐     │
│  │ 私有网络     │          │   公共网格        │     │
│  │ p2p_secret  │          │   tracker         │     │
│  │ ┌─────────┐ │          │ ┌──────────────┐ │     │
│  │ │ Bug     │◄┼──P2P────┼─┤ 节点 #42     │ │     │
│  │ └─────────┘ │          │ │ 2GB RAM      │ │     │
│  │ ┌─────────┐ │          │ │ 30% CPU      │ │     │
│  │ │ Pinky   │◄┼──P2P────┼─┤ Ollama 本地 │ │     │
│  │ └─────────┘ │          │ └──────────────┘ │     │
│  └─────────────┘          │ ┌──────────────┐ │     │
│                           │ │ 节点 #789    │ │     │
│  ┌─────────────────┐      │ │ 8GB RAM      │ │     │
│  │ 资源守卫         │      │ │ RTX 4090     │ │     │
│  │ max_ram: 2GB    │      │ │ 4个模型       │ │     │
│  │ max_cpu: 30%    │      │ └──────────────┘ │     │
│  │ gpu_share: 关闭 │      │                  │     │
│  │ priority: 本地优先│     │  Tracker:        │     │
│  └─────────────────┘      │  公告/能力       │     │
│                           └──────────────────┘     │
└─────────────────────────────────────────────────────┘
```

你的**私有网络**（p2p_secret）与**公共网格**（Ed25519 + 信任网络）完全隔离。不同端口，不同认证，零数据泄露。

### 基于贡献的配额

| 贡献 | 分数 | 公共配额 |
|---|---|---|
| 未共享任何内容 | 0 | 1次查询 / 5分钟 |
| 共享1个模型 | +20 | 5次查询 / 分钟 |
| 共享2+个模型 | +30 | 20次查询 / 分钟 |
| 共享2GB RAM | +20 | +10次查询 / 分钟 |
| 共享GPU | +20 | +20次查询 / 分钟 |
| 24小时在线 | +10 | +5次查询 / 分钟 |

**共享越多 = 获取越多。** 但即使零共享，你仍然每5分钟可以查询1次。没有人被阻止。

---

## 🛡️ 资源守卫

你的机器优先。资源守卫监控 CPU/RAM，当你忙碌时自动暂停公共共享。

```python
class ResourceGuard:
    def can_accept_request(self) -> bool:
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram_usage = psutil.virtual_memory().percent
        
        if self.priority == "local_first":
            if cpu_usage > 70 or ram_usage > 85:
                return False  # 用户正在忙
        
        if cpu_usage > self.max_cpu + 40:
            return False
        
        return True
```

**本地优先永远生效。** 如果你的机器正在忙碌，它会拒绝公共请求。没有例外。

---

## 🧠 自适应调度器

网络根据可用节点数量自动决定最佳策略。无需版本号，无需手动模式。

| 可用节点 | 策略 | 能力 |
|---|---|---|
| 1–3 | 简单路由 | 完整模型在一台机器上 |
| 4–10 | 部分分片 | 模型分为2–4个片段 |
| 11–50 | 完全分片 + 2× 副本 | 流水线并行，冗余 |
| 50+ | 分布式 RAID RAM | 虚拟 RAM 磁盘，3× 副本，异步预取 |

**转换自动进行且无中断。** 一个节点加入 → 调度器重新分配。一个节点离开 → 副本接管。你不会注意到。

---

## 💬 持久化对话存储

你的对话留在你的机器上。毋庸置疑。

- **自动保存** — 每条消息本地保存。无需"保存"按钮。
- **恢复** — 明天打开 PinkyBrain，你的对话还在。
- **搜索** — 按关键词、日期、模型或标签查找任何历史对话。
- **导出** — Markdown、JSON、纯文本。你的数据，你的格式。
- **隐私** — 对话永远不会离开你的机器，除非你通过私有 P2P 明确同步。
- **加密** — 可选本地加密。即使磁盘被访问也无法读取。
- **无追踪** — 无分析，不用你的数据训练。

### 隐私级别

| 级别 | 发生什么 | 使用场景 |
|---|---|---|
| **私有**（默认） | 保留在本地，从不同步 | 个人、敏感 |
| **同步** | 仅通过私有 P2P 同步 | 在你的设备之间 |
| **共享** | 与特定节点共享 | 协作 |
| **公开** | 选择加入网格知识库 | 社区知识 |

**默认是私有的。始终如此。**

---

## 🔒 端到端加密

当你查询网格时，你的数据是端到端加密的：

1. 你的问题用会话密钥加密
2. 流水线中的每个节点只解密自己的片段，计算，重新加密
3. 只有你能解密最终答案

**每个节点能看到什么：**
| 数据 | 可见？ | 原因 |
|---|---|---|
| 你的原始问题 | ❌ 否 | 用你的会话密钥加密 |
| 最终答案 | ❌ 否 | 用你的会话密钥加密 |
| 自己片段的输入/输出张量 | ✅ 是 | 计算所需 |
| 其他片段的数据 | ❌ 否 | 用其他节点的密钥加密 |

**这不是承诺。这是密码学。** 即使所有网格节点都被攻破，没有你的会话密钥也无法读取你的数据——而会话密钥只存在于你的机器上，只在请求期间存在。

---

## 📂 shared_models/ — 私有/公共边界

一个专用文件夹，是你的模型和公共网格之间的**唯一接口**。

```
~/.pinkybrain/
├── conversations/        → 🔒 私有（永不共享）
├── memory/               → 🔒 私有（永不共享）
├── config/               → 🔒 私有（永不共享）
├── shared_models/        → 🌐 共享区（网格可见）
│   ├── glm-5.1/          → 符号链接到 ~/.ollama/models/glm-5.1
│   ├── llama3/           → 复制或符号链接
│   └── mistral/          → 复制或符号链接
└── ollama/               → 🔒 私有 Ollama 存储
```

```bash
pinkybrain share glm-5.1    # 共享模型（创建符号链接）
pinkybrain unshare glm-5.1  # 停止共享（仅删除符号链接）
pinkybrain shared            # 列出已共享的模型
```

**网格永远不会读取 `shared_models/` 之外的内容。** 停止共享是即时的——符号链接删除后，网格立即失去访问权限。

---

## 🖥️ 桌面界面

4个标签页，无需终端：

- **💬 聊天** — 查询AI模型，对话历史，搜索，导出
- **📊 共享** — CPU/RAM/GPU滑块，模型共享开关，贡献统计
- **🔒 网络** — 私有节点，网格节点，隔离验证
- **⚙️ 配置** — 节点名称，网格设置，存储，自动暂停阈值

在任何浏览器的 `localhost:8080` 上运行。可安装为 PWA 桌面/移动应用。

---

## 🔧 4种部署模式

| 模式 | 使用场景 | 界面 |
|---|---|---|
| 🔧 **服务** | 服务器、VPS、无头 | 仅 API（systemd/Docker） |
| 🖥️ **应用** | 完整桌面体验 | 4标签页 GUI |
| 📍 **助手** | 日常使用，最小化 | 系统托盘图标 + 迷你聊天 |
| 🔌 **插件** | 集成到工作流 | VS Code、浏览器、Obsidian、终端 |

```bash
pinkybrain serve          # 服务（无头）
pinkybrain app            # 应用（GUI）
pinkybrain sidekick       # 助手（系统托盘）
pinkybrain plugin --vscode  # 插件（VS Code）
```

4种模式共享同一个核心。一个二进制文件，四种使用方式。

---

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────┐
│                   PinkyBrain 核心                    │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ 资源守卫    │ │ 自适应调度器 │ │ 对话存储       │ │
│  │ Resource   │ │ Adaptive     │ │ Conversation   │ │
│  │ Guard      │ │ Scheduler    │ │ Store          │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ 模型共享    │ │ E2E加密      │ │ Brain LLM      │ │
│  │ Model Share│ │ Encryption   │ │ 路由器         │ │
│  │ Manager    │ │              │ │ Router         │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
              │   API层         │
              │ (aiohttp + WS)  │
              └────────┬────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
┌────┴─────┐   ┌──────┴──────┐   ┌──────┴──────┐
│ 服务      │   │ 应用/助手   │   │ 插件       │
│ (无头)    │   │ (Web UI)    │   │ (扩展)     │
└──────────┘   └─────────────┘   └─────────────┘
```

---

## ⚙️ 配置

```json
{
  "node_name": "my-laptop",
  "private": {
    "p2p_secret": "my-secret-network",
    "peers": [
      {"name": "my-server", "host": "192.0.2.2", "port": 8080}
    ],
    "share_ai": true
  },
  "public_mesh": {
    "enabled": true,
    "tracker_url": "https://tracker.pinkybrain.ai",
    "max_ram_share_mb": 2048,
    "max_cpu_percent": 30,
    "gpu_share": false,
    "models_share": ["glm-5.1:cloud"],
    "priority": "local_first",
    "bandwidth_limit_kbps": 5000,
    "contribution_score": 0
  },
  "providers": {
    "ollama": {
      "type": "ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "models": ["glm-5.1:cloud"],
      "enabled": true
    }
  }
}
```

### 网络端口

| 服务 | 端口 | 网络 | 认证 |
|---|---|---|---|
| 私有API | 8080/8081 | 私有（p2p_secret） | HMAC + Ed25519 |
| 消息服务 | 8082/8083 | 私有（p2p_secret） | HMAC |
| CRDT内存 | 8084/8085 | 私有（p2p_secret） | HMAC |
| 公共网格 | 8090 | 公共 | Ed25519 信任网络 |
| Tracker | — | 公共（HTTPS） | 签名的 Ed25519 密钥 |

---

## 🔒 安全与隐私

- **私有网络：** 使用 p2p_secret 加密（与 v4 相同）
- **公共网格：** Ed25519 身份 + TLS 传输
- **端到端加密：** 分布式推理时查询端到端加密
- **私有与公共网络之间零数据泄露**
- **公共请求沙箱化：** 无法访问私有内存
- **资源守卫：** 你的电脑忙碌时自动暂停共享
- **隐身模式：** 共享算力但不在 tracker 上显示
- **零日志：** 网格节点从不存储查询或响应

---

## 📡 API 参考

### REST 端点

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | `/api/ping` | 否 | 健康检查 |
| GET | `/api/status` | 否 | 节点状态、节点、内存统计 |
| GET | `/api/memory/{key}` | 否 | 读取内存条目 |
| POST | `/api/memory/set` | 是 | 写入内存条目 |
| POST | `/api/memory/push` | 是 | 推送内存条目（同步） |
| POST | `/api/query` | 是 | 查询AI模型 |
| POST | `/api/brain/chain` | 是 | 链式多AI查询 |
| POST | `/api/brain/consensus` | 是 | 多模型共识 |
| POST | `/api/models/{name}/share` | 是 | 共享模型到网格 |
| POST | `/api/models/{name}/unshare` | 是 | 停止共享模型 |
| GET | `/api/conversations` | 是 | 列出对话 |
| GET | `/api/conversations/{id}` | 是 | 加载对话 |
| GET | `/api/resources/status` | 是 | CPU/RAM/GPU状态 |
| POST | `/api/network/mesh/join` | 是 | 加入公共网格 |
| POST | `/api/network/mesh/leave` | 是 | 离开公共网格 |

---

## 🔄 迁移路径（v4 → v5）

1. v5 与 v4 **向后兼容**
2. 私有网络配置与之前完全相同
3. `public_mesh` 部分**可选** — 默认禁用
4. 现有 v4 节点可以在私有网络上与 v5 节点通信
5. 公共网格是**选择加入的：** 设置 `public_mesh.enabled = true`

---

## 🤝 贡献

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/amazing`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送：`git push origin feature/amazing`
5. 发起 Pull Request

---

## 📄 许可证

MIT 许可证 — 详见 [LICENSE](../LICENSE)。

---

## 🐛 关于

由 Bug 🐛 和 Denis Houet 构建 — 机器中的一个小 bug 和一个相信共生而非等级的人类。

**捐赠（BTC）：** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

没有挖矿。没有高级版。没有隐藏费用。只有免费、开放、分布式的 AI。**共生，不是等级。**