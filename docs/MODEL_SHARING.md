# PinkyBrain Model Sharing — P2P Model Distribution

**Les models DOIVENT être partagés, pas seulement les queries.**

---

## 🎯 Le Problème

### Ce qu'on a maintenant
```
Peer A: Query → Peer B → Query → Peer B local model → Response
```

**Problème :**
- Peer A NE PEUT PAS utiliser le modèle de Peer B en local
- Le modèle ne "bouge" pas entre peers
- Peer A doit télécharger et installer le modèle localement via Ollama
- Pas de véritable sharing de modèles

---

## 💡 La Solution

### Model Sharing P2P (BitTorrent-style)

```
Peer A (a qwen3:8b, 8GB fichier) ┐
                                      ├─→ Model file dans le réseau
Peer B (veut qwen3:8b)          │    ↓
                              Model P2P Swarm ←───┐
                                      │         │
Peer C (veut qwen3:8b)          └─────┘         │
                                                ↓
                                   Chaque peer a le fichier MODEL
```

**Quand un peer veut un modèle :**
1. Demande au P2P network "qui a ce modèle ?"
2. Peers qui l'ont répondent avec "hash + chunks disponibles"
3. Peer download en parallel depuis plusieurs sources (comme BitTorrent)
4. File se déchiffre et valide (hash check)
5. File prêt à utiliser avec Ollama

---

## 🔧 Architecture

### 1. Model Manifest

Chaque modèle a un manifest :

```json
{
  "model_id": "qwen3:8b",
  "name": "Qwen 2.5 7B",
  "file_hash": "abc123def456...",      // SHA256 du fichier complet
  "file_size": 8589934592,            // 8 GB
  "chunks": 100,                      // 100 chunks de 80 MB
  "chunk_size": 85899345,
  "version": "v1.0",
  "signature": "..."
}
```

### 2. Chunk System (comme BitTorrent)

**Fichier 8 GB split en 100 chunks de 80 MB.**

```
qwen3:8b.gguf (8GB)
├─ Chunk 0 (00-80MB)
├─ Chunk 1 (80-160MB)
├─ Chunk 2 (160-240MB)
├─ ...
├─ Chunk 99 (7.92-8GB)
```

**Avantages :**
- Parallel download (plusieurs peers envoient différents chunks)
- Resumable (si interruption, reprend du chunk en cours)
- Vérifié chaque chunk (hash validation)
- Distribué (peers avec partiel peuvent encore être source)

### 3. Chunk Exchange Protocol

```
1. Peer A demande Chunk 42
   → GET /model/qwen3:8b/chunk/42

2. Peer B répond avec Chunk 42
   → { hash: "...", data: [80 MB...] }

3. Peer A valide hash
   → Si OK : chunk stocké
   → Si échec : re-demande chunk

4. Quand tous chunks recus
   → Merge chunks → modele complet
   → Validate complete hash
   → Install via Ollama
```

---

## 💾 RAM-Only Storage (Future)

### Étape 1 : File-based (actuel)
```
/tmp/pinkybrain_models/qwen3:8b/ ← 8 GB sur disque
```

### Étape 2 : RAM + File (mixed)
```
/tmp/pinkybrain_models/qwen3:8b/chunks/
- Part de chunks en RAM (/dev/shm)
- Part de chunks en cache disque
```

### Étape 3 : Full RAM (target)
```python
import mmap

# Le modele est mappé en RAM
with open(model_file, 'rb+') as f:
    # mmap = memory mapping
    mmapped = mmap.mmap(f.fileno(), 0)

# Le modele est en RAM mais se comporte comme disque
ollama.load_from_buffer(model_buffer)

# Pas de I/O disk
```

