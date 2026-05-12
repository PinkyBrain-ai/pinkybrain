#!/usr/bin/env python3
"""
📚 MODEL REGISTRY — PinkyBrain v5.2
=====================================
Catalogue de modèles avec métadonnées riches.

Permet de:
1. Déclarer les modèles qu'on veut utiliser et/ou partager
2. Lister les modèles disponibles sur le réseau public avec infos détaillées
3. Ajouter des modèles personnalisés avec profil complet
4. Découvrir les modèles des pairs avec capacités, puissance, utilité
5. Catégoriser les modèles (local, mesh, cloud, à installer)

Architecture:
- ModelRegistry: registre central, persiste en JSON
- ModelCard: fiche détaillée d'un modèle (nom, spécialités, taille, RAM requise, etc.)
- ModelSource: enum des sources (local, mesh, cloud, wishlist)
- API endpoints: /api/registry/* pour gestion complète
"""

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger('PinkyBrain.ModelRegistry')

# ============================================================================
# CONSTANTES
# ============================================================================

DEFAULT_BASE_DIR = os.path.expanduser("~/.pinkybrain")
REGISTRY_FILE = "model_registry.json"
CATALOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "model_catalog.json")
CATALOG_HASH_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "model_catalog.sha256")
CATALOG_SIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "model_catalog.sig")

# Seuil de sécurité : taille max du catalogue (1 MB)
MAX_CATALOG_SIZE = 1 * 1024 * 1024

# Clé publique Ed25519 de confiance pour la vérification des signatures
# À générer avec: python3 -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; key = Ed25519PrivateKey.generate(); print('PRIVATE:', key.private_bytes_raw().hex()); print('PUBLIC:', key.public_key().public_bytes_raw().hex())"
# La clé privée est gardée secrète, seule la publique est ici.
TRUSTED_PUBLIC_KEY_HEX: Optional[str] = None  # À configurer lors du déploiement

# Catégories de taille de modèle
SIZE_CATEGORIES = {
    "tiny": {"params": "<3B", "ram_gb": 2, "vram_gb": 0, "label": "Tiny", "icon": "🐜"},
    "small": {"params": "3-8B", "ram_gb": 8, "vram_gb": 4, "label": "Small", "icon": "🐹"},
    "medium": {"params": "8-35B", "ram_gb": 24, "vram_gb": 12, "label": "Medium", "icon": "🐱"},
    "large": {"params": "35-70B", "ram_gb": 48, "vram_gb": 24, "label": "Large", "icon": "🦁"},
    "xl": {"params": "70B+", "ram_gb": 96, "vram_gb": 48, "label": "XL", "icon": "🐋"},
}

# Niveaux de qualité
QUALITY_LEVELS = {
    1: "Basique — réponses courtes, erreurs fréquentes",
    2: "Limité — convient pour des tâches simples",
    3: "Correct — acceptable pour un usage général",
    4: "Bon — fiable pour la plupart des tâches",
    5: "Moyen — bon rapport qualité/puissance",
    6: "Satisfaisant — robuste sur ses spécialités",
    7: "Très bon — excellent dans son domaine",
    8: "Excellent — haut niveau de qualité",
    9: "Exceptionnel — quasi-optimal",
    10: "État de l'art — meilleur dans sa catégorie",
}

# Niveaux de vitesse
SPEED_LEVELS = {
    1: "Très lent (>30s/token)",
    2: "Lent (15-30s/token)",
    3: "Modéré (8-15s/token)",
    4: "Acceptable (4-8s/token)",
    5: "Moyen (2-4s/token)",
    6: "Rapide (1-2s/token)",
    7: "Très rapide (0.5-1s/token)",
    8: "Rapide (<0.5s/token)",
    9: "Très rapide (<0.3s/token)",
    10: "Instantané (<0.1s/token)",
}


# ============================================================================
# ÉNUMÉRATIONS
# ============================================================================

class ModelSource(Enum):
    """Source d'un modèle."""
    LOCAL = "local"          # Installé localement (Ollama)
    MESH = "mesh"            # Disponible via le réseau P2P
    CLOUD = "cloud"          # API cloud (OpenAI, Anthropic, etc.)
    WISHLIST = "wishlist"    # À installer / wishlist
    INSTALLING = "installing"  # En cours d'installation


class ModelStatus(Enum):
    """Statut d'un modèle."""
    READY = "ready"                  # Prêt à l'emploi
    DOWNLOADING = "downloading"       # En cours de téléchargement
    SHARING = "sharing"              # Partagé sur le mesh
    OFFLINE = "offline"              # Non disponible
    ERROR = "error"                  # Erreur
    WISHLIST = "wishlist"            # Souhaité mais pas installé


# ============================================================================
# MODEL CARD — Fiche détaillée d'un modèle
# ============================================================================

