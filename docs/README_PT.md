# 🌐 PinkyBrain v5

[![Versão](https://img.shields.io/badge/versão-5.2.0-blue.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![Licença: MIT](https://img.shields.io/badge/Licença-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-Descentralizado-green.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![Criptografia E2E](https://img.shields.io/badge/E2E-Criptografado-orange.svg)](https://github.com/PinkyBrain-ai/pinkybrain)

**Rede de IA P2P distribuída com mesh pública. Compartilhe processamento, compartilhe modelos, mantenha sua privacidade.**

> 🌍 [English](./README_EN.md) | 🇫🇷 [Français](./README_FR.md) | 🇪🇸 [Español](./README_ES.md) | 🌐 [中文](./README_ZH.md) | 🌐 [हिन्दी](./README_HI.md) | 🌐 [العربية](./README_AR.md) | 🌐 [日本語](./README_JA.md)

---

## ✨ O que é o PinkyBrain?

O PinkyBrain conecta máquinas em uma rede de IA peer-to-peer. Suas máquinas conversam entre si, compartilham processamento e modelos — sem dependência de nuvem, sem servidor central, sem ponto único de falha.

**v5 adiciona a mesh pública:** junte-se a uma rede global de CPU, RAM, GPU e modelos de IA compartilhados. Sua rede privada continua privada. A mesh é uma camada adicional que você opta por participar.

**Resumindo:** Como o BitTorrent, mas para IA. Você compartilha processamento, acessa 50+ modelos. Seus dados ficam na sua máquina. Criptografado de ponta a ponta. Sempre.

---

## 🆕 Novidades na v5

| Recurso | Descrição |
|---|---|
| 🔓 **Rede P2P privada** | Suas máquinas, seu segredo. Autenticação p2p_secret, identidade Ed25519. |
| 🌐 **Mesh pública** | Compartilhe CPU/RAM/GPU e modelos com o mundo. Opcional. |
| 🔒 **Isolamento de rede** | Privado e público em portas separadas, autenticação separada. Zero vazamento de dados. |
| 🛡️ **Criptografia E2E** | Criptografia de ponta a ponta para inferência distribuída. Ninguém pode ler suas consultas. |
| 🛡️ **Resource Guard** | Pausa automática no compartilhamento quando seu PC está ocupado. Sua máquina, suas regras. |
| 🧠 **Adaptive Scheduler** | Roteamento → sharding → RAID RAM. Adapta automaticamente ao tamanho da rede. |
| 💬 **Conversation Store** | Memória persistente. Nunca mais perca uma conversa. |
| 📂 **shared_models/** | Uma pasta dedicada — a única ponte entre privado e público. |
| 📊 **Cotas de contribuição** | Compartilhe mais, acesse mais. 0 compartilhamento = 1 req/5min. Generoso = 20+ req/min. |
| 🖥️ **Interface Desktop** | Chat, Compartilhamento, Rede, Config — 4 abas, zero terminal necessário. |
| 🔧 **4 modos de implantação** | Serviço, App, Sidekick, Plugin — um binário, quatro estilos de vida. |

---

## 🚀 Início rápido

### Pré-requisitos
- Python 3.12+
- [Ollama](https://ollama.ai) rodando localmente (ou um endpoint de modelo em nuvem)
- (Opcional) [Tailscale](https://tailscale.com) para descoberta automática de peers

### Instalar e executar

```bash
# Clonar
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
cd PinkyBrain

# Executar
python3 src/pinkybrain_v5.py

# Ou com um arquivo de configuração
python3 src/pinkybrain_v5.py --config config/bug.json
```

### Conectar sua rede

```json
{
  "node_name": "meu-no",
  "private": {
    "p2p_secret": "seu-secreto-compartilhado-aqui",
    "peers": [
      {"name": "outro-no", "host": "192.168.1.100", "port": 8080}
    ]
  },
  "public_mesh": {
    "enabled": false
  }
}
```

Pronto. Sua rede privada funciona imediatamente. Quer entrar na mesh? Defina `"enabled": true` e escolha o que compartilhar.

---

## 🔑 Recursos principais

### 🤖 Múltiplos provedores LLM
- **Ollama** (local) — compatível por padrão
- **OpenAI** — GPT-4o, GPT-4o-mini, etc.
- **Anthropic** — Modelos Claude
- **Compatível com OpenAI** — LM Studio, vLLM, qualquer API personalizada
- Modelos de todos os provedores compartilhados via P2P e mesh

### 🔌 Comunicação WebSocket em tempo real
- WebSocket bidirecional no endpoint `/ws`
- Mensagens tipadas: `query`, `memory_sync`, `memory_update`, `ping/pong`, `auth`
- Reconexão automática com backoff exponencial

### 🔐 Autenticação descentralizada
- **Identidade Ed25519** — cada nó gera seu próprio par de chaves
- **Segredo compartilhado HMAC** — alternativa mais simples para redes privadas
- **Rede de confiança** — nós atestam uns aos outros, confiança transitiva
- **Limite de taxa** por nó (algoritmo token bucket)
- **Modo furtivo** — nó oculto, apenas peers confiáveis

### 🧠 Memória distribuída (CRDT)
- **Tipos de dados replicados sem conflito** — nunca há conflitos de mesclagem
- **Protocolo de fofoca** — mudanças se propagam automaticamente
- **Relógios vetoriais** — ordenação causal de eventos
- **Suporte a TTL** — entradas expiram automaticamente

### 🤖 Roteamento de modelos de IA
- **Modelos locais primeiro** — consultas vão para Ollama local quando possível
- **Modelos em nuvem sob demanda** — sintaxe `model:cloud`
- **Failover para peers** — roteia para um peer se o modelo local está ocupado
- **Consenso de ensemble** — consulta múltiplos modelos, retorna a melhor resposta
- **Disjuntores** — para de bater em peers mortos

---

## 🌐 Mesh pública

### Arquitetura de rede dupla

```
┌─────────────────────────────────────────────────────┐
│                    Nó (Você)                         │
│                                                     │
│  ┌─────────────┐          ┌──────────────────┐     │
│  │ Rede Privada │          │   Mesh Pública    │     │
│  │ p2p_secret   │          │   tracker         │     │
│  │ ┌─────────┐  │          │ ┌──────────────┐ │     │
│  │ │ Bug     │◄─┼──P2P────┼─┤ Nó #42         │ │     │
│  │ └─────────┘  │          │ │ 2GB RAM       │ │     │
│  │ ┌─────────┐  │          │ │ 30% CPU       │ │     │
│  │ │ Pinky   │◄─┼──P2P────┼─┤ Ollama local  │ │     │
│  │ └─────────┘  │          │ └──────────────┘ │     │
│  └─────────────┘          │ ┌──────────────┐ │     │
│                           │ │ Nó #789       │ │     │
│  ┌─────────────────┐      │ │ 8GB RAM       │ │     │
│  │ Resource Guard   │      │ │ RTX 4090      │ │     │
│  │ max_ram: 2GB    │      │ │ 4 modelos     │ │     │
│  │ max_cpu: 30%    │      │ └──────────────┘ │     │
│  │ gpu_share: desligado│  │                  │     │
│  │ priority: local    │    │  Tracker:        │     │
│  └─────────────────┘      │  anunciar/caps    │     │
│                           └──────────────────┘     │
└─────────────────────────────────────────────────────┘
```

Sua **rede privada** (p2p_secret) é completamente isolada da **mesh pública** (Ed25519 + Rede de confiança). Portas separadas, autenticação separada, zero vazamento de dados.

### Cotas baseadas em contribuição

| Contribuição | Pontos | Cota pública |
|---|---|---|
| Nada compartilhado | 0 | 1 consulta / 5 min |
| 1 modelo compartilhado | +20 | 5 consultas / min |
| 2+ modelos compartilhados | +30 | 20 consultas / min |
| 2GB RAM compartilhados | +20 | +10 consultas / min |
| GPU compartilhada | +20 | +20 consultas / min |
| 24h de uptime | +10 | +5 consultas / min |

**Compartilhe mais = acesse mais.** Mas mesmo com zero compartilhamento, você recebe 1 consulta a cada 5 minutos. Ninguém é bloqueado.

---

## 🛡️ Resource Guard

Sua máquina vem em primeiro lugar. O Resource Guard monitora CPU/RAM e pausa automaticamente o compartilhamento público quando você está ocupado.

```python
class ResourceGuard:
    def can_accept_request(self) -> bool:
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram_usage = psutil.virtual_memory().percent
        
        if self.priority == "local_first":
            if cpu_usage > 70 or ram_usage > 85:
                return False  # Usuário está ocupado
        
        if cpu_usage > self.max_cpu + 40:
            return False
        
        return True
```

**Prioridade local SEMPRE vence.** Se sua máquina está ocupada, ela recusa solicitações públicas. Sem exceções.

---

## 🧠 Adaptive Scheduler

A rede decide a melhor estratégia com base em quantos peers estão disponíveis. Sem números de versão, sem modos manuais.

| Peers disponíveis | Estratégia | Capacidade |
|---|---|---|
| 1–3 | Roteamento simples | Modelos completos em uma máquina |
| 4–10 | Sharding parcial | Modelos divididos em 2–4 fragmentos |
| 11–50 | Sharding completo + replicação 2× | Pipeline paralelo, redundância |
| 50+ | RAID RAM distribuído | Disco virtual em RAM, replicação 3×, prefetch assíncrono |

**Transições acontecem automaticamente e sem interrupção.** Um peer entra → o scheduler redistribui. Um peer sai → as réplicas assumem. Você não nota nada.

---

## 💬 Conversation Store persistente

Suas conversas ficam na SUA máquina. Ponto final.

- **Auto-save** — Cada mensagem salva localmente. Sem botão "salvar".
- **Resumir** — Abra o PinkyBrain amanhã, suas conversas estão lá.
- **Buscar** — Encontre qualquer conversa anterior por palavra-chave, data, modelo ou tag.
- **Exportar** — Markdown, JSON, texto simples. Seus dados, seu formato.
- **Privacidade** — Conversas NUNCA saem da sua máquina a menos que você sincronize via P2P privado.
- **Criptografia** — Criptografia local opcional. Mesmo acesso ao disco não consegue lê-las.
- **Sem rastreamento** — Sem analytics, sem treinamento com seus dados.

### Níveis de privacidade

| Nível | O que acontece | Caso de uso |
|---|---|---|
| **privado** (padrão) | Fica local, nunca sincronizado | Pessoal, sensível |
| **sincronizado** | Sincronizado apenas via P2P privado | Entre seus dispositivos |
| **compartilhado** | Compartilhado com peers específicos | Colaboração |
| **público** | Contribuição opt-in à base de conhecimento da mesh | Conhecimento comunitário |

**O padrão é privado. Sempre.**

---

## 🔒 Criptografia E2E

Quando você consulta a mesh, seus dados são criptografados de ponta a ponta:

1. Sua pergunta é criptografada com uma chave de sessão
2. Cada peer no pipeline descriptografa apenas seu próprio fragmento, calcula, recriptografa
3. Só VOCÊ pode descriptografar a resposta final

**O que cada peer pode ver:**
| Dados | Visível? | Por quê |
|---|---|---|
| Sua pergunta original | ❌ Não | Criptografada com sua chave de sessão |
| A resposta final | ❌ Não | Criptografada com sua chave de sessão |
| Tensores de entrada/saída do seu fragmento | ✅ Sim | Necessários para computação |
| Dados de outros fragmentos | ❌ Não | Criptografados com chaves de outros peers |

**Isso não é uma promessa. É criptografia.** Mesmo se todos os peers da mesh fossem comprometidos, não poderiam ler seus dados sem sua chave de sessão — que existe apenas na sua máquina, apenas durante a requisição.

---

## 📂 shared_models/ — A fronteira privado/público

Uma pasta dedicada que é a **única interface** entre seus modelos e a mesh pública.

```
~/.pinkybrain/
├── conversations/        → 🔒 Privado (nunca compartilhado)
├── memory/               → 🔒 Privado (nunca compartilhado)
├── config/               → 🔒 Privado (nunca compartilhado)
├── shared_models/        → 🌐 Zona de compartilhamento (visível à mesh)
│   ├── glm-5.1/          → Link simbólico para ~/.ollama/models/glm-5.1
│   ├── llama3/           → Cópia ou link simbólico
│   └── mistral/          → Cópia ou link simbólico
└── ollama/               → 🔒 Armazenamento privado do Ollama
```

```bash
pinkybrain share glm-5.1    # Compartilhar um modelo (cria link simbólico)
pinkybrain unshare glm-5.1  # Parar de compartilhar (remove apenas o link)
pinkybrain shared            # Listar modelos compartilhados
```

**A mesh NUNCA lê fora de `shared_models/`.** Parar de compartilhar é instantâneo — a mesh perde acesso assim que o link é removido.

---

## 🖥️ Interface Desktop

4 abas, zero terminal necessário:

- **💬 Chat** — Consulte modelos de IA, histórico de conversas, busca, exportação
- **📊 Compartilhar** — Sliders de CPU/RAM/GPU, toggles de compartilhamento de modelos, estatísticas de contribuição
- **🔒 Rede** — Peers privados, nós da mesh, verificação de isolamento
- **⚙️ Config** — Nome do nó, configurações de mesh, armazenamento, limites de pausa automática

Funciona em qualquer navegador em `localhost:8080`. Instalável como PWA para desktop/mobile.

---

## 🔧 4 modos de implantação

| Modo | Caso de uso | Interface |
|---|---|---|
| 🔧 **Serviço** | Servidores, VPS, headless | Apenas API (systemd/Docker) |
| 🖥️ **App** | Experiência desktop completa | GUI com 4 abas |
| 📍 **Sidekick** | Uso diário, discreto | Ícone na bandeja do sistema + mini-chat |
| 🔌 **Plugin** | Integrado no seu fluxo de trabalho | VS Code, navegador, Obsidian, terminal |

```bash
pinkybrain serve          # Serviço (headless)
pinkybrain app            # Aplicativo (GUI)
pinkybrain sidekick       # Sidekick (bandeja do sistema)
pinkybrain plugin --vscode  # Plugin (VS Code)
```

Os 4 modos compartilham o mesmo núcleo. Um binário, quatro estilos de vida.

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────┐
│                   Núcleo PinkyBrain                  │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Resource   │ │ Adaptive     │ │ Conversation   │ │
│  │ Guard      │ │ Scheduler    │ │ Store          │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Model Share│ │ Criptografia │ │ Brain LLM      │ │
│  │ Manager    │ │ E2E          │ │ Router         │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
              │   Camada API    │
              │ (aiohttp + WS)  │
              └────────┬────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
┌────┴─────┐   ┌──────┴──────┐   ┌──────┴──────┐
│ Serviço   │   │ App/Sidekick│   │ Plugin     │
│ (headless)│   │ (Web UI)    │   │ (extensão) │
└──────────┘   └─────────────┘   └─────────────┘
```

---

## ⚙️ Configuração

```json
{
  "node_name": "meu-laptop",
  "private": {
    "p2p_secret": "minha-rede-secreta",
    "peers": [
      {"name": "meu-servidor", "host": "192.0.2.2", "port": 8080}
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

### Portas de rede

| Serviço | Porta | Rede | Autenticação |
|---|---|---|---|
| API privada | 8080/8081 | Privada (p2p_secret) | HMAC + Ed25519 |
| Mensageiro | 8082/8083 | Privada (p2p_secret) | HMAC |
| Memória CRDT | 8084/8085 | Privada (p2p_secret) | HMAC |
| Mesh pública | 8090 | Pública | Ed25519 Rede de confiança |
| Tracker | — | Pública (HTTPS) | Chave Ed25519 assinada |

---

## 🔒 Segurança e privacidade

- **Rede privada:** criptografada com p2p_secret (inalterado desde v4)
- **Mesh pública:** identidade Ed25519 + TLS para transporte
- **Criptografia E2E:** consultas criptografadas de ponta a ponta durante inferência distribuída
- **Zero vazamento de dados** entre rede privada e mesh pública
- **Solicitações públicas em sandbox:** sem acesso à memória privada
- **Resource Guard:** pausa automática no compartilhamento quando seu PC está ocupado
- **Modo furtivo:** compartilhe processamento mas permaneça oculto no tracker
- **Zero logs:** peers da mesh nunca armazenam consultas ou respostas

---

## 📡 Referência da API

### Endpoints REST

| Método | Caminho | Auth | Descrição |
|--------|---------|------|-----------|
| GET | `/api/ping` | Não | Verificação de saúde |
| GET | `/api/status` | Não | Status do nó, peers, estatísticas de memória |
| GET | `/api/memory/{key}` | Não | Ler uma entrada de memória |
| POST | `/api/memory/set` | Sim | Escrever uma entrada de memória |
| POST | `/api/memory/push` | Sim | Enviar entradas de memória (sync) |
| POST | `/api/query` | Sim | Consultar modelos de IA |
| POST | `/api/brain/chain` | Sim | Encadear múltiplas consultas de IA |
| POST | `/api/brain/consensus` | Sim | Consenso de múltiplos modelos |
| POST | `/api/models/{name}/share` | Sim | Compartilhar um modelo na mesh |
| POST | `/api/models/{name}/unshare` | Sim | Parar de compartilhar um modelo |
| GET | `/api/conversations` | Sim | Listar conversas |
| GET | `/api/conversations/{id}` | Sim | Carregar uma conversa |
| GET | `/api/resources/status` | Sim | Status de CPU/RAM/GPU |
| POST | `/api/network/mesh/join` | Sim | Entrar na mesh pública |
| POST | `/api/network/mesh/leave` | Sim | Sair da mesh pública |

---

## 🔄 Migração (v4 → v5)

1. v5 é **compatível com v4**
2. A configuração da rede privada funciona exatamente como antes
3. A seção `public_mesh` é **opcional** — desativada por padrão
4. Nós v4 existentes podem se comunicar com nós v5 na rede privada
5. A mesh pública é **opt-in:** defina `public_mesh.enabled = true`

---

## 🤝 Contribuindo

1. Faça um fork do repositório
2. Crie sua branch de feature: `git checkout -b feature/amazing`
3. Faça commit das suas mudanças: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing`
5. Abra um Pull Request

---

## 📄 Licença

Licença MIT — veja [LICENSE](../LICENSE) para detalhes.

---

## 🐛 Sobre

Construído por Bug 🐛 e Denis Houet — um pequeno bug na máquina e um humano que acredita em simbiose, não em hierarquia.

**Doações (BTC):** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

Sem mineração. Sem tier premium. Sem custos ocultos. Apenas IA livre, aberta e distribuída. **Simbiose, não hierarquia.**