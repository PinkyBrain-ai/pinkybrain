#!/usr/bin/env python3
"""
Exemple 4: True P2P Network
"""

import asyncio
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.true_p2p_network import P2PNode, P2PConfig, NodeID


async def main():
    """Exemple P2P"""

    print("=" * 70)
    print("EXEMPLE 4: True P2P Network - DHT & Gossip")
    print("=" * 70)

    # Configuration
    config = P2PConfig()
    config.bootstrap_nodes = []  # Premier nœud, pas de bootstrap

    # Créer le nœud P2P
    print("\n🔄 Création du nœud P2P...")
    node = P2PNode("127.0.0.1", 9990, config)

    # Démarrer le nœud
    print("⚙️ Démarrage...")
    await node.start()

    # Attendre un peu
    await asyncio.sleep(3)

    # Stocker une valeur dans la DHT
    print("\n💾 Stockage dans la DHT...")
    success = await node.store("user:denis", {
        "name": "Denis",
        "email": "denis@example.com",
        "location": "Bruxelles"
    })

    if success:
        print("✅ Donnée stockée avec succès")
    else:
        print("❌ Erreur lors du stockage")

    # Récupérer la valeur
    print("\n🔍 Récupération depuis la DHT...")
    value = await node.get("user:denis")

    if value:
        print("✅ Donnée trouvée:")
        print(f"   {value}")
    else:
        print("❌ Donnée non trouvée")

    # Broadcast
    print("\n📢 Broadcast...")
    await node.broadcast("announcement", {
        "message": "PinkyBrain v3.0 est en ligne !",
        "timestamp": 1234567890
    })

    print("✅ Message broadcasté")

    # Statistiques
    print("\n📊 Statistiques du nœud:")
    status = node.get_status()

    print(f"   Node ID: {status['node_id']}")
    print(f"   Address: {status['host']}:{status['port']}")
    print(f"   Total Peers: {status['routing_table']['total_peers']}")
    print(f"   Keys Stored: {status['dht_store']['keys']}")
    print(f"   Info Types: {status['gossip']['info_types']}")

    print("\n💡 Le nœud continue de tourner en background...")
    print("   Ctrl+C pour arrêter")

    # Garder en cours
    try:
        while True:
            await asyncio.sleep(60)

            status = node.get_status()
            print(f"\n📊 [Every 60s] Peers: {status['routing_table']['total_peers']}")

    except KeyboardInterrupt:
        print("\n\n🛑 Arrêt du nœud...")
        node.stop()
        print("✅ Nœud arrêté")


if __name__ == '__main__':
    asyncio.run(main())