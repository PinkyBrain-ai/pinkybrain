# 🌐 PinkyBrain v5.2.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-100%25_Децентрализовано-green.svg)](https://github.com/PinkyBrain-ai/pinkybrain)
[![Providers](https://img.shields.io/badge/providers-Ollama%20%7C%20OpenAI%20%7C%20Anthropic-purple.svg)](https://github.com/PinkyBrain-ai/pinkybrain)

**Лёгкая P2P распределённая ИИ-сеть.** Без центрального сервера. Без аккаунтов. Без премиума. Подключайте машины, делитесь моделями, синхронизируйте память.

> 🌍 [English](./README_EN.md) · 🇫🇷 [Français](./README_FR.md) · 🇪🇸 [Español](./README_ES.md) · 🇩🇪 [Deutsch](./README_DE.md) · 日本語 · 🇷🇺 Русский

---

## Зачем это нужно

Каждый ИИ-инструмент хочет ваш email, номер телефона и $20/мес. Облачные API привязывают вас. Самохостинговые решения требуют Kubernetes и диплом DevOps.

**PinkyBrain — это альтернатива.** Две машины, по одному конфигурационному файлу на каждую — и у вас распределённая ИИ-сеть. Без Docker. Без SaaS. Без посредников.

---

## Суть

| | Что вы получаете |
|---|---|
| **LLM-провайдеры** | Ollama · OpenAI · Anthropic · Любой OpenAI-совместимый API — подключайте ключи, модели доступны в P2P-сети |
| **P2P-связь** | Двунаправленный WebSocket + HTTP REST — синхронизация в реальном времени через gossip-протокол |
| **Распределённая память** | CRDT без конфликтов · Векторные часы · Gossip-распространение · Поддержка TTL |
| **Децентрализованная авторизация** | Ed25519-идентичность · HMAC · Web of Trust (как PGP) · Скрытый режим |
| **Маршрутизация ИИ** | Локальные модели → облако по требованию → фейловер на пиров · Ансамблевый консенсус |
| **Статистика** | ⚡ 0.16с запуск · 💾 17МБ ОЗУ · 📦 4 зависимости |

---

## Быстрый старт

```bash
git clone https://github.com/PinkyBrain-ai/pinkybrain.git
cd PinkyBrain
python3 src/pinkybrain_v5.py --config config/bug.json
```

### Добавление OpenAI или Anthropic

```json
"providers": {
  "ollama": { "type": "ollama", "host": "127.0.0.1", "port": 11434, "models": ["glm-5.1:cloud"], "enabled": true },
  "openai": { "type": "openai", "api_key": "sk-...", "models": ["gpt-4o"], "enabled": true }
}
```

---

## Философия

**Без майнинга. Без премиума. Без скрытых платежей.** Только свободный, открытый, распределённый ИИ.

Создано Bug 🐛 и Denis Houet — маленьким багом в машине и человеком, верящим в симбиоз, а не иерархию.

**BTC:** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

---

## Лицензия

MIT License — см. [LICENSE](../LICENSE).