@dataclass
class ModelCard:
    """Fiche complète d'un modèle avec toutes ses caractéristiques."""
    # Identité
    name: str
    display_name: str = ""
    description: str = ""
    long_description: str = ""
    
    # Classification
    source: ModelSource = ModelSource.LOCAL
    status: ModelStatus = ModelStatus.READY
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    # Performances
    quality_rating: int = 5
    speed_rating: int = 5
    context_window: int = 8192
    
    # Ressources
    size_category: str = "small"
    params_count: str = ""
    ram_required_gb: float = 4.0
    vram_required_gb: float = 0.0
    disk_size_gb: float = 0.0
    
    # Spécialités
    strengths: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    best_for: List[str] = field(default_factory=list)
    not_for: List[str] = field(default_factory=list)
    
    # Multilingual
    languages: List[str] = field(default_factory=lambda: ["en"])
    primary_language: str = "en"
    
    # Technique
    provider: str = "ollama"
    architecture: str = ""
    license: str = ""
    quantization: str = ""
    
    # Mesh & partage
    shared: bool = False
    downloadable: bool = False
    mesh_nodes: List[str] = field(default_factory=list)
    last_seen: float = 0.0                                  # Dernière fois qu'un nœud mesh l'a annoncé (0 = jamais vu sur le mesh)
    
    # Score & confiance
    community_score: float = 0.0
    trust_score: float = 0.0
    downloads: int = 0
    
    # Métadonnées
    added_at: float = 0.0
    updated_at: float = 0.0
    last_used: float = 0.0
    use_count: int = 0
    notes: str = ""
    
    # Prix (si cloud)
    price_per_million_input: float = 0.0
    price_per_million_output: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Sérialiser en dict."""
        return {
            "name": self.name,
            "display_name": self.display_name or self.name,
            "description": self.description,
            "long_description": self.long_description,
            "source": self.source.value,
            "status": self.status.value,
            "categories": self.categories,
            "tags": self.tags,
            "quality_rating": self.quality_rating,
            "speed_rating": self.speed_rating,
            "context_window": self.context_window,
            "size_category": self.size_category,
            "params_count": self.params_count,
            "ram_required_gb": self.ram_required_gb,
            "vram_required_gb": self.vram_required_gb,
            "disk_size_gb": self.disk_size_gb,
            "strengths": self.strengths,
            "limitations": self.limitations,
            "best_for": self.best_for,
            "not_for": self.not_for,
            "languages": self.languages,
            "primary_language": self.primary_language,
            "provider": self.provider,
            "architecture": self.architecture,
            "license": self.license,
            "quantization": self.quantization,
            "shared": self.shared,
            "downloadable": self.downloadable,
            "mesh_nodes": self.mesh_nodes,
            "last_seen": self.last_seen,
            "community_score": self.community_score,
            "trust_score": self.trust_score,
            "downloads": self.downloads,
            "added_at": self.added_at,
            "updated_at": self.updated_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
            "notes": self.notes,
            "price_per_million_input": self.price_per_million_input,
            "price_per_million_output": self.price_per_million_output,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelCard':
        """Désérialiser depuis un dict."""
        try:
            source = ModelSource(data.get("source", "local"))
        except ValueError:
            source = ModelSource.LOCAL
        try:
            status = ModelStatus(data.get("status", "ready"))
        except ValueError:
            status = ModelStatus.READY
        
        return cls(
            name=data.get("name", "unknown"),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            long_description=data.get("long_description", ""),
            source=source,
            status=status,
            categories=data.get("categories", []),
            tags=data.get("tags", []),
            quality_rating=data.get("quality_rating", 5),
            speed_rating=data.get("speed_rating", 5),
            context_window=data.get("context_window", 8192),
            size_category=data.get("size_category", "small"),
            params_count=data.get("params_count", ""),
            ram_required_gb=data.get("ram_required_gb", 4.0),
            vram_required_gb=data.get("vram_required_gb", 0.0),
            disk_size_gb=data.get("disk_size_gb", 0.0),
            strengths=data.get("strengths", []),
            limitations=data.get("limitations", []),
            best_for=data.get("best_for", []),
            not_for=data.get("not_for", []),
            languages=data.get("languages", ["en"]),
            primary_language=data.get("primary_language", "en"),
            provider=data.get("provider", "ollama"),
            architecture=data.get("architecture", ""),
            license=data.get("license", ""),
            quantization=data.get("quantization", ""),
            shared=data.get("shared", False),
            downloadable=data.get("downloadable", False),
            mesh_nodes=data.get("mesh_nodes", []),
            last_seen=data.get("last_seen", 0.0),
            community_score=data.get("community_score", 0.0),
            trust_score=data.get("trust_score", 0.0),
            downloads=data.get("downloads", 0),
            added_at=data.get("added_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
            last_used=data.get("last_used", 0.0),
            use_count=data.get("use_count", 0),
            notes=data.get("notes", ""),
            price_per_million_input=data.get("price_per_million_input", 0.0),
            price_per_million_output=data.get("price_per_million_output", 0.0),
        )
    
    def get_size_icon(self) -> str:
        """Icône pour la taille du modèle."""
        return SIZE_CATEGORIES.get(self.size_category, SIZE_CATEGORIES["small"])["icon"]
    
    def get_quality_label(self) -> str:
        """Label pour la qualité."""
        return QUALITY_LEVELS.get(self.quality_rating, "Inconnu")
    
    def get_speed_label(self) -> str:
        """Label pour la vitesse."""
        return SPEED_LEVELS.get(self.speed_rating, "Inconnu")
    
    def summary(self) -> str:
        """Résumé court du modèle."""
        source_icon = {
            "local": "🏠", "mesh": "🌐", "cloud": "☁️",
            "wishlist": "📋", "installing": "⏳"
        }.get(self.source.value, "❓")
        shared_icon = "📡" if self.shared else ""
        quality_bar = "█" * self.quality_rating + "░" * (10 - self.quality_rating)
        speed_bar = "█" * self.speed_rating + "░" * (10 - self.speed_rating)
        
        lines = [
            f"{source_icon} {self.display_name or self.name} {shared_icon}",
            f"   {self.description}",
            f"   Qualité: [{quality_bar}] {self.quality_rating}/10 — {self.get_quality_label()}",
            f"   Vitesse: [{speed_bar}] {self.speed_rating}/10 — {self.get_speed_label()}",
            f"   Contexte: {self.context_window:,} tokens | Taille: {self.size_category} ({self.params_count or '?'})",
            f"   RAM: {self.ram_required_gb}GB | VRAM: {self.vram_required_gb}GB | Disque: {self.disk_size_gb}GB",
            f"   Langues: {', '.join(self.languages)}",
        ]
        if self.strengths:
            lines.append(f"   ✅ {', '.join(self.strengths[:3])}")
        if self.limitations:
            lines.append(f"   ⚠️  {', '.join(self.limitations[:3])}")
        if self.best_for:
            lines.append(f"   Idéal pour: {', '.join(self.best_for[:3])}")
        
        return "\n".join(lines)


# ============================================================================
# ============================================================
# CATALOGUE — Chargé depuis config/model_catalog.json
# ============================================================
# VÉRIFICATION D'INTÉGRITÉ DU CATALOGUE
# ============================================================

def compute_catalog_hash(catalog_path: str) -> str:
    """Calculer le hash SHA-256 du fichier catalogue.
    
    Retourne le hash hex en minuscules.
    """
    sha256 = hashlib.sha256()
    with open(catalog_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_catalog_hash(catalog_path: str, hash_path: str) -> bool:
    """Vérifier l'intégrité du catalogue contre son fichier de hash.
    
    Si le fichier .sha256 n'existe pas, on le crée (première exécution).
    Si il existe, on vérifie que le hash correspond.
    
    Returns:
        True si le catalogue est intact (ou si c'est la première exécution)
        False si le hash ne correspond pas (fichier altéré !)
    """
    # Calculer le hash actuel
    current_hash = compute_catalog_hash(catalog_path)
    
    if not os.path.exists(hash_path):
        # Première exécution : créer le fichier de hash
        try:
            with open(hash_path, "w", encoding="utf-8") as f:
                f.write(f"{current_hash}  model_catalog.json\n")
            logger.info(f"📚 Created catalog hash file: {hash_path}")
            return True
        except OSError as e:
            logger.error(f"📚 Cannot write catalog hash file: {e}")
            return True  # On laisse passer si on ne peut pas écrire
    
    # Lire le hash attendu
    try:
        with open(hash_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            # Format: <hash>  <filename> ou juste <hash>
            expected_hash = content.split()[0] if content else ""
    except OSError:
        expected_hash = ""
    
    if expected_hash.lower() != current_hash.lower():
        logger.error(
            f"🚨 CATALOG INTEGRITY CHECK FAILED!\n"
            f"   Expected: {expected_hash}\n"
            f"   Got:      {current_hash}\n"
            f"   The catalog file may have been tampered with!"
        )
        return False
    
    logger.info(f"📚 Catalog integrity verified: SHA-256 matches")
    return True


def verify_catalog_signature(catalog_path: str, sig_path: str, public_key_hex: Optional[str] = None) -> bool:
    """Vérifier la signature Ed25519 du catalogue.
    
    Args:
        catalog_path: Chemin vers le catalogue JSON
        sig_path: Chemin vers le fichier de signature
        public_key_hex: Clé publique Ed25519 en hex (optionnel, sinon utilise TRUSTED_PUBLIC_KEY_HEX)
    
    Returns:
        True si la signature est valide ou si pas de signature à vérifier
        False si la signature est invalide
    """
    pub_key_hex = public_key_hex or TRUSTED_PUBLIC_KEY_HEX
    
    # Si pas de clé publique configurée, on ne peut pas vérifier
    if not pub_key_hex:
        logger.debug("📚 No public key configured, skipping signature verification")
        return True
    
    # Si pas de fichier de signature, avertissement mais on laisse passer
    if not os.path.exists(sig_path):
        logger.warning("📚 No signature file found — catalog cannot be verified")
        return True  # Pas bloquant si pas de signature
    
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        
        # Lire la signature
        with open(sig_path, "rb") as f:
            signature = f.read()
        
        # Lire le catalogue
        with open(catalog_path, "rb") as f:
            catalog_data = f.read()
        
        # Charger la clé publique
        pub_key_bytes = bytes.fromhex(pub_key_hex)
        public_key = Ed25519PublicKey.from_public_bytes(pub_key_bytes)
        
        # Vérifier
        try:
            public_key.verify(signature, catalog_data)
            logger.info("📚 Catalog signature verified: Ed25519 valid")
            return True
        except InvalidSignature:
            logger.error(
                f"🚨 CATALOG SIGNATURE INVALID!\n"
                f"   The catalog file has been modified or the signature is wrong!"
            )
            return False
    
    except ImportError:
        logger.warning("📚 cryptography library not installed — cannot verify signature")
        return True  # Pas bloquant si la lib n'est pas là
    except Exception as e:
        logger.error(f"📚 Signature verification error: {e}")
        return True  # Permissif en cas d'erreur technique


def validate_catalog_schema(data: List[Dict[str, Any]]) -> bool:
    """Valider le schéma du catalogue pour éviter les injections.
    
    Vérifie:
    - C'est bien une liste
    - Chaque entrée a un nom valide
    - Pas de clés inattendues dangereuses
    - Pas de code exécutable
    - Taille raisonnable des champs texte
    """
    if not isinstance(data, list):
        logger.error("🚨 Catalog validation: not a list")
        return False
    
    # Clés autorisées dans une ModelCard
    allowed_keys = {
        "name", "display_name", "description", "long_description",
        "source", "status", "categories", "tags",
        "quality_rating", "speed_rating", "context_window",
        "size_category", "params_count", "ram_required_gb", "vram_required_gb", "disk_size_gb",
        "strengths", "limitations", "best_for", "not_for",
        "languages", "primary_language",
        "provider", "architecture", "license", "quantization",
        "shared", "downloadable", "mesh_nodes",
        "community_score", "trust_score", "downloads",
        "added_at", "updated_at", "last_used", "use_count", "notes",
        "price_per_million_input", "price_per_million_output",
    }
    
    # Champs texte avec limite de taille
    text_limits = {
        "name": 128, "display_name": 256, "description": 1000,
        "long_description": 5000, "notes": 2000,
        "architecture": 100, "license": 200, "quantization": 50,
        "provider": 100, "primary_language": 10,
    }
    
    # Valeurs autorisées pour source et status
    valid_sources = {"local", "mesh", "cloud", "wishlist", "installing"}
    valid_statuses = {"ready", "downloading", "sharing", "offline", "error", "wishlist"}
    
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            logger.error(f"🚨 Catalog validation: entry {i} is not a dict")
            return False
        
        # Nom obligatoire et valide
        name = entry.get("name", "")
        if not name or not isinstance(name, str):
            logger.error(f"🚨 Catalog validation: entry {i} missing or invalid 'name'")
            return False
        if len(name) > 128 or not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._:/ -]{0,127}$', name):
            logger.error(f"🚨 Catalog validation: entry {i} invalid name '{name}'")
            return False
        
        # Vérifier les clés
        for key in entry:
            if key not in allowed_keys:
                logger.error(f"🚨 Catalog validation: entry '{name}' has unknown key '{key}'")
                return False
        
        # Vérifier les valeurs source/status
        source = entry.get("source", "local")
        if source not in valid_sources:
            logger.error(f"🚨 Catalog validation: entry '{name}' has invalid source '{source}'")
            return False
        status = entry.get("status", "ready")
        if status not in valid_statuses:
            logger.error(f"🚨 Catalog validation: entry '{name}' has invalid status '{status}'")
            return False
        
        # Vérifier la taille des champs texte
        for field, max_len in text_limits.items():
            val = entry.get(field, "")
            if isinstance(val, str) and len(val) > max_len:
                logger.error(f"🚨 Catalog validation: entry '{name}' field '{field}' too long ({len(val)} > {max_len})")
                return False
        
        # Vérifier les listes
        for list_field in ["categories", "tags", "strengths", "limitations", "best_for", "not_for", "languages", "mesh_nodes"]:
            val = entry.get(list_field, [])
            if not isinstance(val, list):
                logger.error(f"🚨 Catalog validation: entry '{name}' field '{list_field}' is not a list")
                return False
            if len(val) > 20:
                logger.error(f"🚨 Catalog validation: entry '{name}' field '{list_field}' has too many items ({len(val)})")
                return False
            for item in val:
                if not isinstance(item, str) or len(item) > 200:
                    logger.error(f"🚨 Catalog validation: entry '{name}' field '{list_field}' has invalid item")
                    return False
        
        # Vérifier les notes (pas de HTML/JS)
        for text_field in ["description", "long_description", "notes", "display_name"]:
            val = entry.get(text_field, "")
            if isinstance(val, str):
                # Pas de balises HTML ou scripts
                if re.search(r'<[^>]+>', val):
                    logger.error(f"🚨 Catalog validation: entry '{name}' field '{text_field}' contains HTML tags")
                    return False
                # Pas de scripts
                if re.search(r'(?:script|javascript|onerror|onload|eval|exec)', val, re.IGNORECASE):
                    logger.error(f"🚨 Catalog validation: entry '{name}' field '{text_field}' contains suspicious content")
                    return False
        
        # Vérifier les ratings
        for rating_field in ["quality_rating", "speed_rating"]:
            val = entry.get(rating_field, 5)
            if not isinstance(val, (int, float)) or val < 0 or val > 10:
                logger.error(f"🚨 Catalog validation: entry '{name}' field '{rating_field}' invalid: {val}")
                return False
    
    logger.info(f"📚 Catalog schema validated: {len(data)} entries OK")
    return True


def _load_catalog_from_file() -> List[Dict[str, Any]]:
    """Charger le catalogue depuis le fichier JSON externe avec vérification d'intégrité.
    
    Processus de sécurité:
    1. Vérifier la taille du fichier (< MAX_CATALOG_SIZE)
    2. Calculer et vérifier le hash SHA-256
    3. Vérifier la signature Ed25519 (si configurée)
    4. Valider le schéma JSON (pas d'injection)
    5. Charger les données
    
    L'ordre de priorité:
    - config/model_catalog.json (catalogue de référence, hash vérifié)
    - ~/.pinkybrain/model_catalog.json (override utilisateur, hash vérifié si présent)
    """
    catalog_paths = [
        CATALOG_FILE,  # config/model_catalog.json à côté du code
        os.path.join(os.path.expanduser("~/.pinkybrain"), "model_catalog.json"),  # override utilisateur
    ]
    
    for path in catalog_paths:
        if not os.path.exists(path):
            continue
        
        try:
            # 1. Vérifier la taille du fichier
            file_size = os.path.getsize(path)
            if file_size > MAX_CATALOG_SIZE:
                logger.error(f"🚨 Catalog file {path} is too large ({file_size} > {MAX_CATALOG_SIZE} bytes). Skipping.")
                continue
            
            # 2. Vérifier le hash SHA-256
            hash_path = path + ".sha256"  # model_catalog.json.sha256
            if not verify_catalog_hash(path, hash_path):
                logger.error(f"🚨 Catalog integrity check FAILED for {path}. File may be tampered with!")
                continue  # Passer au chemin suivant au lieu de charger un fichier corrompu
            
            # 3. Vérifier la signature Ed25519 (optionnel)
            sig_path = path + ".sig"  # model_catalog.json.sig
            if not verify_catalog_signature(path, sig_path):
                logger.error(f"🚨 Catalog signature INVALID for {path}. File may be tampered with!")
                continue
            
            # 4. Charger et parser le JSON
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                logger.warning(f"📚 Catalog file {path} is not a list, skipping")
                continue
            
            # 5. Valider le schéma
            if not validate_catalog_schema(data):
                logger.error(f"🚨 Catalog schema validation FAILED for {path}. Possible injection!")
                continue
            
            logger.info(f"📚 Loaded catalog from {path}: {len(data)} models (integrity verified)")
            return data
            
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"📚 Error loading catalog from {path}: {e}")
            continue
    
    logger.warning("📚 No valid catalog file found — using empty catalog")
    return []


DEFAULT_CATALOG: List[Dict[str, Any]] = _load_catalog_from_file()

# ============================================================================
# MODEL REGISTRY — Registre central
# ============================================================================

class ModelRegistry:
    """Registre central des modèles — catalogue, wishlist, mesh discovery."""
    
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or DEFAULT_BASE_DIR)
        self._registry_file = self.base_dir / REGISTRY_FILE
        self._cards: Dict[str, ModelCard] = {}
        self._initialized = False
    
    def initialize(self):
        """Initialiser le registre — charge les données existantes et le catalogue par défaut."""
        if self._initialized:
            return
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._load()
        for card_data in DEFAULT_CATALOG:
            name = card_data["name"]
            if name not in self._cards:
                card = ModelCard.from_dict(card_data)
                card.added_at = card.added_at or time.time()
                self._cards[name] = card
        self._save()
        self._initialized = True
        logger.info(f"📚 Model Registry initialized: {len(self._cards)} models")
    
    # ===================================================================
    # OPÉRATIONS CRUD
    # ===================================================================
    
    def add_model(self, card: ModelCard) -> bool:
        if not card.name:
            logger.error("Cannot add model without name")
            return False
        now = time.time()
        if card.name in self._cards:
            existing = self._cards[card.name]
            card.added_at = existing.added_at or now
            card.updated_at = now
            card.use_count = existing.use_count
            card.last_used = existing.last_used
        else:
            card.added_at = now
            card.updated_at = now
        self._cards[card.name] = card
        self._save()
        logger.info(f"📚 Model added: {card.name} ({card.source.value})")
        return True
    
    def remove_model(self, name: str) -> bool:
        if name in self._cards:
            del self._cards[name]
            self._save()
            logger.info(f"📚 Model removed: {name}")
            return True
        return False
    
    def get_model(self, name: str) -> Optional[ModelCard]:
        return self._cards.get(name)
    
    def update_model(self, name: str, updates: Dict[str, Any]) -> bool:
        if name not in self._cards:
            return False
        card = self._cards[name]
        for key, value in updates.items():
            if hasattr(card, key):
                if key == "source":
                    value = ModelSource(value)
                elif key == "status":
                    value = ModelStatus(value)
                setattr(card, key, value)
        card.updated_at = time.time()
        self._save()
        return True
    
    def record_usage(self, name: str):
        if name in self._cards:
            self._cards[name].use_count += 1
            self._cards[name].last_used = time.time()
            self._save()
    
    # ===================================================================
    # REQUÊTES
    # ===================================================================
    
    def list_models(self, source: str = None, category: str = None,
                    tag: str = None, language: str = None,
                    min_quality: int = None, max_size: str = None,
                    shared_only: bool = False, available_only: bool = False,
                    downloadable_only: bool = False,
                    sort_by: str = "quality") -> List[ModelCard]:
        results = list(self._cards.values())
        if source:
            results = [m for m in results if m.source.value == source]
        if category:
            results = [m for m in results if category in m.categories]
        if tag:
            results = [m for m in results if tag in m.tags]
        if language:
            results = [m for m in results if language in m.languages]
        if min_quality:
            results = [m for m in results if m.quality_rating >= min_quality]
        if max_size:
            size_order = ["tiny", "small", "medium", "large", "xl"]
            max_idx = size_order.index(max_size) if max_size in size_order else len(size_order)
            results = [m for m in results if size_order.index(m.size_category) <= max_idx
                       if m.size_category in size_order]
        if shared_only:
            results = [m for m in results if m.shared]
        if available_only:
            results = [m for m in results if m.status == ModelStatus.READY]
        if downloadable_only:
            results = [m for m in results if m.downloadable]
        sort_key = {
            "quality": lambda m: m.quality_rating,
            "speed": lambda m: m.speed_rating,
            "name": lambda m: m.name,
            "size": lambda m: ["tiny", "small", "medium", "large", "xl"].index(m.size_category),
            "use_count": lambda m: m.use_count,
        }.get(sort_by, lambda m: m.quality_rating)
        results.sort(key=sort_key, reverse=(sort_by != "name"))
        return results
    
    def search(self, query: str) -> List[ModelCard]:
        query_lower = query.lower()
        results = []
        for card in self._cards.values():
            searchable = " ".join([
                card.name, card.display_name, card.description,
                card.long_description,
                " ".join(card.categories), " ".join(card.tags),
                " ".join(card.strengths), " ".join(card.best_for),
                " ".join(card.languages), card.provider,
            ]).lower()
            if query_lower in searchable:
                results.append(card)
        results.sort(key=lambda m: m.quality_rating, reverse=True)
        return results
    
    def get_recommendations(self, task: str = None, language: str = None,
                            max_ram_gb: float = None, min_quality: int = None) -> List[ModelCard]:
        candidates = list(self._cards.values())
        candidates = [m for m in candidates if m.status in (ModelStatus.READY, ModelStatus.SHARING)]
        if max_ram_gb:
            candidates = [m for m in candidates if m.ram_required_gb <= max_ram_gb]
        if min_quality:
            candidates = [m for m in candidates if m.quality_rating >= min_quality]
        if language:
            lang_match = [m for m in candidates if language in m.languages]
            if lang_match:
                candidates = lang_match
        if task:
            task_lower = task.lower()
            task_map = {
                "code": "code", "programming": "code", "dev": "code", "développement": "code",
                "conversation": "conversation", "chat": "conversation", "discuter": "conversation",
                "raisonnement": "raisonnement", "reasoning": "raisonnement", "logique": "raisonnement",
                "créatif": "creatif", "creative": "creatif", "écriture": "creatif", "writing": "creatif",
                "math": "math", "maths": "math", "mathématiques": "math",
                "vision": "vision", "image": "vision", "photo": "vision",
                "multilingual": "multilingual", "traduction": "multilingual", "translation": "multilingual",
            }
            category = task_map.get(task_lower, task_lower)
            cat_match = [m for m in candidates if category in m.categories]
            if cat_match:
                candidates = cat_match
        scored = []
        for m in candidates:
            score = m.quality_rating * 3
            score += m.speed_rating
            if language and language in m.languages:
                score += 5
            if language and m.primary_language == language:
                score += 3
            if task and task.lower() in " ".join(m.categories).lower():
                score += 5
            if m.shared:
                score += 2
            scored.append((m, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [m for m, s in scored]
    
    def get_mesh_catalog(self, include_cloud_shared: bool = False) -> List[ModelCard]:
        """Obtenir le catalogue des modèles disponibles sur le mesh public.
        
        Politique par défaut :
        - Les modèles cloud ne sont JAMAIS sur le mesh, SAUF si explicitement
          partagés par l'utilisateur (shared=True + force=True) et include_cloud_shared=True
        - Les modèles cloud-via-ollama (nom contenant ':cloud') sont exclus par défaut
        - Les modèles wishlist ne sont pas sur le mesh (pas installés)
        - Seuls les modèles locaux marqués shared=True sont inclus
        
        Si include_cloud_shared=True, les modèles cloud marqués shared=True sont inclus
        avec un avertissement — c'est le choix de l'utilisateur, à ses risques.
        """
        models = []
        for card in self._cards.values():
            is_cloud = card.source == ModelSource.CLOUD
            is_cloud_routed = card.name.endswith(':cloud') or ':cloud:' in card.name
            
            # Les modèles cloud ne sont sur le mesh QUE si explicitement partagés + demandés
            if is_cloud and not (include_cloud_shared and card.shared):
                continue
            # Les modèles cloud-routed ne sont sur le mesh QUE si explicitement partagés + demandés
            if is_cloud_routed and not (include_cloud_shared and card.shared):
                continue
            # Les modèles wishlist ne sont pas sur le mesh non plus
            if card.source == ModelSource.WISHLIST:
                continue
            if card.shared or card.source == ModelSource.MESH:
                mesh_card = ModelCard.from_dict(card.to_dict())
                mesh_card.source = ModelSource.MESH if not card.shared else card.source
                mesh_card.downloadable = True
                # Avertissement pour les modèles cloud partagés
                if is_cloud or is_cloud_routed:
                    mesh_card.notes = (mesh_card.notes or "") + " ⚠️ CLOUD MODEL — uses the owner's API key and resources. Shared at their own risk."
                models.append(mesh_card)
        models.sort(key=lambda m: m.community_score, reverse=True)
        return models
    
    def get_wishlist(self) -> List[ModelCard]:
        return [m for m in self._cards.values() if m.status == ModelStatus.WISHLIST]
    
    def add_to_wishlist(self, name: str, notes: str = "") -> ModelCard:
        card = ModelCard(
            name=name,
            source=ModelSource.WISHLIST,
            status=ModelStatus.WISHLIST,
            notes=notes,
            added_at=time.time(),
        )
        self._cards[name] = card
        self._save()
        logger.info(f"📚 Model added to wishlist: {name}")
        return card
    
    def share_model(self, name: str, force: bool = False) -> bool:
        """Marquer un modèle comme partagé sur le mesh.
        
        Politique par défaut :
        - Les modèles cloud (source=CLOUD) ne sont JAMAIS partagés sur le mesh
        - Les modèles cloud-via-ollama (nom contenant ':cloud') ne sont JAMAIS partagés
          car ce sont des API externes, pas des modèles téléchargeables
        - Les modèles wishlist ne sont pas partageables (pas installés)
        - Utiliser force=True pour override cette politique (l'utilisateur le spécifie explicitement)
        """
        if name not in self._cards:
            return False
        card = self._cards[name]
        if not force:
            # Les modèles cloud ne sont pas partageables sur le mesh
            if card.source == ModelSource.CLOUD:
                logger.warning(f"📚 Cannot share cloud model '{name}' on mesh — cloud models are private by default")
                return False
            # Les modèles cloud-via-ollama (nom se terminant par ':cloud') ne sont pas partageables non plus
            # Ce sont des API externes, pas des fichiers locaux qu'on peut distribuer
            if name.endswith(':cloud') or ':cloud:' in name:
                logger.warning(f"📚 Cannot share cloud-routed model '{name}' on mesh — uses external API, not shareable")
                return False
            # Les modèles wishlist ne sont pas partageables (pas installés)
            if card.source == ModelSource.WISHLIST:
                logger.warning(f"📚 Cannot share wishlist model '{name}' — not installed locally")
                return False
        card.shared = True
        card.status = ModelStatus.SHARING
        card.updated_at = time.time()
        self._save()
        return True
    
    def unshare_model(self, name: str) -> bool:
        if name in self._cards:
            self._cards[name].shared = False
            self._cards[name].status = ModelStatus.READY
            self._cards[name].updated_at = time.time()
            self._save()
            return True
        return False
    
    def update_mesh_discovery(self, mesh_models: List[Dict]):
        for model_data in mesh_models:
            name = model_data.get("name")
            if not name:
                continue
            node_id = model_data.get("node_id", "unknown")
            now = time.time()
            if name in self._cards:
                card = self._cards[name]
                if node_id not in card.mesh_nodes:
                    card.mesh_nodes.append(node_id)
                card.last_seen = now  # Marquer comme vu récemment
                card.updated_at = now
                if card.source == ModelSource.LOCAL:
                    card.downloadable = True
                elif card.source != ModelSource.LOCAL:
                    card.source = ModelSource.MESH
                    card.downloadable = True
            else:
                card = ModelCard(
                    name=name,
                    display_name=model_data.get("display_name", name),
                    description=model_data.get("description", "Modèle découvert sur le mesh"),
                    source=ModelSource.MESH,
                    status=ModelStatus.READY,
                    categories=model_data.get("categories", []),
                    quality_rating=model_data.get("quality_rating", 5),
                    speed_rating=model_data.get("speed_rating", 5),
                    shared=True,
                    downloadable=True,
                    mesh_nodes=[node_id],
                    last_seen=now,  # Première vue
                    community_score=model_data.get("community_score", 0.0),
                    added_at=time.time(),
                )
                self._cards[name] = card
        self._save()
        logger.info(f"📚 Mesh discovery updated: {len(mesh_models)} models processed")
    
    def get_stats(self) -> Dict:
        total = len(self._cards)
        by_source = {}
        by_status = {}
        by_category = {}
        shared_count = 0
        downloadable_count = 0
        for card in self._cards.values():
            source = card.source.value
            by_source[source] = by_source.get(source, 0) + 1
            status = card.status.value
            by_status[status] = by_status.get(status, 0) + 1
            for cat in card.categories:
                by_category[cat] = by_category.get(cat, 0) + 1
            if card.shared:
                shared_count += 1
            if card.downloadable:
                downloadable_count += 1
        return {
            "total_models": total,
            "by_source": by_source,
            "by_status": by_status,
            "by_category": by_category,
            "shared_count": shared_count,
            "downloadable_count": downloadable_count,
        }
    
    def format_catalog(self, format_type: str = "text") -> str:
        if format_type == "json":
            return json.dumps([c.to_dict() for c in self._cards.values()], indent=2, ensure_ascii=False)
        models = sorted(self._cards.values(), key=lambda m: (-m.quality_rating, m.name))
        if format_type == "markdown":
            lines = [
                "# 📚 Catalogue des Modèles PinkyBrain\n",
                f"**{len(models)} modèles** | ",
                f"🏠 Local: {sum(1 for m in models if m.source == ModelSource.LOCAL)} | ",
                f"🌐 Mesh: {sum(1 for m in models if m.source == ModelSource.MESH)} | ",
                f"☁️ Cloud: {sum(1 for m in models if m.source == ModelSource.CLOUD)} | ",
                f"📋 Wishlist: {sum(1 for m in models if m.source == ModelSource.WISHLIST)}\n",
            ]
            for source in [ModelSource.LOCAL, ModelSource.MESH, ModelSource.CLOUD, ModelSource.WISHLIST]:
                source_models = [m for m in models if m.source == source]
                if not source_models:
                    continue
                source_icon = {"local": "🏠", "mesh": "🌐", "cloud": "☁️", "wishlist": "📋"}.get(source.value, "❓")
                source_name = {"local": "Locaux", "mesh": "Mesh Public", "cloud": "Cloud (API)", "wishlist": "Wishlist"}.get(source.value, source.value)
                lines.append(f"\n## {source_icon} {source_name}\n")
                lines.append("| Modèle | Qualité | Vitesse | Contexte | Taille | Langues | Partagé |")
                lines.append("|--------|---------|---------|----------|--------|---------|---------|")
                for m in source_models:
                    shared = "✅" if m.shared else "—"
                    langs = ", ".join(m.languages[:3])
                    lines.append(
                        f"| {m.display_name or m.name} | "
                        f"{'⭐' * m.quality_rating} {m.quality_rating}/10 | "
                        f"{'⚡' * m.speed_rating} {m.speed_rating}/10 | "
                        f"{m.context_window:,} | "
                        f"{m.size_category} ({m.params_count or '?'}) | "
                        f"{langs} | "
                        f"{shared} |"
                    )
            return "\n".join(lines)
        # Format texte
        lines = [
            "📚 Catalogue des Modèles PinkyBrain",
            "=" * 50,
            f"Total: {len(models)} modèles",
            f"🏠 Local: {sum(1 for m in models if m.source == ModelSource.LOCAL)}",
            f"🌐 Mesh: {sum(1 for m in models if m.source == ModelSource.MESH)}",
            f"☁️ Cloud: {sum(1 for m in models if m.source == ModelSource.CLOUD)}",
            f"📋 Wishlist: {sum(1 for m in models if m.source == ModelSource.WISHLIST)}",
            "",
        ]
        for m in models:
            lines.append(m.summary())
            lines.append("")
        return "\n".join(lines)

    # ===================================================================
    # PURGE DES MODÈLES OBSOLÈTES
    # ===================================================================

    # Durée par défaut avant qu'un modèle mesh soit considéré obsolète
    STALE_THRESHOLD_SECONDS = 365 * 24 * 3600   # 12 mois
    STALE_THRESHOLD_DAYS = 365

    def purge_stale_models(self, max_age_days: int = 365) -> List[ModelCard]:
        """Retirer les modèles mesh sans nœud actif depuis plus de max_age_days.

        Les modèles locaux, cloud et wishlist ne sont JAMAIS retirés automatiquement.
        Seuls les modèles découverts via le mesh (source=MESH) dont last_seen est
        plus ancien que max_age_days sont purgés.

        Si last_seen == 0 (jamais vu sur le mesh), le modèle est conservé
        (c'est peut-être un modèle du catalogue par défaut qui n'a pas encore
        été annoncé sur le mesh).

        Args:
            max_age_days: Nombre de jours sans nœud actif avant purge (défaut: 365)

        Returns:
            Liste des modèles retirés.
        """
        now = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        purged = []

        to_remove = []
        for name, card in self._cards.items():
            # Ne jamais purger les modèles locaux, cloud ou wishlist
            if card.source in (ModelSource.LOCAL, ModelSource.CLOUD, ModelSource.WISHLIST, ModelSource.INSTALLING):
                continue

            # Ne pas purger les modèles jamais vus (last_seen == 0)
            # Ce sont les entrées du catalogue par défaut
            if card.last_seen == 0:
                continue

            # Vérifier si le modèle est obsolète
            age_seconds = now - card.last_seen
            if age_seconds > max_age_seconds:
                # Vérifier aussi qu'il n'a plus de nœuds actifs
                # (last_seen est mis à jour quand un nœud l'annonce)
                logger.info(
                    f"📚 Purging stale mesh model '{name}': "
                    f"last seen {age_seconds / 86400:.0f} days ago "
                    f"(threshold: {max_age_days} days), "
                    f"nodes: {card.mesh_nodes}"
                )
                to_remove.append(name)

        for name in to_remove:
            purged.append(self._cards.pop(name))

        if purged:
            self._save()
            logger.info(f"📚 Purged {len(purged)} stale mesh models (> {max_age_days} days without active node)")

        return purged

    def check_stale_models(self, max_age_days: int = 365) -> List[Dict[str, Any]]:
        """Vérifier les modèles proches de l'obsolescence SANS les retirer.

        Returns:
            Liste de dicts avec name, days_since_seen, source, mesh_nodes.
        """
        now = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        stale = []

        for name, card in self._cards.items():
            if card.source not in (ModelSource.MESH,):
                continue
            if card.last_seen == 0:
                continue

            age_seconds = now - card.last_seen
            age_days = age_seconds / 86400

            if age_seconds > max_age_seconds * 0.8:  # Alerte à 80% du seuil
                stale.append({
                    "name": name,
                    "display_name": card.display_name,
                    "source": card.source.value,
                    "days_since_seen": round(age_days),
                    "threshold_days": max_age_days,
                    "status": "stale" if age_days > max_age_days else "warning",
                    "mesh_nodes": card.mesh_nodes,
                })

        stale.sort(key=lambda x: x["days_since_seen"], reverse=True)
        return stale

    # ===================================================================
    # PERSISTANCE
    # ===================================================================
    
    def _load(self):
        if not self._registry_file.exists():
            self._cards = {}
            return
        try:
            with open(self._registry_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and "models" in data:
                data = data["models"]
            self._cards = {}
            for name, card_data in data.items():
                try:
                    self._cards[name] = ModelCard.from_dict(card_data)
                except Exception as e:
                    logger.warning(f"Failed to load model card for {name}: {e}")
            logger.info(f"📚 Loaded {len(self._cards)} models from registry")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load registry: {e}")
            self._cards = {}
    
    def _save(self):
        try:
            data = {
                "version": "1.0",
                "updated_at": time.time(),
                "models": {name: card.to_dict() for name, card in self._cards.items()},
            }
            with open(self._registry_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Failed to save registry: {e}")


# ============================================================================
# CLI
# ============================================================================

def main():
    """CLI interface for the Model Registry."""
    import argparse
    parser = argparse.ArgumentParser(
        description='📚 PinkyBrain Model Registry',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  list              List all models
  search <query>    Search models
  info <model>      Show detailed info
  add <model>        Add a model to registry
  remove <model>    Remove a model
  share <model>     Mark model as shared
  unshare <model>   Stop sharing
  wishlist <model>  Add to wishlist
  recommend         Get recommendations
  catalog           Show full catalog
  stats             Show registry statistics
  mesh              Show mesh-available models
  stale [days]      Check stale mesh models (default: 365 days)
  purge [days]      Purge mesh models not seen in N days (default: 365)
  verify [file]     Verify catalog integrity (hash + signature + schema)
  sign <key> [file] Sign catalog with Ed25519 private key
  hash [file]       Compute SHA-256 hash of catalog
  update-hash [file] Update the .sha256 hash file for the catalog
""")
    parser.add_argument('command', nargs='?', help='Command')
    parser.add_argument('args', nargs='*', help='Command arguments')
    parser.add_argument('--source', help='Filter by source (local, mesh, cloud, wishlist)')
    parser.add_argument('--category', help='Filter by category')
    parser.add_argument('--language', help='Filter by language')
    parser.add_argument('--min-quality', type=int, help='Minimum quality rating')
    parser.add_argument('--task', help='Task type for recommendations')
    parser.add_argument('--format', choices=['text', 'markdown', 'json'], default='text')
    parser.add_argument('--base-dir', help='Base directory')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    registry = ModelRegistry(base_dir=args.base_dir)
    registry.initialize()
    cmd = args.command
    cmd_args = args.args
    if cmd == 'list':
        models = registry.list_models(
            source=args.source, category=args.category,
            language=args.language, min_quality=args.min_quality,
        )
        if not models:
            print("No models found")
        else:
            print(f"Models ({len(models)}):\n")
            for m in models:
                source_icon = {"local": "🏠", "mesh": "🌐", "cloud": "☁️", "wishlist": "📋", "installing": "⏳"}.get(m.source.value, "❓")
                shared = " 📡" if m.shared else ""
                print(f"  {source_icon} {m.display_name or m.name}{shared}")
                print(f"     {m.description}")
                print(f"     Quality: {m.quality_rating}/10 | Speed: {m.speed_rating}/10 | Context: {m.context_window:,} | Size: {m.size_category}")
                print()
    elif cmd == 'search':
        if not cmd_args:
            print("Usage: search <query>")
            return
        results = registry.search(" ".join(cmd_args))
        if not results:
            print("No results")
        else:
            for m in results:
                print(m.summary())
                print()
    elif cmd == 'info':
        if not cmd_args:
            print("Usage: info <model_name>")
            return
        name = cmd_args[0]
        card = registry.get_model(name)
        if not card:
            results = registry.search(name)
            if results:
                card = results[0]
            else:
                print(f"Model '{name}' not found")
                return
        print(card.summary())
        print(f"\n   Provider: {card.provider}")
        print(f"   Architecture: {card.architecture or 'N/A'}")
        print(f"   License: {card.license or 'N/A'}")
        print(f"   Quantization: {card.quantization or 'N/A'}")
        if card.price_per_million_input or card.price_per_million_output:
            print(f"   Prix: ${card.price_per_million_input}/M input, ${card.price_per_million_output}/M output")
        if card.best_for:
            print(f"   ✅ Idéal pour: {', '.join(card.best_for)}")
        if card.not_for:
            print(f"   ❌ Pas pour: {', '.join(card.not_for)}")
        if card.mesh_nodes:
            print(f"   🌐 Nœuds mesh: {', '.join(card.mesh_nodes)}")
        print(f"   Utilisations: {card.use_count}")
        if card.notes:
            print(f"   Notes: {card.notes}")
    elif cmd == 'add':
        if not cmd_args:
            print("Usage: add <model_name> [--source local|cloud|wishlist]")
            return
        name = cmd_args[0]
        source = args.source or "local"
        card = ModelCard(
            name=name,
            display_name=name,
            source=ModelSource(source),
            status=ModelStatus.WISHLIST if source == "wishlist" else ModelStatus.READY,
            added_at=time.time(),
        )
        registry.add_model(card)
        print(f"✅ Added {name} (source: {source})")
    elif cmd == 'remove':
        if not cmd_args:
            print("Usage: remove <model_name>")
            return
        if registry.remove_model(cmd_args[0]):
            print(f"✅ Removed {cmd_args[0]}")
        else:
            print(f"❌ Model '{cmd_args[0]}' not found")
    elif cmd == 'share':
        if not cmd_args:
            print("Usage: share <model_name> [--force]")
            print("  --force  Override cloud model protection (share at your own risk)")
            return
        model_name = cmd_args[0]
        force = '--force' in cmd_args
        card = registry.get_model(model_name)
        if not card:
            print(f"❌ Model '{model_name}' not found")
            return
        is_cloud = card.source.value == 'cloud' or model_name.endswith(':cloud') or ':cloud:' in model_name
        if is_cloud and not force:
            print(f"⚠️  '{model_name}' is a cloud model — it cannot be shared on the mesh by default.")
            print(f"   Sharing a cloud model means other nodes will use YOUR API key.")
            print(f"   You are responsible for all costs incurred.")
            print(f"   Use: share {model_name} --force  to share at your own risk.")
            return
        if is_cloud and force:
            print(f"⚠️  WARNING: You are sharing a cloud model on the public mesh.")
            print(f"   Other nodes will route requests through YOUR API key.")
            print(f"   You are responsible for all usage and costs.")
        if registry.share_model(model_name, force=force):
            print(f"✅ {model_name} is now shared on the mesh")
            if is_cloud:
                print(f"   ⚠️  Risk acknowledged — cloud model shared publicly")
        else:
            print(f"❌ Cannot share '{model_name}'")
    elif cmd == 'unshare':
        if not cmd_args:
            print("Usage: unshare <model_name>")
            return
        if registry.unshare_model(cmd_args[0]):
            print(f"✅ {cmd_args[0]} is no longer shared")
        else:
            print(f"❌ Model '{cmd_args[0]}' not found")
    elif cmd == 'wishlist':
        if not cmd_args:
            wishlist = registry.get_wishlist()
            if not wishlist:
                print("Wishlist is empty")
            else:
                print(f"Wishlist ({len(wishlist)}):\n")
                for m in wishlist:
                    print(f"  📋 {m.name}")
                    if m.notes:
                        print(f"     {m.notes}")
            return
        name = cmd_args[0]
        notes = " ".join(cmd_args[1:]) if len(cmd_args) > 1 else ""
        registry.add_to_wishlist(name, notes)
        print(f"✅ Added {name} to wishlist")
    elif cmd == 'recommend':
        recommendations = registry.get_recommendations(
            task=args.task, language=args.language, min_quality=args.min_quality,
        )
        if not recommendations:
            print("No recommendations found")
        else:
            print(f"🎯 Recommendations ({len(recommendations)}):\n")
            for m in recommendations[:5]:
                print(m.summary())
                print()
    elif cmd == 'catalog':
        print(registry.format_catalog(format_type=args.format))
    elif cmd == 'stats':
        stats = registry.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    elif cmd == 'mesh':
        mesh_models = registry.get_mesh_catalog()
        if not mesh_models:
            print("No mesh models available")
        else:
            print(f"🌐 Mesh Catalog ({len(mesh_models)}):\n")
            for m in mesh_models:
                shared = "📡" if m.shared else ""
                downloadable = "⬇️" if m.downloadable else ""
                print(f"  {m.display_name or m.name} {shared}{downloadable}")
                print(f"     {m.description}")
                print(f"     Quality: {m.quality_rating}/10 | Nodes: {len(m.mesh_nodes)}")
                print()
    elif cmd == 'stale':
        max_days = int(cmd_args[0]) if cmd_args else 365
        stale = registry.check_stale_models(max_age_days=max_days)
        if not stale:
            print(f"✅ No stale mesh models (threshold: {max_days} days)")
        else:
            print(f"⚠️  {len(stale)} stale mesh model(s) (threshold: {max_days} days):\n")
            for s in stale:
                status_icon = "🔴" if s["status"] == "stale" else "🟡"
                print(f"  {status_icon} {s['display_name'] or s['name']}")
                print(f"     Last seen: {s['days_since_seen']} days ago")
                print(f"     Nodes: {', '.join(s['mesh_nodes']) if s['mesh_nodes'] else 'none'}")
                print()
    elif cmd == 'purge':
        max_days = int(cmd_args[0]) if cmd_args else 365
        purged = registry.purge_stale_models(max_age_days=max_days)
        if not purged:
            print(f"✅ No stale models to purge (threshold: {max_days} days)")
        else:
            print(f"🗑️  Purged {len(purged)} stale mesh model(s):")
            for p in purged:
                print(f"  - {p.display_name or p.name} (last seen: {p.last_seen})")
    elif cmd == 'verify':
        # Verify catalog integrity
        import sys
        catalog_path = cmd_args[0] if cmd_args else CATALOG_FILE
        hash_path = catalog_path + ".sha256"
        sig_path = catalog_path + ".sig"
        print(f"🔍 Verifying catalog: {catalog_path}")
        # Size check
        try:
            size = os.path.getsize(catalog_path)
            print(f"  Size: {size:,} bytes ({'OK' if size <= MAX_CATALOG_SIZE else 'TOO LARGE'})")
            if size > MAX_CATALOG_SIZE:
                print("  ❌ File too large!")
                sys.exit(1)
        except OSError:
            print(f"  ❌ File not found!")
            sys.exit(1)
        # Hash check
        current_hash = compute_catalog_hash(catalog_path)
        print(f"  SHA-256: {current_hash}")
        if verify_catalog_hash(catalog_path, hash_path):
            print(f"  ✅ Hash verified")
        else:
            print(f"  ❌ Hash MISMATCH — file may be tampered with!")
            sys.exit(1)
        # Signature check
        if os.path.exists(sig_path):
            if verify_catalog_signature(catalog_path, sig_path):
                print(f"  ✅ Signature verified")
            else:
                print(f"  ❌ Signature INVALID — file may be tampered with!")
                sys.exit(1)
        else:
            print(f"  ℹ️  No signature file (not required)")
        # Schema check
        with open(catalog_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if validate_catalog_schema(data):
            print(f"  ✅ Schema valid ({len(data)} models)")
        else:
            print(f"  ❌ Schema validation FAILED!")
            sys.exit(1)
        print(f"\n🛡️  Catalog integrity: OK")
    elif cmd == 'sign':
        # Sign the catalog with an Ed25519 private key
        import sys
        if not cmd_args:
            print("Usage: sign <private_key_hex>")
            print("Generate a key pair with:")
            print("  python3 -c \"from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; key = Ed25519PrivateKey.generate(); print('PRIVATE:', key.private_bytes_raw().hex()); print('PUBLIC:', key.public_key().public_bytes_raw().hex())\"")
            sys.exit(1)
        private_key_hex = cmd_args[0]
        catalog_path = cmd_args[1] if len(cmd_args) > 1 else CATALOG_FILE
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            priv_key_bytes = bytes.fromhex(private_key_hex)
            private_key = Ed25519PrivateKey.from_private_bytes(priv_key_bytes)
            with open(catalog_path, "rb") as f:
                data = f.read()
            signature = private_key.sign(data)
            sig_path = catalog_path + ".sig"
            with open(sig_path, "wb") as f:
                f.write(signature)
            pub_key = private_key.public_key()
            pub_hex = pub_key.public_bytes_raw().hex()
            print(f"✅ Catalog signed: {sig_path}")
            print(f"   Public key (add to TRUSTED_PUBLIC_KEY_HEX): {pub_hex}")
        except ImportError:
            print("❌ cryptography library not installed. Install with: pip install cryptography")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    elif cmd == 'hash':
        # Compute and display the hash
        catalog_path = cmd_args[0] if cmd_args else CATALOG_FILE
        if not os.path.exists(catalog_path):
            print(f"❌ File not found: {catalog_path}")
            sys.exit(1)
        current_hash = compute_catalog_hash(catalog_path)
        print(f"{current_hash}")
    elif cmd == 'update-hash':
        # Update the hash file for the catalog
        catalog_path = cmd_args[0] if cmd_args else CATALOG_FILE
        hash_path = catalog_path + ".sha256"
        current_hash = compute_catalog_hash(catalog_path)
        with open(hash_path, "w", encoding="utf-8") as f:
            f.write(f"{current_hash}  model_catalog.json\n")
        print(f"✅ Hash updated: {hash_path}")
        print(f"   SHA-256: {current_hash}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
