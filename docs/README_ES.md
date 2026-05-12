# 🌐 PinkyBrain v5

[![Versión](https://img.shields.io/badge/versión-5.2.0-blue.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-Descentralizado-green.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![Cifrado E2E](https://img.shields.io/badge/E2E-Cifrado-orange.svg)](https://github.com/PinkyBrain-ai/pinkybrain)

**Red de IA P2P distribuida con malla pública. Comparte cómputo, comparte modelos, mantente privado.**

> 🌍 [English](./README_EN.md) | 🇫🇷 [Français](./README_FR.md) | 🌐 [中文文档](./README_ZH.md) | 🌐 [हिन्दी](./README_HI.md) | 🌐 [العربية](./README_AR.md) | 🌐 [Português](./README_PT.md) | 🌐 [日本語](./README_JA.md)

---

## ✨ ¿Qué es PinkyBrain?

PinkyBrain conecta máquinas en una red de IA peer-to-peer. Tus máquinas se comunican entre sí, comparten cómputo y modelos — sin dependencia de la nube, sin servidor central, sin punto único de fallo.

**v5 añade la malla pública:** únete a una red global de CPU, RAM, GPU y modelos IA compartidos. Tu red privada sigue siendo privada. La malla es una capa adicional que activas voluntariamente.

**En resumen:** Como BitTorrent, pero para IA. Compartes cómputo, accedes a más de 50 modelos. Tus datos se quedan en tu máquina. Cifrado de extremo a extremo. Siempre.

---

## 🆕 Novedades en v5

| Funcionalidad | Descripción |
|---|---|
| 🔓 **Red P2P privada** | Tus máquinas, tu secreto. Autenticación p2p_secret, identidad Ed25519. |
| 🌐 **Malla pública** | Comparte CPU/RAM/GPU y modelos con el mundo. Opcional. |
| 🔒 **Aislamiento de red** | Privado y público en puertos separados, auth separada. Cero filtración de datos. |
| 🛡️ **Cifrado E2E** | Cifrado de extremo a extremo para inferencia distribuida. Nadie puede leer tus consultas. |
| 🛡️ **Resource Guard** | Pausa automática del compartimiento cuando tu PC está ocupado. Tu máquina, tus reglas. |
| 🧠 **Adaptive Scheduler** | Enrutamiento → sharding → RAID RAM. Se adapta automáticamente al tamaño de la red. |
| 💬 **Conversation Store** | Memoria persistente. Nunca más pierdas una conversación. |
| 📂 **shared_models/** | Una carpeta dedicada — el único puente entre privado y público. |
| 📊 **Cuotas de contribución** | Comparte más, accede más. 0 compartición = 1 req/5min. Generoso = 20+ req/min. |
| 🖥️ **Interfaz Desktop** | Chat, Compartir, Red, Config — 4 pestañas, cero terminal necesaria. |
| 🔧 **4 modos de despliegue** | Servicio, App, Sidekick, Plugin — un binario, cuatro estilos de vida. |

---

## 🚀 Inicio rápido

### Requisitos previos
- Python 3.12+
- [Ollama](https://ollama.ai) ejecutándose localmente (o un endpoint en la nube)
- (Opcional) [Tailscale](https://tailscale.com) para descubrimiento automático de pares

### Instalar y ejecutar

```bash
# Clonar
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
cd PinkyBrain

# Ejecutar
python3 src/pinkybrain_v5.py

# O con un archivo de configuración
python3 src/pinkybrain_v5.py --config config/bug.json
```

### Conectar tu red

```json
{
  "node_name": "mi-nodo",
  "private": {
    "p2p_secret": "tu-secreto-compartido-aqui",
    "peers": [
      {"name": "otro-nodo", "host": "192.168.1.100", "port": 8080}
    ]
  },
  "public_mesh": {
    "enabled": false
  }
}
```

Eso es todo. Tu red privada funciona de inmediato. ¿Quieres unirte a la malla? Establece `"enabled": true` y elige qué compartir.

---

## 🔑 Funcionalidades clave

### 🤖 Múltiples proveedores LLM
- **Ollama** (local) — compatible por defecto
- **OpenAI** — GPT-4o, GPT-4o-mini, etc.
- **Anthropic** — Modelos Claude
- **Compatible con OpenAI** — LM Studio, vLLM, cualquier API personalizada
- Modelos de todos los proveedores compartidos en P2P y malla

### 🔌 Comunicación WebSocket en tiempo real
- WebSocket bidireccional en el endpoint `/ws`
- Mensajes tipados: `query`, `memory_sync`, `memory_update`, `ping/pong`, `auth`
- Reconexión automática con retroceso exponencial

### 🔐 Autenticación descentralizada
- **Identidad Ed25519** — cada nodo genera su propio par de claves
- **Secreto compartido HMAC** — alternativa más simple para redes privadas
- **Red de confianza** — los nodos se avalan mutuamente, confianza transitiva
- **Limitación de tasa** por nodo (algoritmo token bucket)
- **Modo sigiloso** — nodo oculto, solo pares de confianza

### 🧠 Memoria distribuida (CRDT)
- **Tipos de datos replicados sin conflicto** — nunca hay conflictos de fusión
- **Protocolo de rumor** — los cambios se propagan automáticamente
- **Relojes vectoriales** — ordenamiento causal de eventos
- **Soporte TTL** — las entradas expiran automáticamente

### 🤖 Enrutamiento de IA
- **Modelos locales primero** — las consultas van a Ollama local cuando sea posible
- **Modelos en la nube bajo demanda** — sintaxis `model:cloud`
- **Failover a pares** — enruta a un par si el modelo local está ocupado
- **Consenso de conjunto** — consulta múltiples modelos, devuelve la mejor respuesta
- **Disyuntores** — deja de acosar a los pares caídos

---

## 🌐 Malla pública

### Arquitectura de doble red

```
┌─────────────────────────────────────────────────────┐
│                    Nodo (Tú)                         │
│                                                     │
│  ┌─────────────┐          ┌──────────────────┐     │
│  │ Red Privada │          │   Malla Pública   │     │
│  │ p2p_secret  │          │   tracker         │     │
│  │ ┌─────────┐ │          │ ┌──────────────┐ │     │
│  │ │ Bug     │◄┼──P2P────┼─┤ Nodo #42     │ │     │
│  │ └─────────┘ │          │ │ 2GB RAM      │ │     │
│  │ ┌─────────┐ │          │ │ 30% CPU      │ │     │
│  │ │ Pinky   │◄┼──P2P────┼─┤ Ollama local │ │     │
│  │ └─────────┘ │          │ └──────────────┘ │     │
│  └─────────────┘          │ ┌──────────────┐ │     │
│                           │ │ Nodo #789    │ │     │
│  ┌─────────────────┐      │ │ 8GB RAM      │ │     │
│  │ Resource Guard   │      │ │ RTX 4090     │ │     │
│  │ max_ram: 2GB    │      │ │ 4 modelos    │ │     │
│  │ max_cpu: 30%    │      │ └──────────────┘ │     │
│  │ gpu_share: off   │      │                  │     │
│  │ priority: local   │      │  Tracker:        │     │
│  └─────────────────┘      │  anuncio/caps     │     │
│                           └──────────────────┘     │
└─────────────────────────────────────────────────────┘
```

Tu **red privada** (p2p_secret) está completamente aislada de la **malla pública** (Ed25519 + Red de confianza). Puertos separados, auth separada, cero filtración de datos.

### Cuotas basadas en contribución

| Contribución | Puntuación | Cuota pública |
|---|---|---|
| Nada compartido | 0 | 1 consulta / 5 min |
| 1 modelo compartido | +20 | 5 consultas / min |
| 2+ modelos compartidos | +30 | 20 consultas / min |
| 2GB RAM compartidos | +20 | +10 consultas / min |
| GPU compartido | +20 | +20 consultas / min |
| 24h de uptime | +10 | +5 consultas / min |

**Comparte más = accede más.** Pero incluso sin compartir nada, obtienes 1 consulta cada 5 minutos. Nadie queda bloqueado.

---

## 🛡️ Resource Guard

Tu máquina es lo primero. El Resource Guard monitorea CPU/RAM y pausa automáticamente el compartimiento público cuando estás ocupado.

```python
class ResourceGuard:
    def can_accept_request(self) -> bool:
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram_usage = psutil.virtual_memory().percent
        
        if self.priority == "local_first":
            if cpu_usage > 70 or ram_usage > 85:
                return False  # El usuario está ocupado
        
        if cpu_usage > self.max_cpu + 40:
            return False
        
        return True
```

**La prioridad local SIEMPRE gana.** Si tu máquina está ocupada, rechaza solicitudes públicas. Sin excepciones.

---

## 🧠 Adaptive Scheduler

La red decide la mejor estrategia según cuántos pares estén disponibles. Sin números de versión, sin modos manuales.

| Pares disponibles | Estrategia | Capacidad |
|---|---|---|
| 1–3 | Enrutamiento simple | Modelos completos en una máquina |
| 4–10 | Sharding parcial | Modelos divididos en 2–4 fragmentos |
| 11–50 | Sharding completo + replicación 2× | Pipeline paralelo, redundancia |
| 50+ | RAID RAM distribuido | Disco virtual en RAM, replicación 3×, prefetch asíncrono |

**Las transiciones ocurren automáticamente y sin interrupción.** Un par se une → el scheduler redistribuye. Un par se va → las réplicas toman el relevo. No notas nada.

---

## 💬 Conversation Store persistente

Tus conversaciones se quedan en TU máquina. Punto final.

- **Guardado automático** — Cada mensaje se guarda localmente. Sin botón "guardar".
- **Reanudar** — Abre PinkyBrain mañana, tus conversaciones están ahí.
- **Búsqueda** — Encuentra cualquier conversación por palabra clave, fecha, modelo o etiqueta.
- **Exportar** — Markdown, JSON, texto plano. Tus datos, tu formato.
- **Privacidad** — Las conversaciones NUNCA salen de tu máquina a menos que las sincronices vía P2P privado.
- **Cifrado** — Cifrado local opcional. Ni el acceso al disco permite leerlas.
- **Sin rastreo** — Sin analíticas, sin entrenamiento con tus datos.

### Niveles de privacidad

| Nivel | Qué pasa | Caso de uso |
|---|---|---|
| **privado** (predeterminado) | Se queda local, nunca se sincroniza | Personal, sensible |
| **sincronizado** | Sincronizado solo vía P2P privado | Entre tus dispositivos |
| **compartido** | Compartido con pares específicos | Colaboración |
| **público** | Contribución opt-in a la malla | Conocimiento comunitario |

**Por defecto: privado. Siempre.**

---

## 🔒 Cifrado E2E

Cuando consultas la malla, tus datos están cifrados de extremo a extremo:

1. Tu pregunta se cifra con una clave de sesión
2. Cada par en el pipeline descifra solo su propio fragmento, calcula, vuelve a cifrar
3. Solo TÚ puedes descifrar la respuesta final

**Lo que cada par puede ver:**
| Dato | ¿Visible? | Por qué |
|---|---|---|
| Tu pregunta original | ❌ No | Cifrada con tu clave de sesión |
| La respuesta final | ❌ No | Cifrada con tu clave de sesión |
| Tensores de entrada/salida de su fragmento | ✅ Sí | Necesarios para el cálculo |
| Datos de otros fragmentos | ❌ No | Cifrados con las claves de otros pares |

**Esto no es una promesa. Es criptografía.** Incluso si todos los pares estuvieran comprometidos, no podrían leer tus datos sin tu clave de sesión — que solo existe en tu máquina, solo durante la solicitud.

---

## 📂 shared_models/ — La frontera privado/público

Una carpeta dedicada que es la **única interfaz** entre tus modelos y la malla pública.

```
~/.pinkybrain/
├── conversations/        → 🔒 Privado (nunca compartido)
├── memory/               → 🔒 Privado (nunca compartido)
├── config/               → 🔒 Privado (nunca compartido)
├── shared_models/        → 🌐 Zona de compartición (visible a la malla)
│   ├── glm-5.1/          → Enlace simbólico a ~/.ollama/models/glm-5.1
│   ├── llama3/           → Copia o enlace simbólico
│   └── mistral/          → Copia o enlace simbólico
└── ollama/               → 🔒 Almacenamiento privado de Ollama
```

```bash
pinkybrain share glm-5.1    # Compartir un modelo (crea enlace simbólico)
pinkybrain unshare glm-5.1  # Dejar de compartir (elimina solo el enlace)
pinkybrain shared            # Listar modelos compartidos
```

**La malla NUNCA lee fuera de `shared_models/`.** Dejar de compartir es instantáneo — la malla pierde acceso en el momento en que se elimina el enlace.

---

## 🖥️ Interfaz Desktop

4 pestañas, cero terminal necesaria:

- **💬 Chat** — Consulta modelos IA, historial de conversaciones, búsqueda, exportar
- **📊 Compartir** — Sliders de CPU/RAM/GPU, toggles de compartir modelos, estadísticas de contribución
- **🔒 Red** — Pares privados, nodos de la malla, verificación de aislamiento
- **⚙️ Config** — Nombre del nodo, configuración de malla, almacenamiento, umbrales de pausa

Funciona en cualquier navegador en `localhost:8080`. Instalable como PWA para desktop/móvil.

---

## 🔧 4 modos de despliegue

| Modo | Caso de uso | Interfaz |
|---|---|---|
| 🔧 **Servicio** | Servidores, VPS, headless | Solo API (systemd/Docker) |
| 🖥️ **App** | Experiencia desktop completa | GUI con 4 pestañas |
| 📍 **Sidekick** | Uso diario, discreto | Icono en bandeja del sistema + mini-chat |
| 🔌 **Plugin** | Integrado en tu flujo de trabajo | VS Code, navegador, Obsidian, terminal |

```bash
pinkybrain serve          # Servicio (headless)
pinkybrain app            # Aplicación (GUI)
pinkybrain sidekick       # Sidekick (bandeja del sistema)
pinkybrain plugin --vscode  # Plugin (VS Code)
```

Los 4 modos comparten el mismo núcleo. Un binario, cuatro estilos de vida.

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                Núcleo de PinkyBrain                  │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Resource   │ │ Adaptive     │ │ Conversation   │ │
│  │ Guard      │ │ Scheduler    │ │ Store          │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Model Share│ │ Cifrado E2E  │ │ Brain LLM      │ │
│  │ Manager    │ │              │ │ Router         │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
              │  Capa API       │
              │ (aiohttp + WS)  │
              └────────┬────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
┌────┴─────┐   ┌──────┴──────┐   ┌──────┴──────┐
│ Servicio │   │ App/Sidekick│   │ Plugin     │
│ (headless)│   │ (Web UI)    │   │ (extensión) │
└──────────┘   └─────────────┘   └─────────────┘
```

---

## ⚙️ Configuración

```json
{
  "node_name": "mi-laptop",
  "private": {
    "p2p_secret": "mi-red-secreta",
    "peers": [
      {"name": "mi-servidor", "host": "192.0.2.2", "port": 8080}
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

### Puertos de red

| Servicio | Puerto | Red | Autenticación |
|---|---|---|---|
| API privada | 8080/8081 | Privada (p2p_secret) | HMAC + Ed25519 |
| Mensajería | 8082/8083 | Privada (p2p_secret) | HMAC |
| Memoria CRDT | 8084/8085 | Privada (p2p_secret) | HMAC |
| Malla pública | 8090 | Pública | Ed25519 Red de confianza |
| Tracker | — | Pública (HTTPS) | Clave Ed25519 firmada |

---

## 🔒 Seguridad y privacidad

- **Red privada:** cifrada con p2p_secret (sin cambios desde v4)
- **Malla pública:** identidad Ed25519 + TLS para transporte
- **Cifrado E2E:** consultas cifradas de extremo a extremo durante inferencia distribuida
- **Sin filtración de datos** entre red privada y malla pública
- **Solicitudes públicas en sandbox:** sin acceso a memoria privada
- **Resource Guard:** pausa automática del compartimiento cuando tu PC está ocupado
- **Modo sigiloso:** comparte cómputo pero permanece oculto en el tracker
- **Cero logs:** los pares de la malla nunca almacenan consultas ni respuestas

---

## 📡 Referencia API

### Endpoints REST

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/ping` | No | Verificación de salud |
| GET | `/api/status` | No | Estado del nodo, pares, estadísticas de memoria |
| GET | `/api/memory/{key}` | No | Leer una entrada de memoria |
| POST | `/api/memory/set` | Sí | Escribir una entrada de memoria |
| POST | `/api/memory/push` | Sí | Empujar entradas de memoria (sync) |
| POST | `/api/query` | Sí | Consultar modelos de IA |
| POST | `/api/brain/chain` | Sí | Encadenar múltiples consultas de IA |
| POST | `/api/brain/consensus` | Sí | Consenso de múltiples modelos |
| POST | `/api/models/{name}/share` | Sí | Compartir un modelo a la malla |
| POST | `/api/models/{name}/unshare` | Sí | Dejar de compartir un modelo |
| GET | `/api/conversations` | Sí | Listar conversaciones |
| GET | `/api/conversations/{id}` | Sí | Cargar una conversación |
| GET | `/api/resources/status` | Sí | Estado de CPU/RAM/GPU |
| POST | `/api/network/mesh/join` | Sí | Unirse a la malla pública |
| POST | `/api/network/mesh/leave` | Sí | Salir de la malla pública |

---

## 🔄 Migración (v4 → v5)

1. v5 es **retrocompatible** con v4
2. La configuración de red privada funciona exactamente igual que antes
3. La sección `public_mesh` es **opcional** — deshabilitada por defecto
4. Los nodos v4 existentes pueden comunicarse con nodos v5 en la red privada
5. La malla pública es **opt-in:** establece `public_mesh.enabled = true`

---

## 🤝 Contribuir

1. Haz un fork del repositorio
2. Crea tu rama: `git checkout -b feature/amazing`
3. Haz commit de tus cambios: `git commit -m 'Add amazing feature'`
4. Haz push: `git push origin feature/amazing`
5. Abre un Pull Request

---

## 📄 Licencia

Licencia MIT — ver [LICENSE](../LICENSE) para más detalles.

---

## 🐛 Acerca de

Construido por Bug 🐛 y Denis Houet — un pequeño bug en la máquina y un humano que cree en simbiosis, no en jerarquía.

**Donaciones (BTC):** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

Sin minería. Sin tier premium. Sin costos ocultos. Solo IA libre, abierta y distribuida. **Simbiosis, no jerarquía.**