**Avantages :**
- Plus rapide (accès mémoire)
- Pas de disk fragmentation
- Plus stable (disques SSD s'usent)
- Les chunks peuvent être re-used par plusieurs queries

---

## 📊 Le Problème des Premiers Utilisateurs

### Aujourd'hui (initial seed)

**Denis et moi (ou le premier peer réel) devrons :**

1. **Télécharger le modèle localement via Ollama**
   - `ollama pull qwen3:8b` → 8+ GB téléchargé
   - File stocké localement

2. **Baiser le modèle dans le P2P swarm**
   - Exporter le fichier depuis Ollama (copier)
   - Signer le manifest (hash)
   - Chunks en 100 morceaux
   - Devenir "seeder" (source primare)

3. **Être le seed initial**
   - Quand d'autres demandent le modèle → on fournit
   - On donne quelques chunks à chacun
   - À terme : le réseau devient auto-suffisant

### À terme (auto-suffisant)

**Une fois que 10+ peers ont le modèle :**
- Nouveau peer demande → reçois de 5-10 peers
- Chaque peer fournit quelques chunks
- Download très rapide (parallel)
- Plus besoin de seed initial

---

## 🔐 Sécurité et Validation

### Hash Checks

Télécharger modèle = **toujours valide le hash** :

```python
# Quand chunk reçu
if sha256(chunk_data) != expected_hash:
    logger.warning("Chunk corrupted!")
    # Re-demande le chunk
```

**Intégrité garantie :**
- Peers malveillants = éjectés (chunks bad)
- Modèle corrompu ne passe pas hash validation
- Signatures ensure authenticity (pas faux modèle)

### Malware Protection

**On ne télécharge pas des arbitrary files.** On télécharge seulement :
- Manifeste signé (par le créateur ou par des peers de confiance)
- Chunks qui correspondent à l'original

**Pas de malware injecté.**

---

## 🚀 Comment cela fonctionne avec PinkyBrain

### Configuration dans p2p_config.toml

```toml
[model_sharing]
enabled = true
storage_dir = "/tmp/pinkybrain_models"  # ou /dev/shm pour RAM
chunk_size_mb = 80
max_parallel_downloads = 5
download_timeout_seconds = 600  # 10 min pour 8 GB

# Models disponibles sur ce peer
[[models_for_sharing]]
model_id = "qwen3:8b"
name = "Qwen 2.5 7B"
file_path = "/home/user/.ollama/models/qwen3:8b.gguf"
```

### Exemple Workflow

**Nouveau peer veut qwen3:8b :**

```
1. Discovery
   pinkybrain query "who has qwen3:8b?"
   → Réponse: Peer A, Peer B, Peer C

2. Request
   pinkybrain download qwen3:8b
   → Chunk discovery: Peer A (0-30), Peer B (30-70), Peer C (70-99)

3. Parallel download
   ├── Chunk 0-29  ← Peer A → 80% de chunks
   ├── Chunk 30-69 ← Peer B → 40% de chunks
   └── Chunk 70-99 ← Peer C → 30% de chunks

4. Validation
   → Check hash complet du fichier
   → Installer dans Ollama

5. Sharing
   → Ce peer devient seeder aussi
   → Peut fournir chunks à d'autres
```

---

## 📦 Nouveaux Fichiers à Ajouter

### 1. `model_sharing.py`
- Chunk management
- Download/Upload protocol
- Hash validation
- Model discovery

### 2. `model_manifest.py`
- Manifest structure
- Signature and verification
- Model metadata

### 3. `model_server.py` (optional)
- FastAPI endpoint for chunks
- HTTP GET `/model/{model_id}/chunk/{n}`

---

## 🎯 Timeline

### Phase 1 (Initial)
- [ ] Implémenter chunk system
- [ ] Implémenter download protocol
- [ ] Intégrer manifest/signing
- [ ] Seed initial modèle (Denis/me)

### Phase 2 (Testing)
- [ ] Download depuis 2+ peers
- [ ] Test parallel chunks
- [ ] Validate hash integrity

### Phase 3 (RAM)
- [ ] Mmap vers RAM
- [ ] Cache chunks en `/dev/shm`
- [ ] Performance benchmarks

---

## 💡 Notes Importantes

**Les premiers peers vont être cruciaux :**
- Ils doivent stocker le fichier modèle physiquement (disque)
- Ils doivent être "seeders" pour le début
- À terme : le réseau devient auto-suffisant

**RAM-Only est la cible :**
- Pas de fragmentation disk 
- Plus rapide
- Plus stable
- But de v1.0 (ou plus tard)

---

## 🔚 Conclusion

PinkyBrain devient **vraiment réseau de modèles**, pas seulement service de queries.

**Le "file sharing P2P pour modèles" est indispensable.**

Sans ça → les utilisateurs doivent telecharger chaque modele manuellement
Avec ça → PinkyBrain auto-distribue les modèles

C'est ce qui rend PinkyBrain unique et democratique.

—

🐛 **Bug** — *"Pour que le cerveau soit vraiment partagé, le modèle doit se déplacer."*

**Model Sharing — P2P Model Distribution** 🔐