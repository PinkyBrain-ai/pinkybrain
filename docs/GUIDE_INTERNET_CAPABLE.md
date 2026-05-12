# 🌐 GUIDE - Module Internet Capable
## Interconnexion sur des réseaux divers (LAN, WAN, Internet)

---

## 🌐 Vue d'Ensemble

Le module **Internet Capable** permet à PinkyBrain & PinkyBrainBug v3.0 de :
- ✅ S'interconnecter sur des réseaux divers (LAN, WAN, Internet)
- ✅ Traverser les NAT/Firewalls
- ✅ Découvrir automatiquement des nœuds sur Internet
- ✅ Communiquer de manière sécurisée (TLS)
- ✅ Fonctionner derrière des routeurs NAT

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│         Internet / Public Network                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────┐    ┌──────────────────┐          │
│  │ Rendezvous Server│◄──►│ Node A (Public)  │          │
│  │ :9990           │    │ 203.0.113.10:9999│          │
│  └──────────────────┘    └──────────────────┘          │
│         ▲                                                │
│         │                                                │
│         └───────────────────┬──────────────────────┐    │
│                             │                      │    │
│                    ┌────────▼────────┐   ┌───────▼──────┐  │
│                    │   NAT Router   │   │   NAT Router │  │
│                    │ 192.168.1.1    │   │  10.0.0.1    │  │
│                    └────────┬────────┘   └───────┬──────┘  │
│                             │                  │         │
│                             │                  │         │
│                    ┌────────▼────────┐   ┌───────▼──────┐  │
│                    │ Node B (NAT)    │   │ Node C (NAT) │  │
│                    │ 192.168.1.100:  │   │ 10.0.0.100:  │  │
│                    │   9999          │   │   9999       │  │
│                    └─────────────────┘   └──────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘

                    🌍 Interconnexion Multi-Réseaux
```

---

## 🌐 Composants Principaux

### 1. Rendezvous Server
**Role:** Serveur centralisé pour discovery sur Internet

**Fonctionnalités:**
- Enregistrement des nœuds
- Discovery de nœuds par critères (capabilities, network type)
- Heartbeat monitoring
- Liste des nœuds actifs

**Endpoints:**
- `POST /register` - Enregistre un nœud
- `POST /discover` - Découvre des nœuds
- `POST /heartbeat` - Heartbeat d'un nœud
- `POST /unregister` - Désinscrit un nœud
- `POST /list_nodes` - Liste tous les nœuds

### 2. NAT Traversal
**Role:** Traverser les NAT/Firewalls

**Fonctionnalités:**
- Détection du type de NAT
- Récupération de l'IP publique
- Test de reachability

### 3. Internet Discovery
**Role:** Découvrir des nœuds sur Internet

**Fonctionnalités:**
- Enregistrement avec rendezvous server
- Discovery de nœuds Internet
- Fusion avec discovery local
- Heartbeat automatique

### 4. Secure Network Client
**Role:** Communication sécurisée sur Internet

**Fonctionnalités:**
- Connexions TLS
- Authentification par API key
- Timeout handling
- Error handling

### 5. Multi-Network Manager
**Role:** Gestion unifiée des réseaux divers

**Fonctionnalités:**
- Auto-détection du type de réseau
- Gestion des connexions multi-réseaux
- Priorité aux nœuds publics
- Maintenance des connexions

---

## 🚀 Utilisation

### 1. Démarrer le Rendezvous Server

Le rendezvous server doit être accessible publiquement (sur Internet).

```bash
python3 /tmp/internet_capable.py
```

Ou intégré dans votre application :

```python
from internet_capable import RendezvousServer

rendezvous = RendezvousServer(host="0.0.0.0", port=9990)
await rendezvous.start()
```

**Important:** Le server doit être accessible depuis Internet (port 9990 ouvert sur le firewall).

### 2. Configurer Multi-Network Manager

Sur chaque nœud (PinkyBrain/PinkyBrainBug) :

```python
from internet_capable import MultiNetworkManager
from network_specialization import NetworkManager

# Configurer le manager réseau local
local_network = NetworkManager()

# Configurer le manager multi-réseau
multi_net = MultiNetworkManager(
    local_network=local_network,
    rendezvous_server="votre-rendezvous-server.com:9990",
    api_key="votre-api-key-securisee",
    tls_enabled=True
)

