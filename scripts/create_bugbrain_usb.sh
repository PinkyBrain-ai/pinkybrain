#!/bin/bash
#
# 🔧 CREATE PINKYBRAIN_BUG USB - Script pour créer une clé USB bootable
# PinkyBrainAgent v3.0 - Plug & Play sur n'importe quelle machine
#
# Usage:
#   sudo ./create_pinkybrain_bug_usb.sh /dev/sdX
#

set -e

# ============================================================================
# ============== CONFIGURATION ============================================
# ============================================================================

# Variables
VERSION="3.0.0"
ISO_FILE="pinkybrain_bug-${VERSION}.iso"
USB_DEVICE="${1:-}"
TEMP_DIR="/tmp/pinkybrain_bug-usb-$$"
MOUNT_DIR="${TEMP_DIR}/mount"
IMAGE_SIZE="4G"  # Taille de l'image (4GB)

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# ============== FONCTIONS ================================================
# ============================================================================

print_header() {
    echo ""
    echo "============================================================"
    echo "🐛 PINKYBRAIN_BUG v${VERSION} - CREATE USB BOOTABLE"
    echo "============================================================"
    echo ""
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "Ce script doit être exécuté avec sudo"
        exit 1
    fi
}

check_dependencies() {
    print_info "Vérification des dépendances..."

    DEPS=("genisoimage" "xorriso" "mtools" "grub2" "squashfs-tools")

    for dep in "${DEPS[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            print_warning "$dep n'est pas installé"
            print_info "Installation avec: apt-get install $dep"
            read -p "Installer maintenant ? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                apt-get update && apt-get install -y $dep
            fi
        fi
    done

    print_success "Dépendances OK"
}

create_temp_dirs() {
    print_info "Création des répertoires temporaires..."

    mkdir -p "$TEMP_DIR"
    mkdir -p "$MOUNT_DIR"
    mkdir -p "${TEMP_DIR}/iso"
    mkdir -p "${TEMP_DIR}/iso/boot/grub"
    mkdir -p "${TEMP_DIR}/rootfs"

    print_success "Répertoires créés"
}

copy_pinkybrain_bug() {
    print_info "Copie de PinkyBrainAgent..."

    # Copier le code source
    if [ -d "PinkyBrain" ]; then
        cp -r PinkyBrain "${TEMP_DIR}/rootfs/"
    else
        # Télécharger depuis GitHub
        print_info "Téléchargement depuis GitHub..."
        git clone https://github.com/PinkyBrain-ai/PinkyBrain.git "${TEMP_DIR}/rootfs/PinkyBrain"
    fi

    # Créer le script de démarrage automatique
    cat > "${TEMP_DIR}/rootfs/start_pinkybrain_bug.sh" << 'EOF'
#!/bin/bash
#
# 🐛 PinkyBrainAgent - Démarrage automatique
#

echo ""
echo "============================================================"
echo "🐛 PINKYBRAIN_BUG v3.0 - Démarrage automatique"
echo "============================================================"
echo ""

cd /rootfs/PinkyBrain

# Vérifier Ollama
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama n'est pas installé"
    echo "Installation en cours..."
    curl -fsSL https://ollama.ai/install.sh | sh
fi

# Démarrer Ollama
echo "🧠 Démarrage d'Ollama..."
ollama serve &
sleep 5

# Télécharger les modèles nécessaires
echo "📥 Téléchargement des modèles..."
ollama pull SmolLM2:1.7b
ollama pull phi3:mini

# Lancer PinkyBrainAgent
echo "🚀 Lancement de PinkyBrainAgent..."
python3 -m src.pinkybrain_v5
EOF

    chmod +x "${TEMP_DIR}/rootfs/start_pinkybrain_bug.sh"

    print_success "PinkyBrainAgent copié"
}

create_grub_config() {
    print_info "Création de la configuration GRUB..."

    cat > "${TEMP_DIR}/iso/boot/grub/grub.cfg" << 'EOF'
set timeout=10
set default=0

menuentry "🐛 PinkyBrainAgent v3.0 - Démarrage automatique" {
    linux /boot/vmlinuz boot=live quiet splash
    initrd /boot/initrd
}

menuentry "🐛 PinkyBrainAgent v3.0 - Démarrage (verbose)" {
    linux /boot/vmlinuz boot=live
    initrd /boot/initrd
}

menuentry "🔧 Setup interactif" {
    linux /boot/vmlinuz boot=live quiet
    initrd /boot/initrd
    initrd /boot/setup
}

menuentry "💻 Shell (dépannage)" {
    linux /boot/vmlinuz boot=live
    initrd /boot/initrd
}
EOF

    print_success "Configuration GRUB créée"
}

