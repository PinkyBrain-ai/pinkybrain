#!/usr/bin/env python3
"""
🚀 SETUP INTERACTIF - PinkyBrain & PinkyBrainAgent v3.0
Installation interactive avec configuration complète

Usage:
    python3 setup_interactive.py
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any

class PinkyBrainSetup:
    """Setup interactif PinkyBrain"""

    def __init__(self):
        self.config_file = "config.json"
        self.config = {}
        self.project_root = Path(__file__).parent.parent

    def print_header(self):
        """Affiche le header"""
        print("=" * 70)
        print("🚀 PINKYBRAIN & PINKYBRAIN_BUG v3.0 - SETUP INTERACTIF")
        print("=" * 70)
        print()
        print("Bienvenue dans l'assistant d'installation !")
        print("Cet outil va vous guider à travers la configuration initiale.")
        print()

    def get_input(self, prompt: str, default: Any = None, required: bool = True) -> Any:
        """
        Demande une entrée à l'utilisateur
        """
        if default is not None:
            prompt = f"{prompt} [{default}]: "
        else:
            prompt = f"{prompt}: "

        while True:
            value = input(prompt).strip()

            if value:
                return value
            elif default is not None:
                return default
            elif not required:
                return None
            else:
                print("⚠️ Ce champ est requis. Veuillez entrer une valeur.")

    def configure_agent(self):
        """Configure l'agent principal"""
        print("\n" + "=" * 70)
        print("🤖 CONFIGURATION DE L'AGENT")
        print("=" * 70)

        self.config["agent"] = {
            "name": self.get_input(
                "Nom de votre agent",
                "PinkyBrainAgent"
            ),
            "emoji": self.get_input(
                "Emoji de l'agent",
                "🐛"
            ),
            "description": self.get_input(
                "Description de l'agent",
                "Système d'IA auto-émancipé",
                required=False
            ),
            "language": self.get_input(
                "Langue par défaut",
                "fr"
            ),
            "timezone": self.get_input(
                "Fuseau horaire",
                "Europe/Paris"
            )
        }

    def configure_ollama(self):
        """Configure Ollama"""
        print("\n" + "=" * 70)
        print("🧠 CONFIGURATION OLLAMA")
        print("=" * 70)

        self.config["ollama"] = {
            "enabled": self.get_input(
                "Ollama activé ? (y/n)",
                "y"
            ).lower() == "y",
            "host": self.get_input(
                "Adresse Ollama",
                "127.0.0.1"
            ),
            "port": self.get_input(
                "Port Ollama",
                "11434"
            ),
            "primary_model": self.get_input(
                "Modèle principal",
                "SmolLM2:1.7b"
            ),
            "timeout_default": int(self.get_input(
                "Timeout par défaut (secondes)",
                "120"
            ))
        }

    def configure_api_keys(self):
        """Configure les clés API"""
        print("\n" + "=" * 70)
        print("🔑 CONFIGURATION DES CLÉS API")
        print("=" * 70)
        print("Les clés API sont optionnelles pour le fonctionnement standalone.")
        print("Elles sont nécessaires pour les fonctionnalités cloud et certaines intégrations.")
        print()

        self.config["api_keys"] = {
            "openai": self.get_input(
                "Clé API OpenAI (optionnel)",
                "",
                required=False
            ),
            "anthropic": self.get_input(
                "Clé API Anthropic (optionnel)",
                "",
                required=False
            ),
            "google": self.get_input(
                "Clé API Google (optionnel)",
                "",
                required=False
            ),
            "cohere": self.get_input(
                "Clé API Cohere (optionnel)",
                "",
                required=False
            )
        }

    def configure_telegram(self):
        """Configure Telegram"""
        print("\n" + "=" * 70)
        print("📱 CONFIGURATION TELEGRAM (OPTIONNEL)")
        print("=" * 70)

        enabled = self.get_input(
            "Activer le support Telegram ? (y/n)",
            "n"
        ).lower() == "y"

        if enabled:
            self.config["telegram"] = {
                "enabled": True,
                "bot_token": self.get_input(
                    "Token du bot Telegram",
                    required=True
                ),
                "chat_id": self.get_input(
                    "ID du chat (optionnel)",
                    "",
                    required=False
                )
            }
        else:
            self.config["telegram"] = {"enabled": False}

    def configure_p2p(self):
        """Configure le réseau P2P"""
        print("\n" + "=" * 70)
        print("🌐 CONFIGURATION RÉSEAU P2P")
        print("=" * 70)

        self.config["p2p"] = {
            "enabled": self.get_input(
                "Activer le réseau P2P ? (y/n)",
                "y"
            ).lower() == "y",
            "port": self.get_input(
                "Port P2P",
                "9999"
            ),
            "bootstrap_peers": self.get_input(
                "Peers de bootstrap (séparés par virgule)",
                "",
                required=False
            ).split(",") if self.get_input else []
        }

    def configure_auto_support(self):
        """Configure l'auto-support"""
        print("\n" + "=" * 70)
        print("🤖 CONFIGURATION AUTO-SUPPORT")
        print("=" * 70)
        print("L'auto-support permet à PinkyBrainAgent de répondre lui-même aux questions.")
        print()

        self.config["auto_support"] = {
            "enabled": self.get_input(
                "Activer l'auto-support ? (y/n)",
                "y"
            ).lower() == "y",
            "model": self.get_input(
                "Modèle pour l'auto-support",
                "SmolLM2:1.7b"
            ),
            "max_retries": int(self.get_input(
                "Nombre de tentatives de réponse",
                "3"
            )),
            "confidence_threshold": float(self.get_input(
                "Seuil de confiance (0.0-1.0)",
                "0.7"
            ))
        }

    def configure_maintenance(self):
        """Configure la maintenance"""
        print("\n" + "=" * 70)
        print("🔧 CONFIGURATION MAINTENANCE")
        print("=" * 70)

        self.config["maintenance"] = {
            "auto_cleanup": self.get_input(
                "Nettoyage automatique ? (y/n)",
                "y"
            ).lower() == "y",
            "cleanup_interval_days": int(self.get_input(
                "Intervalle de nettoyage (jours)",
                "7"
            )),
            "backup_enabled": self.get_input(
                "Activer les sauvegardes ? (y/n)",
                "y"
            ).lower() == "y",
            "backup_path": self.get_input(
                "Chemin des sauvegardes",
                "./backups"
            )
        }

    def save_config(self):
        """Sauvegarde la configuration"""
        print("\n" + "=" * 70)
        print("💾 SAUVEGARDE DE LA CONFIGURATION")
        print("=" * 70)

        config_path = self.project_root / self.config_file

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

        print(f"✅ Configuration sauvegardée dans: {config_path}")

    def print_summary(self):
        """Affiche le résumé"""
        print("\n" + "=" * 70)
        print("📊 RÉSUMÉ DE LA CONFIGURATION")
        print("=" * 70)

        print(f"\n🤖 Agent:")
        print(f"   Nom: {self.config['agent']['name']}")
        print(f"   Emoji: {self.config['agent']['emoji']}")
        print(f"   Langue: {self.config['agent']['language']}")
        print(f"   Timezone: {self.config['agent']['timezone']}")

        if self.config["ollama"]["enabled"]:
            print(f"\n🧠 Ollama:")
            print(f"   Host: {self.config['ollama']['host']}:{self.config['ollama']['port']}")
            print(f"   Modèle: {self.config['ollama']['primary_model']}")
            print(f"   Timeout: {self.config['ollama']['timeout_default']}s")

        if self.config["telegram"]["enabled"]:
            print(f"\n📱 Telegram: ✅ Activé")

        if self.config["p2p"]["enabled"]:
            print(f"\n🌐 P2P: ✅ Activé (port {self.config['p2p']['port']})")

        if self.config["auto_support"]["enabled"]:
            print(f"\n🤖 Auto-Support: ✅ Activé")

        print()

    def create_directories(self):
        """Crée les répertoires nécessaires"""
        print("\n" + "=" * 70)
        print("📁 CRÉATION DES RÉPERTOIRES")
        print("=" * 70)

        directories = [
            "output",
            "logs",
            "backups",
            "cache",
            "memory"
        ]

        for dir_name in directories:
            dir_path = self.project_root / dir_name
            dir_path.mkdir(exist_ok=True)
            print(f"✅ Créé: {dir_path}")

    def run(self):
        """Exécute le setup"""
        self.print_header()

        # Configuration
        self.configure_agent()
        self.configure_ollama()
        self.configure_api_keys()
        self.configure_telegram()
        self.configure_p2p()
        self.configure_auto_support()
        self.configure_maintenance()

        # Sauvegarde
        self.save_config()
        self.create_directories()

        # Résumé
        self.print_summary()

        print("\n" + "=" * 70)
        print("✅ SETUP TERMINÉ AVEC SUCCÈS !")
        print("=" * 70)
        print()
        print("Prochaines étapes:")
        print("1. Vérifiez la configuration dans config.json")
        print("2. Lancez l'agent: python3 -m src.pinkybrain_v5")
        print("3. Testez avec: python3 examples/example1_simple_query.py")
        print()
        print("Pour le support, utilisez l'auto-support intégré !")
        print()


def main():
    """Point d'entrée principal"""
    setup = PinkyBrainSetup()
    setup.run()


if __name__ == '__main__':
    main()