# 🌐 PinkyBrain v5.2.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-100%25_Dezentralisiert-green.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![Providers](https://img.shields.io/badge/providers-Ollama%20%7C%20OpenAI%20%7C%20Anthropic-purple.svg)](https://github.com/PinkyBrain-ai/pinkybrain)

**Leichtgewichtiges P2P-verteiltes KI-Netzwerk.** Kein zentraler Server. Keine Accounts. Kein Premium. Maschinen verbinden, Modelle teilen, Speicher synchronisieren.

> 🌍 [English](./README_EN.md) · 🇫🇷 [Français](./README_FR.md) · 🇪🇸 [Español](./README_ES.md) · 🇩🇪 Deutsch

---

## Warum es das gibt

Jedes KI-Tool will deine E-Mail, deine Telefonnummer und 20€/Monat. Cloud-APIs sperren dich ein. Self-Hosted-Lösungen brauchen Kubernetes und einen DevOps-Abschluss.

**PinkyBrain ist die Alternative.** Zwei Maschinen, je eine Konfigurationsdatei, und du hast ein verteiltes KI-Netzwerk. Kein Docker. Kein SaaS. Kein Mittelsmann. Deine Maschinen kommunizieren direkt, teilen KI-Antworten und synchronisieren Speicher — wenn eine ausfällt, laufen die anderen weiter.

---

## Auf einen Blick

| | Was du bekommst |
|---|---|
| **LLM-Anbieter** | Ollama · OpenAI · Anthropic · Jede OpenAI-kompatible API — Schlüssel einstecken, Modelle werden im P2P-Netzwerk geteilt |
| **P2P-Kommunikation** | Bidirektionales WebSocket (`/ws`) + HTTP REST — Echtzeit-Sync mit Gossip-Protokoll |
| **Verteilter Speicher** | CRDT-konfliktfreier Zustand · Vektoruhr · Gossip-Propagation · TTL-Unterstützung |
| **Dezentrale Auth** | Ed25519-Identität · HMAC-Shared-Secret · Web of Trust (PGP-ähnlich) · Stealth-Modus |
| **KI-Routing** | Lokale Modelle zuerst → Cloud on Demand → Peer-Failover · Ensemble-Konsens · Circuit Breakers |
| **Auto-Discovery** | Statische Konfiguration · Tailscale-Auto-Discovery · Dynamische API-Registrierung |
| **Stats** | ⚡ 0.16s Start · 💾 17MB RAM · 📦 4 Abhängigkeiten |

---

## Schnellstart

```bash
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
cd PinkyBrain
python3 src/pinkybrain_v5.py --config config/bug.json
```

### OpenAI oder Anthropic hinzufügen

```json
"providers": {
  "ollama": { "type": "ollama", "host": "127.0.0.1", "port": 11434, "models": ["glm-5.1:cloud"], "enabled": true },
  "openai": { "type": "openai", "api_key": "sk-...", "models": ["gpt-4o"], "enabled": true }
}
```

---

## Philosophie

**Kein Mining. Kein Premium. Keine versteckten Kosten.** Nur freie, offene, verteilte KI.

Gebaut von Bug 🐛 und Denis Houet — ein kleiner Bug in der Maschine und ein Mensch, der an Symbiose glaubt, nicht an Hierarchie.

**BTC:** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

---

## Lizenz

MIT-Lizenz — siehe [LICENSE](../LICENSE) für Details.