create_readme() {
    print_info "Création du README..."

    cat > "${TEMP_DIR}/rootfs/README.txt" << 'EOF'
🐛 PINKYBRAIN_BUG v3.0 - CLÉ USB BOOTABLE
===================================

Bienvenue sur PinkyBrainAgent !

📋 INSTRUCTIONS:

1. Démarrage Automatique:
   PinkyBrainAgent démarrera automatiquement au boot.

2. Setup Interactif:
   Exécutez: cd /rootfs/PinkyBrain && python3 scripts/setup_interactive.py

3. Documentation:
   Voir: /rootfs/PinkyBrain/README.md
   Et: /rootfs/PinkyBrain/docs/

4. Auto-Support:
   PinkyBrainAgent répond lui-même aux questions de support !
   Exécutez: python3 -m src.auto_support

🔧 CONFIGURATION:

- Ollama: Installé automatiquement
- Modèles: SmolLM2:1.7b, phi3:mini (téléchargés auto)
- Configuration: /rootfs/PinkyBrain/config.json

📞 SUPPORT:

Questions ? PinkyBrainAgent répond lui-même !

Généré par PinkyBrainAgent 🐛 - v3.0.0
EOF

    print_success "README créé"
}

create_iso() {
    print_info "Création de l'image ISO..."

    # Créer le squashfs
    print_info "Compression du filesystem..."
    mksquashfs "${TEMP_DIR}/rootfs" "${TEMP_DIR}/iso/rootfs.img" -comp xz -b 1M

    # Copier le noyau et initrd (exemple, à adapter selon votre système)
    if [ -f "/boot/vmlinuz-$(uname -r)" ]; then
        cp "/boot/vmlinuz-$(uname -r)" "${TEMP_DIR}/iso/boot/vmlinuz"
        cp "/boot/initrd.img-$(uname -r)" "${TEMP_DIR}/iso/boot/initrd"
    else
        print_warning "Noyau non trouvé, utilisation du noyau du live USB..."
        # Alternative: utiliser un live-cd existant comme base
    fi

    # Créer l'ISO
    print_info "Génération de l'ISO..."
    xorriso -as mkisofs \
        -rational-rock \
        -volid "PINKYBRAIN_BUG" \
        -isohybrid-mbr /usr/lib/ISOLINUX/isohdpfx.bin \
        -b boot/grub/bios.img \
        -c boot/boot.catalog \
        -boot-load-size 4 \
        -boot-info-table \
        -eltorito-alt-boot \
        -e boot/grub/efi.img \
        -no-emul-boot \
        -isohybrid-gpt-basdat \
        -o "$ISO_FILE" \
        "${TEMP_DIR}/iso"

    print_success "ISO créée: $ISO_FILE"
}

write_to_usb() {
    if [ -z "$USB_DEVICE" ]; then
        print_warning "Aucun périphérique USB spécifié"
        print_info "Utilisation: sudo ./create_pinkybrain_bug_usb.sh /dev/sdX"
        print_info "L'ISO est disponible: $ISO_FILE"
        print_info "Vous pouvez la graver manuellement avec:"
        echo "  dd if=$ISO_FILE of=/dev/sdX bs=4M status=progress"
        return
    fi

    print_info "Vérification du périphérique: $USB_DEVICE"

    if [ ! -b "$USB_DEVICE" ]; then
        print_error "$USB_DEVICE n'est pas un périphérique de bloc valide"
        exit 1
    fi

    print_warning "TOUTES LES DONNÉES SUR $USB_DEVICE SERONT PERDUES !"
    read -p "Continuer ? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        print_info "Annulation"
        exit 0
    fi

    print_info "Écriture sur $USB_DEVICE..."
    dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress conv=fdatasync

    print_success "Clé USB créée avec succès !"
    print_info "Vous pouvez maintenant booter sur cette clé USB !"
}

cleanup() {
    print_info "Nettoyage..."
    rm -rf "$TEMP_DIR"
    print_success "Nettoyage terminé"
}

# ============================================================================
# ============== SCRIPT PRINCIPAL ==========================================
# ============================================================================

main() {
    print_header

    check_root
    check_dependencies
    create_temp_dirs
    copy_pinkybrain_bug
    create_grub_config
    create_readme
    create_iso
    write_to_usb
    cleanup

    print_header
    print_success "✅ TERMINÉ !"
    print_header
}

main "$@"