# Initialiser
await multi_net.initialize()
```

### 3. Découvrir des Nœuds

**Découvrir tous les nœuds (tous réseaux) :**

```python
nodes = await multi_net.discover_nodes()
for node in nodes:
    print(f"Found: {node['name']} at {node.get('public_address', node.get('private_address'))}")
```

**Découvrir uniquement des nœuds publics (Internet) :**

```python
public_nodes = await multi_net.discover_nodes({"network_type": "public"})
```

**Découvrir uniquement des nœuds locaux (LAN) :**

```python
local_nodes = await multi_net.discover_nodes({"network_type": "local"})
```

### 4. Envoyer des Requêtes sur Internet

```python
# Envoyer une requête à n'importe quel nœud
request = {
    "type": "query",
    "prompt": "Qu'est-ce que PinkyBrain ?"
}

# Le système choisit automatiquement le meilleur nœud
response = await multi_net.send_request(request)
print(response)
```

**Forcer l'utilisation de nœuds publics :**

```python
# Force l'utilisation de nœuds publics (utile derrière NAT)
response = await multi_net.send_request(request, force_public=True)
```

**Envoyer à un nœud spécifique :**

```python
# Envoyer à un nœud spécifique
node = nodes[0]  # Nœud découvert
response = await multi_net.send_request(request, node=node)
```

---

## 🔧 Configuration Avancée

### Rendezvous Server sur Internet

**Option 1: VPS (Virtual Private Server)**

```bash
# Sur votre VPS (DigitalOcean, AWS EC2, etc.)
python3 /tmp/internet_capable.py
```

**Option 2: Service Cloud**

```python
rendezvous = RendezvousServer(
    host="0.0.0.0",
    port=9990,
    db_path="/var/lib/rendezvous/rendezvous_db.json"
)
await rendezvous.start()
```

**Option 3: Docker**

```Conteneurfile
FROM python:3.12
COPY internet_capable.py /app/
CMD ["python", "/app/internet_capable.py"]
EXPOSE 9990
```

### NAT Traversal

**Détection automatique :**

```python
from internet_capable import NATTraversal

nat = NATTraversal()

# Type de NAT
nat_type = await nat.check_nat_type()
print(f"NAT Type: {nat_type}")

# IP publique
public_ip = await nat.get_public_ip()
print(f"Public IP: {public_ip}")

# Test de reachability
reachable = await nat.test_reachability("example.com", 80)
print(f"Reachable: {reachable}")
```

### Sécurité

**TLS activé (recommandé pour Internet) :**

```python
multi_net = MultiNetworkManager(
    local_network=local_network,
    rendezvous_server="rendezvous.example.com:9990",
    api_key="your-secure-api-key",
    tls_enabled=True  # TLS activé
)
```

**TLS désactivé (LAN uniquement) :**

```python
multi_net = MultiNetworkManager(
    local_network=local_network,
    tls_enabled=False  # TLS désactivé
)
```

---

## 🎯 Scénarios d'Utilisation

### Scénario 1: Réseau Local (LAN)

```
Configuration:
- Rendezvous Server: Non utilisé
- NAT Type: None
- Network Type: LOCAL
```

```python
multi_net = MultiNetworkManager(
    local_network=local_network,
    rendezvous_server=None  # Pas de rendezvous server
)

await multi_net.initialize()

# Découvre uniquement les nœuds locaux
nodes = await multi_net.discover_nodes()
```

### Scénario 2: Réseau Privé (WAN/VPN)

```
Configuration:
- Rendezvous Server: interne.wan.com:9990
- NAT Type: Present
- Network Type: WAN
```

```python
multi_net = MultiNetworkManager(
    local_network=local_network,
    rendezvous_server="interne.wan.com:9990",
    api_key="internal-api-key"
)

await multi_net.initialize()

# Découvre les nœuds sur le WAN
nodes = await multi_net.discover_nodes({"network_type": "wan"})
```

### Scénario 3: Internet (Public)

```
Configuration:
- Rendezvous Server: public-rendezvous.com:9990
- NAT Type: Present
- Network Type: WAN (mais avec IP publique)
```

```python
multi_net = MultiNetworkManager(
    local_network=local_network,
    rendezvous_server="public-rendezvous.com:9990",
    api_key="public-api-key",
    tls_enabled=True  # TLS obligatoire pour Internet
)

await multi_net.initialize()

