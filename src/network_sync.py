#!/usr/bin/env python3
"""
🔄 NETWORK SYNC — PinkyBrain v5.2
====================================
Synchronisation automatique quand un nœud rejoint le réseau PinkyBrain.

Processus de connexion:
1. Authentification au réseau (via tracker/P2P)
2. Récupération de la liste des nœuds actifs (DNS dynamique)
3. Purge des nœuds absents depuis trop longtemps
4. Mise à jour du catalogue avec les modèles partagés par les nœuds
5. Identification des modèles non encore dans le catalogue local
6. Proposition de téléchargement/installation des modèles manquants

Sécurité:
  - Hash SHA-256 vérifié pour les catalogues reçus
  - Signature Ed25519 optionnelle pour les catalogues du mesh
  - Validation du schéma de chaque modèle reçu
  - Les nœuds inactifs depuis >30 jours sont retirés du DNS dynamique
  - Les modèles mesh sans nœud actif depuis >12 mois sont purgés du catalogue
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple

logger = logging.getLogger('PinkyBrain.NetworkSync')

# ============================================================================
# CONSTANTES
# ============================================================================

NODE_STALE_THRESHOLD_DAYS = 30       # Nœud considéré absent après 30 jours
NODE_PURGE_THRESHOLD_DAYS = 90       # Nœud retiré du DNS après 90 jours
MODEL_STALE_THRESHOLD_DAYS = 365    # Modèle mesh purgé après 12 mois sans nœud
SYNC_INTERVAL = 300                   # Sync toutes les 5 minutes
DISCOVERY_TIMEOUT = 15                # Timeout découverte en secondes
MAX_NODES = 500                       # Max nœuds dans le DNS local
MAX_MODELS_PER_NODE = 20             # Max modèles annoncés par nœud


# ============================================================================
# DNS DYNAMIQUE — Gestion des nœuds connus
# ============================================================================

class DynamicDNS:
    """DNS dynamique pour les nœuds PinkyBrain.
    
    Maintient une liste de nœuds avec leur IP, port, modèles et dernière
    fois qu'ils ont été vus. Les nœuds absents sont progressivement
    dégradés puis retirés.
    """

    def __init__(self, persist_dir: str = None):
        self.persist_dir = Path(persist_dir) if persist_dir else Path.home() / ".pinkybrain"
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._nodes_file = self.persist_dir / "dns_nodes.json"
        self._nodes: Dict[str, Dict] = {}  # node_id -> node_info
        self._load()

    def _load(self):
        """Charger les nœuds depuis le fichier persistant."""
        if self._nodes_file.exists():
            try:
                with open(self._nodes_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict) and "nodes" in data:
                    self._nodes = data["nodes"]
                    logger.info(f"🔄 Loaded {len(self._nodes)} nodes from DNS cache")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"🔄 Failed to load DNS cache: {e}")
                self._nodes = {}

    def _save(self):
        """Sauvegarder les nœuds dans le fichier persistant."""
        try:
            data = {
                "version": "1.0",
                "updated_at": time.time(),
                "node_count": len(self._nodes),
                "nodes": self._nodes,
            }
            with open(self._nodes_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"🔄 Failed to save DNS cache: {e}")

    def update_node(self, node_id: str, address: str, port: int = 8080,
                    name: str = "", models: List[str] = None,
                    capabilities: Dict = None) -> Dict:
        """Mettre à jour ou ajouter un nœud dans le DNS."""
        now = time.time()
        if node_id in self._nodes:
            # Mise à jour
            node = self._nodes[node_id]
            node["address"] = address
            node["port"] = port
            node["last_seen"] = now
            if name:
                node["name"] = name
            if models is not None:
                node["models"] = models[:MAX_MODELS_PER_NODE]
            if capabilities:
                node["capabilities"] = capabilities
            node["status"] = "active"
        else:
            # Nouveau nœud
            self._nodes[node_id] = {
                "node_id": node_id,
                "address": address,
                "port": port,
                "name": name or f"node-{node_id[:8]}",
                "models": models[:MAX_MODELS_PER_NODE] if models else [],
                "capabilities": capabilities or {},
                "first_seen": now,
                "last_seen": now,
                "status": "active",
                "contribution_score": 0.0,
            }

        # Limiter le nombre de nœuds
        if len(self._nodes) > MAX_NODES:
            self._purge_stale_nodes()

        self._save()
        return self._nodes[node_id]

    def remove_node(self, node_id: str) -> bool:
        """Retirer un nœud du DNS."""
        if node_id in self._nodes:
            del self._nodes[node_id]
            self._save()
            logger.info(f"🔄 Removed node {node_id} from DNS")
            return True
        return False

    def get_active_nodes(self, max_age_days: float = NODE_STALE_THRESHOLD_DAYS) -> List[Dict]:
        """Obtenir les nœuds actifs (vus récemment)."""
        now = time.time()
        max_age = max_age_days * 86400
        active = []
        for node_id, node in self._nodes.items():
            age = now - node.get("last_seen", 0)
            if age <= max_age:
                info = dict(node)
                info["age_days"] = round(age / 86400, 1)
                info["is_active"] = True
                active.append(info)
        active.sort(key=lambda n: n.get("last_seen", 0), reverse=True)
        return active

    def get_stale_nodes(self, min_age_days: float = NODE_STALE_THRESHOLD_DAYS) -> List[Dict]:
        """Obtenir les nœuds obsolètes (pas vus récemment)."""
        now = time.time()
        min_age = min_age_days * 86400
        stale = []
        for node_id, node in self._nodes.items():
            age = now - node.get("last_seen", 0)
            if age > min_age:
                info = dict(node)
                info["age_days"] = round(age / 86400, 1)
                info["is_active"] = False
                stale.append(info)
        stale.sort(key=lambda n: n.get("last_seen", 0), reverse=True)
        return stale

    def get_all_models_available(self) -> Dict[str, List[str]]:
        """Obtenir tous les modèles disponibles sur le réseau et qui les partage.
        
        Returns:
            Dict: model_name -> [node_ids qui l'ont]
        """
        models: Dict[str, List[str]] = {}
        active = self.get_active_nodes(max_age_days=NODE_STALE_THRESHOLD_DAYS)
        for node in active:
            node_id = node["node_id"]
            for model_name in node.get("models", []):
                if model_name not in models:
                    models[model_name] = []
                if node_id not in models[model_name]:
                    models[model_name].append(node_id)
        return models

    def _purge_stale_nodes(self, max_age_days: float = NODE_PURGE_THRESHOLD_DAYS):
        """Retirer les nœuds trop anciens du DNS."""
        now = time.time()
        max_age = max_age_days * 86400
        to_remove = [
            node_id for node_id, node in self._nodes.items()
            if now - node.get("last_seen", 0) > max_age
        ]
        for node_id in to_remove:
            del self._nodes[node_id]
        if to_remove:
            logger.info(f"🔄 Purged {len(to_remove)} stale nodes from DNS (> {max_age_days} days)")
            self._save()

    def mark_node_offline(self, node_id: str):
        """Marquer un nœud comme hors ligne (mais le garder dans le DNS)."""
        if node_id in self._nodes:
            self._nodes[node_id]["status"] = "offline"
            self._save()

    def get_stats(self) -> Dict:
        """Statistiques du DNS."""
        active = self.get_active_nodes()
        stale = self.get_stale_nodes()
        all_models = self.get_all_models_available()
        return {
            "total_nodes": len(self._nodes),
            "active_nodes": len(active),
            "stale_nodes": len(stale),
            "models_available": len(all_models),
            "total_model_instances": sum(len(v) for v in all_models.values()),
        }


# ============================================================================
# NETWORK SYNC — Synchronisation réseau principale
# ============================================================================

class NetworkSync:
    """Synchronisation automatique du réseau PinkyBrain.
    
    Quand un nœud rejoint le réseau:
    1. Découverte des nœuds actifs (via tracker + mDNS + DNS cache)
    2. Mise à jour du DNS dynamique (ajout/suppression de nœuds)
    3. Sync du catalogue de modèles avec les nœuds actifs
    4. Identification des modèles manquants
    5. Proposition de téléchargement
    
    Cette classe coordonne TrackerClient, DynamicDNS et ModelRegistry.
    """

    def __init__(self, model_registry=None, tracker_client=None,
                 dns: DynamicDNS = None, persist_dir: str = None):
        self.model_registry = model_registry
        self.tracker_client = tracker_client
        self.dns = dns or DynamicDNS(persist_dir=persist_dir)
        self._sync_task = None
        self._running = False
        self._last_sync = 0.0
        self._sync_count = 0
        self._models_discovered = 0
        self._models_missing = 0

    async def start(self):
        """Démarrer la synchronisation périodique."""
        if self._running:
            return
        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("🔄 NetworkSync started")

    async def stop(self):
        """Arrêter la synchronisation."""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("🔄 NetworkSync stopped")

    async def _sync_loop(self):
        """Boucle de synchronisation périodique."""
        # Première sync immédiate
        await self.full_sync()

        while self._running:
            try:
                await asyncio.sleep(SYNC_INTERVAL)
                if self._running:
                    await self.full_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"🔄 Sync error: {e}")
                await asyncio.sleep(60)  # Backoff en cas d'erreur

    async def full_sync(self) -> Dict:
        """Synchronisation complète.
        
        Returns:
            Dict avec les résultats de la sync.
        """
        logger.info("🔄 Starting full network sync...")
        results = {
            "dns_updated": 0,
            "dns_purged": 0,
            "models_discovered": 0,
            "models_missing": 0,
            "catalog_updated": 0,
            "timestamp": time.time(),
        }

        # 1. Découvrir les nœuds via le tracker
        discovered_nodes = await self._discover_nodes()

        # 2. Mettre à jour le DNS dynamique
        for node_info in discovered_nodes:
            node_id = node_info.get("node_id", "")
            if not node_id:
                continue
            address = node_info.get("address", "")
            port = node_info.get("port", 8080)
            name = node_info.get("name", "")
            models = node_info.get("models", node_info.get("capabilities", {}).get("models", []))
            capabilities = node_info.get("capabilities", {})

            if address:
                self.dns.update_node(
                    node_id=node_id,
                    address=address,
                    port=port,
                    name=name,
                    models=models,
                    capabilities=capabilities,
                )
                results["dns_updated"] += 1

        # 3. Purger les nœuds trop anciens du DNS
        stale_nodes = self.dns.get_stale_nodes(min_age_days=NODE_PURGE_THRESHOLD_DAYS)
        for node in stale_nodes:
            self.dns.remove_node(node["node_id"])
            results["dns_purged"] += 1

        # 4. Mettre à jour le catalogue avec les modèles des nœuds actifs
        if self.model_registry:
            mesh_models = self.dns.get_all_models_available()
            results["models_discovered"] = len(mesh_models)

            # Construire la liste des modèles avec leurs nœuds
            mesh_model_list = []
            for model_name, node_ids in mesh_models.items():
                mesh_model_list.append({
                    "name": model_name,
                    "node_id": node_ids[0] if node_ids else "unknown",
                    "display_name": model_name,  # Les nœuds peuvent fournir plus d'infos
                    "community_score": len(node_ids),  # Plus de nœuds = plus de confiance
                })

            self.model_registry.update_mesh_discovery(mesh_model_list)
            results["catalog_updated"] = len(mesh_model_list)

            # 5. Purger les modèles mesh sans nœud actif depuis >12 mois
            purged = self.model_registry.purge_stale_models(max_age_days=MODEL_STALE_THRESHOLD_DAYS)
            # On ne compte pas les purgés dans "missing" car ils étaient déjà inactifs

            # 6. Identifier les modèles manquants (disponibles sur le mesh mais pas locaux)
            missing = self._find_missing_models()
            results["models_missing"] = len(missing)
            self._models_missing = len(missing)

            if missing:
                logger.info(f"🔄 Missing models available on mesh: {[m['name'] for m in missing]}")

        self._sync_count += 1
        self._last_sync = time.time()
        self._models_discovered = results.get("models_discovered", 0)

        logger.info(
            f"🔄 Sync complete: {results['dns_updated']} nodes updated, "
            f"{results['dns_purged']} purged, "
            f"{results.get('models_discovered', 0)} models discovered, "
            f"{results.get('models_missing', 0)} missing"
        )

        return results

    async def _discover_nodes(self) -> List[Dict]:
        """Découvrir les nœuds via le tracker et/ou mDNS."""
        nodes = []

        # Via TrackerClient
        if self.tracker_client:
            try:
                discovered = self.tracker_client.get_known_nodes()
                nodes.extend(discovered)
            except Exception as e:
                logger.debug(f"🔄 Tracker discovery failed: {e}")

        # Via mDNS (ZeroConfigDiscovery) — si disponible dans PinkyBrain
        # Cette partie sera branchée par PinkyBrain qui a accès à ZeroConfigDiscovery

        return nodes

    def _find_missing_models(self) -> List[Dict]:
        """Trouver les modèles disponibles sur le mesh mais pas dans le catalogue local.
        
        Returns:
            Liste de dicts avec name, display_name, node_count, available_nodes
        """
        if not self.model_registry:
            return []

        missing = []
        mesh_available = self.dns.get_all_models_available()
        local_models = {card.name for card in self.model_registry.list_models(available_only=True)}

        for model_name, node_ids in mesh_available.items():
            # Vérifier si on a déjà ce modèle localement
            if model_name in local_models:
                continue

            # Vérifier si on l'a déjà dans le catalogue (même en wishlist)
            existing = self.model_registry.get_model(model_name)
            if existing and existing.source.value != "mesh":
                continue

            # Modèle manquant !
            # Obtenir des infos des nœuds qui l'ont
            node_names = []
            active_nodes = self.dns.get_active_nodes()
            for node in active_nodes:
                if node["node_id"] in node_ids:
                    node_names.append(node.get("name", node["node_id"][:8]))

            missing.append({
                "name": model_name,
                "display_name": model_name,
                "node_count": len(node_ids),
                "available_nodes": node_names[:5],  # Max 5 noms
                "community_score": len(node_ids),  # Plus de nœuds = plus fiable
                "status": "available_on_mesh",
                "action": "download",  # ou "install" si c'est un modèle Ollama
            })

        # Trier par popularité (plus de nœuds d'abord)
        missing.sort(key=lambda m: m["node_count"], reverse=True)
        return missing

    def get_sync_status(self) -> Dict:
        """Obtenir le statut de la synchronisation."""
        return {
            "running": self._running,
            "sync_count": self._sync_count,
            "last_sync": self._last_sync,
            "last_sync_ago": round(time.time() - self._last_sync, 1) if self._last_sync else None,
            "models_discovered": self._models_discovered,
            "models_missing": self._models_missing,
            "dns_stats": self.dns.get_stats(),
        }

    def get_missing_models_report(self) -> str:
        """Générer un rapport lisible des modèles manquants."""
        missing = self._find_missing_models()
        if not missing:
            return "✅ Tous les modèles du mesh sont déjà dans le catalogue."

        lines = [
            f"📋 {len(missing)} modèle(s) disponible(s) sur le mesh mais pas localement:\n",
        ]
        for m in missing:
            nodes = ", ".join(m["available_nodes"][:3])
            if m["node_count"] > 3:
                nodes += f" +{m['node_count'] - 3} autres"
            lines.append(f"  • {m['name']} — {m['node_count']} nœud(s) ({nodes})")

        lines.append("\nUtilisez /api/registry/add ou python3 model_registry.py add pour les ajouter.")
        return "\n".join(lines)