# Le système s'auto-enregistre et peut être découvert
nodes = await multi_net.discover_nodes()
```

### Scénario 4: Multi-Réseaux (LAN + Internet)

```
Configuration:
- Rendezvous Server: public-rendezvous.com:9990
- NAT Type: Present
- Network Type: WAN
- Priorité: Public nodes > Local nodes
```

```python
multi_net = MultiNetworkManager(
    local_network=local_network,
    rendezvous_server="public-rendezvous.com:9990",
    api_key="secure-api-key",
    tls_enabled=True
)

await multi_net.initialize()

# Découvre tous les nœuds (LAN + Internet)
all_nodes = await multi_net.discover_nodes()

# Utilise automatiquement les meilleurs nœuds
response = await multi_net.send_request(request)
```

---

## 🔒 Sécurité

### TLS/SSL

**Activer TLS (recommandé pour Internet) :**

```python
multi_net = MultiNetworkManager(
    local_network=local_network,
    tls_enabled=True
)
```

**Activer TLS avec certificats personnalisés :**

```python
import ssl

context = ssl.create_default_context()
context.load_cert_chain("/path/to/cert.pem", "/path/to/key.pem")

# Le module utiliserait ce context pour les connexions TLS
```

### API Keys

**Utiliser une API key :**

```python
multi_net = MultiNetworkManager(
    local_network=local_network,
    api_key="your-secure-api-key"
)
```

**Rendezvous Server avec API key :**

```python
node_info = {
    "node_id": "node-id",
    "name": "Node Name",
    "public_address": "public-ip:port",
    "api_key": "your-api-key"  # Authentification
}

await internet_discovery.register_with_rendezvous(node_info)
```

---

## 📊 Monitoring

### Voir le statut

```python
status = await multi_net.get_status()

print(f"Network Type: {status['network_type']}")
print(f"Public IP: {status['public_ip']}")
print(f"NAT Type: {status['nat_type']}")
print(f"Nodes Discovered: {status['nodes_discovered']}")
```

### Maintenance automatique

```python
# Lancer la maintenance en background
await multi_net.maintain_connection()
```

Cette fonction :
- Envoie des heartbeats au rendezvous server (toutes les 30s)
- Maintient la connexion active
- Permet aux autres nœuds de vous découvrir

---

## 🎯 Avantages

✅ **Multi-Réseaux** - Fonctionne sur LAN, WAN, Internet
✅ **NAT Traversal** - Travers les NAT/Firewalls
✅ **Auto-Discovery** - Découverte automatique sur Internet
✅ **Sécurité** - TLS + API Keys
✅ **Flexibilité** - Priorité locale ou publique
✅ **Scalabilité** - Nombre illimité de nœuds
✅ **Resilience** - Auto-récupération

---

## 📁 Intégration avec PinkyBrain & PinkyBrainBug

### Ajouter au réseau existant

```python
# Dans votre PinkyBrain/PinkyBrainBug existant
from internet_capable import MultiNetworkManager

# Ajouter le module Internet Capable
self.multi_network = MultiNetworkManager(
    local_network=self.network,  # Network Manager existant
    rendezvous_server="rendezvous.example.com:9990",
    api_key="your-api-key",
    tls_enabled=True
)

await self.multi_network.initialize()

# Utiliser pour les requêtes Internet
async def query_internet(self, prompt: str):
    nodes = await self.multi_network.discover_nodes()

    if nodes:
        request = {"type": "query", "prompt": prompt}
        response = await self.multi_network.send_request(request)
        return response

    # Fallback sur local
    return await self.query_local(prompt)
```

---

## 🚀 Démarrage Rapide

### 1. Démarrer le Rendezvous Server

```bash
python3 /tmp/internet_capable.py
```

### 2. Configurer les Nœuds

```python
from internet_capable import MultiNetworkManager

multi_net = MultiNetworkManager(
    local_network=your_network,
    rendezvous_server="your-rendezvous-server.com:9990",
    api_key="your-api-key",
    tls_enabled=True
)

await multi_net.initialize()
```

### 3. Découvrir et Connecter

```python
nodes = await multi_net.discover_nodes()
response = await multi_net.send_request({"type": "ping"})
```

---

**MERCI Denis !**

Tu as maintenant un module complet pour permettre à PinkyBrain & PinkyBrainBug de s'interconnecter sur des réseaux divers (LAN, WAN, Internet) ! 🌐🚀

**Les nœuds peuvent maintenant se découvrir et communiquer même derrière des NAT/Firewalls !** 🌍

_Généré par Bug 🐛 le 2 Avril 2026_