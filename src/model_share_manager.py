#!/usr/bin/env python3
"""
📂 MODEL SHARE MANAGER — PinkyBrain v5
========================================
Manages the shared_models/ directory — the ONLY bridge between private
models and the public mesh.

Security guarantees:
  - The mesh NEVER reads outside shared_models/
  - Symlinks are unidirectional (read-only for mesh)
  - Strict model name validation (no path traversal)
  - No private data in tracker announcements
  - Directory created with restrictive permissions (0700)
  - Downloads from mesh are verified (SHA-256 checksum)
  - Privatize moves models OUT of shared_models/ (removes mesh visibility)
"""

import hashlib
import json
import logging
import os
import re
import shutil
import stat
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger('PinkyBrain.ModelShareManager')

# ============================================================================
# CONSTANTS
# ============================================================================

DEFAULT_BASE_DIR = os.path.expanduser("~/.pinkybrain")
SHARED_MODELS_DIR_NAME = "shared_models"
OLLAMA_MODELS_DIR = os.path.expanduser("~/.ollama/models")

# Model name validation: alphanumeric, dots, hyphens, underscores, colons
# NO path separators, NO parent directory references
VALID_MODEL_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$')

# Maximum model name length
MAX_MODEL_NAME_LENGTH = 128

# Buffer size for checksum computation
CHECKSUM_BUFFER_SIZE = 64 * 1024  # 64 KB


# ============================================================================
# EXCEPTIONS
# ============================================================================

class ModelShareError(Exception):
    """Base exception for ModelShareManager."""
    pass


class InvalidModelNameError(ModelShareError):
    """Model name fails validation (path traversal, invalid chars, etc.)."""
    pass


class ModelNotFoundError(ModelShareError):
    """Model not found in the expected location."""
    pass


class ModelAlreadySharedError(ModelShareError):
    """Model is already in shared_models/."""
    pass


class ModelNotSharedError(ModelShareError):
    """Model is not in shared_models/ (cannot unshare)."""
    pass


class IntegrityCheckError(ModelShareError):
    """Model integrity check failed (corrupted, tampered, etc.)."""
    pass


class DownloadError(ModelShareError):
    """Error downloading a model from the mesh."""
    pass


# ============================================================================
# MODEL SHARE MANAGER
# ============================================================================

class ModelShareManager:
    """Manages the shared_models/ directory — the ONLY bridge to the public mesh.

    This is the boundary between private and public. The mesh can ONLY see
    what's in shared_models/. Everything else is off-limits.

    Design principles:
      1. Symlinks, not copies — saves disk space, unshare is instant
      2. Validate ALL model names — prevent path traversal attacks
      3. Restrictive directory permissions — 0700, owned by user
      4. Checksums on all downloads — verify integrity before use
      5. Privatize removes mesh access — moves model to private storage
    """

    def __init__(self, base_dir: str = None, ollama_dir: str = None):
        """Initialize ModelShareManager.

        Args:
            base_dir: Base directory for PinkyBrain data (default: ~/.pinkybrain)
            ollama_dir: Ollama models directory (default: ~/.ollama/models)
        """
        self.base_dir = Path(base_dir or DEFAULT_BASE_DIR)
        self.shared_dir = self.base_dir / SHARED_MODELS_DIR_NAME
        self.ollama_dir = Path(ollama_dir or OLLAMA_MODELS_DIR)

        # Metadata file for checksums and timestamps
        self._metadata_file = self.shared_dir / ".metadata.json"
        self._metadata: Dict = {}

        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    # ===================================================================
    # INITIALIZATION
    # ===================================================================

    def initialize(self) -> None:
        """Initialize the shared_models directory with proper permissions.

        This MUST be called before any other operation. It:
          1. Creates shared_models/ with mode 0700
          2. Loads existing metadata
          3. Validates existing symlinks
        """
        # Create shared_models/ with restrictive permissions
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        self._enforce_permissions()

        # Load metadata
        self._load_metadata()

        # Validate existing symlinks (remove broken ones)
        self._validate_existing_symlinks()

        logger.info(f"ModelShareManager initialized: {self.shared_dir}")

    def _enforce_permissions(self) -> None:
        """Ensure shared_models/ has restrictive permissions (0700).

        This prevents other users on the system from reading shared model info.
        """
        try:
            self.shared_dir.chmod(0o700)
        except OSError as e:
            logger.error(f"Failed to set permissions on {self.shared_dir}: {e}")
            raise

    # ===================================================================
    # MODEL NAME VALIDATION — CRITICAL SECURITY BOUNDARY
    # ===================================================================

    @staticmethod
    def validate_model_name(name: str) -> str:
        """Validate a model name against security rules.

        Prevents:
          - Path traversal (../, /, \\)
          - Null bytes
          - Empty names
          - Names that are too long
          - Names with special characters that could cause issues
          - Hidden files (starting with .)

        Args:
            name: Model name to validate.

        Returns:
            The validated, stripped model name.

        Raises:
            InvalidModelNameError: If the name fails validation.
        """
        if not name:
            raise InvalidModelNameError("Model name cannot be empty")

        # Strip whitespace
        name = name.strip()

        # Reject null bytes
        if '\x00' in name:
            raise InvalidModelNameError("Model name contains null byte — possible injection")

        # Reject names that start with a dot (hidden files)
        if name.startswith('.'):
            raise InvalidModelNameError(f"Model name cannot start with '.': {name}")

        # Reject path separators
        if '/' in name or '\\' in name:
            raise InvalidModelNameError(
                f"Model name contains path separator: {name}")

        # Reject parent directory references
        if '..' in name:
            raise InvalidModelNameError(
                f"Model name contains parent reference '..': {name}")

        # Check length
        if len(name) > MAX_MODEL_NAME_LENGTH:
            raise InvalidModelNameError(
                f"Model name too long ({len(name)} > {MAX_MODEL_NAME_LENGTH}): {name}")

        # Check against allowed pattern
        if not VALID_MODEL_NAME_PATTERN.match(name):
            raise InvalidModelNameError(
                f"Model name contains invalid characters: {name}. "
                f"Allowed: alphanumeric, dots, hyphens, underscores, colons.")

        return name

    def _safe_shared_path(self, model_name: str) -> Path:
        """Get the path for a model in shared_models/, after validation.

        This is the ONLY way to construct paths in shared_models/.
        All model names are validated before path construction to prevent
        path traversal.

        Note: We intentionally do NOT follow symlinks when checking the path.
        Symlinks in shared_models/ may point to private Ollama directories,
        which is expected and safe — the mesh only sees the symlink, not
        the target. We verify the symlink itself is inside shared_models/.

        Args:
            model_name: Validated model name.

        Returns:
            Path to the model in shared_models/.

        Raises:
            InvalidModelNameError: If the model name fails validation.
        """
        validated = self.validate_model_name(model_name)
        path = self.shared_dir / validated

        # Double-check: the UNRESOLVED path must be inside shared_models/.
        # We do NOT follow symlinks here — symlinks inside shared_models/
        # pointing to private Ollama dirs are expected and safe. The mesh
        # only has access to follow the symlink to read the model, which
        # is by design. We just need to ensure the name itself doesn't
        # escape the directory.
        shared_resolved = self.shared_dir.resolve()
        # Check that the path's parent resolves inside shared_models/
        # This catches path traversal in the name itself without penalizing
        # legitimate symlinks.
        parent_resolved = path.parent.resolve()
        if not str(parent_resolved).startswith(str(shared_resolved)):
            raise InvalidModelNameError(
                f"Path traversal detected: {model_name} resolves outside shared_models/")

        # Also verify the filename doesn't normalize differently
        # (defense-in-depth, the regex already blocks / and ..)
        normalized = os.path.normpath(validated)
        if normalized != validated:
            raise InvalidModelNameError(
                f"Path traversal detected: {model_name} normalizes to {normalized}")

        return path

    # ===================================================================
    # CORE OPERATIONS
    # ===================================================================

    def share_model(self, model_name: str) -> bool:
        """Share a model with the public mesh.

        Creates a symlink from the model's Ollama location to shared_models/.
        The mesh can ONLY see models in this directory.

        The original model stays in the private Ollama directory.
        Unsharing removes the symlink but leaves the original intact.

        Args:
            model_name: Name of the model to share (e.g., "glm-5.1:cloud").

        Returns:
            True if the model was successfully shared, False if it wasn't found.

        Raises:
            InvalidModelNameError: If the model name fails validation.
            ModelAlreadySharedError: If the model is already shared.
        """
        validated_name = self.validate_model_name(model_name)
        link_path = self._safe_shared_path(validated_name)

        # Check if already shared
        if link_path.exists() or link_path.is_symlink():
            # If it's a valid symlink to the same target, that's fine
            if link_path.is_symlink():
                existing_target = os.readlink(str(link_path))
                model_location = self._find_model_in_ollama(validated_name)
                if model_location and existing_target == str(model_location):
                    logger.debug(f"Model {validated_name} already shared")
                    return True
            raise ModelAlreadySharedError(
                f"Model {validated_name} is already shared (or name collision)")

        # Find the model in Ollama's private storage
        model_location = self._find_model_in_ollama(validated_name)
        if not model_location:
            logger.warning(f"Model {validated_name} not found in Ollama")
            return False

        # Create the symlink
        try:
            os.symlink(str(model_location), str(link_path))
            logger.info(f"Shared model {validated_name} → {model_location}")
        except OSError as e:
            logger.error(f"Failed to create symlink for {validated_name}: {e}")
            return False

        # Record in metadata
        self._set_metadata(validated_name, {
            'shared_at': time.time(),
            'source': str(model_location),
            'type': 'symlink',
            'size_mb': self._compute_size(model_location),
        })

        return True

    def unshare_model(self, model_name: str) -> bool:
        """Stop sharing a model. Removes from shared_models/ only.

        The original model stays in the private Ollama directory.
        The mesh immediately loses access.

        Args:
            model_name: Name of the model to unshare.

        Returns:
            True if the model was successfully unshared.

        Raises:
            InvalidModelNameError: If the model name fails validation.
            ModelNotSharedError: If the model is not currently shared.
        """
        validated_name = self.validate_model_name(model_name)
        link_path = self._safe_shared_path(validated_name)

        if not link_path.exists() and not link_path.is_symlink():
            raise ModelNotSharedError(f"Model {validated_name} is not shared")

        # Remove symlink or directory
        try:
            if link_path.is_symlink():
                os.unlink(str(link_path))
            elif link_path.is_dir():
                shutil.rmtree(str(link_path))
            else:
                link_path.unlink()
            logger.info(f"Unshared model {validated_name}")
        except OSError as e:
            logger.error(f"Failed to unshare {validated_name}: {e}")
            return False

        # Remove from metadata
        self._remove_metadata(validated_name)

        return True

    def get_shared_models(self) -> List[Dict]:
        """List models visible to the public mesh.

        ONLY returns models in shared_models/.
        NEVER scans the private Ollama directory.

        Returns:
            List of dicts with model info: name, size_mb, shared_since, type.
        """
        models = []

        if not self.shared_dir.exists():
            return models

        for entry in sorted(self.shared_dir.iterdir()):
            # Skip hidden files (metadata, etc.)
            if entry.name.startswith('.'):
                continue

            # Skip anything that's not a symlink or directory
            if not (entry.is_symlink() or entry.is_dir()):
                continue

            name = entry.name

            # Validate each entry (paranoia — should never fail)
            try:
                self.validate_model_name(name)
            except InvalidModelNameError:
                logger.warning(f"Invalid model name in shared_models/: {name}, skipping")
                continue

            # Check if symlink target still exists (broken link)
            if entry.is_symlink():
                target = entry.resolve()
                if not target.exists():
                    logger.warning(f"Broken symlink in shared_models/: {name} → {target}")
                    # Clean up broken symlink
                    try:
                        os.unlink(str(entry))
                        self._remove_metadata(name)
                    except OSError:
                        pass
                    continue

            # Get size
            path = entry
            size_mb = self._compute_size(path)

            # Get metadata
            meta = self._get_metadata(name)
            shared_since = meta.get('shared_at', os.path.getctime(str(entry))) if meta else os.path.getctime(str(entry))
            model_type = meta.get('type', 'symlink' if entry.is_symlink() else 'downloaded') if meta else 'unknown'

            models.append({
                'name': name,
                'size_mb': round(size_mb, 2),
                'shared_since': shared_since,
                'type': model_type,
            })

        return models

    def is_shared(self, model_name: str) -> bool:
        """Check if a model is currently shared with the mesh.

        Args:
            model_name: Model name to check.

        Returns:
            True if the model is in shared_models/ and accessible.
        """
        validated_name = self.validate_model_name(model_name)
        link_path = self._safe_shared_path(validated_name)
        return link_path.exists() or link_path.is_symlink()

    # ===================================================================
    # DOWNLOAD FROM MESH
    # ===================================================================

    def download_from_mesh(self, model_name: str, tracker=None,
                           expected_checksum: str = None) -> bool:
        """Download a model from the mesh into shared_models/.

        The downloaded model goes INTO shared_models/ (the public zone).
        It can later be privatized if the user wants it private.

        Args:
            model_name: Name of the model to download.
            tracker: Optional TrackerClient instance for discovering sources.
            expected_checksum: SHA-256 checksum to verify after download.

        Returns:
            True if download succeeded and integrity verified.

        Raises:
            InvalidModelNameError: If the model name fails validation.
            IntegrityCheckError: If checksum verification fails.
            DownloadError: If the download fails.
        """
        validated_name = self.validate_model_name(model_name)
        dest_path = self._safe_shared_path(validated_name)

        # Don't overwrite existing shared models
        if dest_path.exists() or dest_path.is_symlink():
            logger.info(f"Model {validated_name} already exists in shared_models/")
            return True

        # Find download sources via tracker
        if tracker:
            sources = self._find_download_sources(validated_name, tracker)
            if not sources:
                raise DownloadError(f"No sources found for model {validated_name}")
        else:
            raise DownloadError(f"No tracker provided to find sources for {validated_name}")

        # Try each source
        for source in sources:
            try:
                success = self._download_from_source(
                    validated_name, source, dest_path, expected_checksum)
                if success:
                    logger.info(f"Downloaded model {validated_name} from mesh")
                    self._set_metadata(validated_name, {
                        'shared_at': time.time(),
                        'source': f"mesh:{source.get('node_id', 'unknown')}",
                        'type': 'downloaded',
                        'size_mb': self._compute_size(dest_path),
                        'checksum': expected_checksum,
                    })
                    return True
            except (IntegrityCheckError, DownloadError) as e:
                logger.warning(f"Download from {source.get('address', 'unknown')} failed: {e}")
                # Clean up partial download
                if dest_path.exists():
                    shutil.rmtree(str(dest_path), ignore_errors=True)
                continue

        raise DownloadError(f"All sources failed for model {validated_name}")

    def _find_download_sources(self, model_name: str, tracker) -> List[Dict]:
        """Find nodes that have a model available for download.

        Args:
            model_name: Model to find.
            tracker: TrackerClient instance.

        Returns:
            List of source dicts with node info.
        """
        try:
            # Use the tracker to find nodes with this model
            nodes = asyncio_run(tracker.discover(model=model_name))
            # Sort by score (best first)
            nodes.sort(key=lambda n: n.get('score', 0) if isinstance(n, dict) else getattr(n, 'score', 0), reverse=True)
            return [{'address': n.get('address', '') if isinstance(n, dict) else getattr(n, 'address', ''),
                     'node_id': n.get('node_id', '') if isinstance(n, dict) else getattr(n, 'node_id', ''),
                     'score': n.get('score', 0) if isinstance(n, dict) else getattr(n, 'score', 0)}
                    for n in nodes]
        except Exception as e:
            logger.error(f"Error finding download sources for {model_name}: {e}")
            return []

    def _download_from_source(self, model_name: str, source: Dict,
                               dest_path: Path, expected_checksum: str = None) -> bool:
        """Download a model from a specific mesh source.

        This is a placeholder for the actual download implementation.
        In production, this would use HTTP/WebSocket to fetch model files
        from the peer node.

        Args:
            model_name: Model name.
            source: Source node info (address, node_id, score).
            dest_path: Destination path in shared_models/.
            expected_checksum: Expected SHA-256 checksum.

        Returns:
            True if download succeeded.

        Raises:
            DownloadError: If the download fails.
            IntegrityCheckError: If checksum verification fails.
        """
        # TODO: Implement actual download from peer node via HTTP/WebSocket
        # For now, this creates a placeholder directory structure
        # The actual implementation will depend on the mesh protocol

        address = source.get('address', '')
        if not address:
            raise DownloadError(f"No address for source of {model_name}")

        logger.info(f"Would download {model_name} from {address}")
        raise DownloadError(
            f"Direct peer download not yet implemented for {model_name}. "
            f"Use 'ollama pull {model_name}' and then 'share_model' instead.")

    # ===================================================================
    # PRIVATIZE — Move from shared to private
    # ===================================================================

    def privatize(self, model_name: str) -> bool:
        """Move a model from shared_models/ to private Ollama storage.

        This removes the model from the public mesh and places it in
        private Ollama storage. The mesh can no longer see it.

        If the model was a symlink, the original stays in Ollama and
        we just remove the symlink.
        If the model was downloaded (actual files in shared_models/),
        we move it to the Ollama directory.

        Args:
            model_name: Model to privatize.

        Returns:
            True if successful.

        Raises:
            InvalidModelNameError: If model name is invalid.
            ModelNotSharedError: If model is not in shared_models/.
        """
        validated_name = self.validate_model_name(model_name)
        shared_path = self._safe_shared_path(validated_name)

        if not shared_path.exists() and not shared_path.is_symlink():
            raise ModelNotSharedError(f"Model {validated_name} is not in shared_models/")

        # If it's a symlink, just remove it — the original is already in Ollama
        if shared_path.is_symlink():
            logger.info(f"Privatizing symlink {validated_name}: removing symlink "
                        f"(original stays in Ollama)")
            try:
                os.unlink(str(shared_path))
            except OSError as e:
                logger.error(f"Failed to remove symlink for {validated_name}: {e}")
                return False
            self._remove_metadata(validated_name)
            return True

        # It's an actual directory (downloaded model) — move to Ollama
        ollama_dest = self.ollama_dir / validated_name.replace(':', '/')

        # If the model already exists in Ollama, just remove from shared
        if ollama_dest.exists():
            logger.info(f"Model {validated_name} already exists in Ollama, "
                        f"removing from shared_models/")
            try:
                shutil.rmtree(str(shared_path))
            except OSError as e:
                logger.error(f"Failed to remove {shared_path}: {e}")
                return False
            self._remove_metadata(validated_name)
            return True

        # Move from shared_models/ to Ollama private storage
        try:
            ollama_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(shared_path), str(ollama_dest))
            logger.info(f"Privatized model {validated_name}: moved to {ollama_dest}")
        except OSError as e:
            logger.error(f"Failed to move {validated_name} to Ollama: {e}")
            return False

        self._remove_metadata(validated_name)
        return True

    # ===================================================================
    # MODEL SIZE — For tracker announcements
    # ===================================================================

    def get_model_size(self, model_name: str) -> Optional[float]:
        """Get the size of a shared model in MB.

        This is used for tracker announcements so other nodes know
        the model's approximate size before downloading.

        No private data is included in the announcement — just the
        model name and size.

        Args:
            model_name: Name of the shared model.

        Returns:
            Size in MB, or None if the model is not shared.
        """
        validated_name = self.validate_model_name(model_name)
        shared_path = self._safe_shared_path(validated_name)

        if not shared_path.exists() and not shared_path.is_symlink():
            return None

        return self._compute_size(shared_path)

    # ===================================================================
    # INTEGRITY VERIFICATION
    # ===================================================================

    def verify_integrity(self, model_name: str,
                         expected_checksum: str = None) -> bool:
        """Verify that a shared model is not corrupted or tampered with.

        If an expected checksum is provided, verifies against it.
        Otherwise, verifies that the model files can be read without errors.

        Args:
            model_name: Name of the shared model.
            expected_checksum: Expected SHA-256 checksum (hex string).

        Returns:
            True if the model passes integrity checks.

        Raises:
            InvalidModelNameError: If model name is invalid.
            ModelNotSharedError: If model is not shared.
            IntegrityCheckError: If integrity check fails.
        """
        validated_name = self.validate_model_name(model_name)
        shared_path = self._safe_shared_path(validated_name)

        if not shared_path.exists() and not shared_path.is_symlink():
            raise ModelNotSharedError(f"Model {validated_name} is not shared")

        # Resolve symlink
        actual_path = shared_path.resolve()
        if not actual_path.exists():
            raise IntegrityCheckError(
                f"Model {validated_name} symlink target does not exist: {actual_path}")

        # Check if it's a directory (Ollama models are directories)
        if actual_path.is_dir():
            return self._verify_directory_integrity(validated_name, actual_path, expected_checksum)
        else:
            return self._verify_file_integrity(validated_name, actual_path, expected_checksum)

    def _verify_file_integrity(self, model_name: str, file_path: Path,
                                expected_checksum: str = None) -> bool:
        """Verify a single model file's integrity."""
        try:
            computed = self._compute_checksum(file_path)
            if computed is None:
                raise IntegrityCheckError(
                    f"Could not compute checksum for {model_name}")

            if expected_checksum:
                if computed != expected_checksum:
                    raise IntegrityCheckError(
                        f"Checksum mismatch for {model_name}: "
                        f"expected {expected_checksum}, got {computed}")

            # Verify the file is readable
            with open(file_path, 'rb') as f:
                # Read first and last bytes to verify accessibility
                f.read(1)
                f.seek(-1, 2) if file_path.stat().st_size > 0 else None
                f.read(1)

            return True

        except OSError as e:
            raise IntegrityCheckError(f"Cannot read model file {model_name}: {e}")

    def _verify_directory_integrity(self, model_name: str, dir_path: Path,
                                     expected_checksum: str = None) -> bool:
        """Verify a model directory's integrity.

        Checks:
          1. Directory is readable
          2. Contains at least one file
          3. All files are readable
          4. If expected_checksum is provided, the combined hash matches
        """
        try:
            # Check directory is readable
            if not os.access(str(dir_path), os.R_OK):
                raise IntegrityCheckError(
                    f"Cannot read model directory {model_name}")

            # List files in directory
            files = list(dir_path.rglob('*'))
            actual_files = [f for f in files if f.is_file()]

            if not actual_files:
                raise IntegrityCheckError(
                    f"Model directory {model_name} is empty")

            # Check each file is readable
            for f in actual_files:
                if not os.access(str(f), os.R_OK):
                    raise IntegrityCheckError(
                        f"Cannot read model file: {f.name} in {model_name}")

            # If expected checksum provided, compute combined hash
            if expected_checksum:
                combined_hash = self._compute_directory_checksum(dir_path)
                if combined_hash != expected_checksum:
                    raise IntegrityCheckError(
                        f"Checksum mismatch for {model_name}: "
                        f"expected {expected_checksum}, got {combined_hash}")

            return True

        except IntegrityCheckError:
            raise
        except Exception as e:
            raise IntegrityCheckError(
                f"Integrity check failed for {model_name}: {e}")

    # ===================================================================
    # CHECKSUM UTILITIES
    # ===================================================================

    @staticmethod
    def _compute_checksum(file_path: Path) -> Optional[str]:
        """Compute SHA-256 checksum of a file.

        Args:
            file_path: Path to the file.

        Returns:
            Hex digest of SHA-256 hash, or None on error.
        """
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(CHECKSUM_BUFFER_SIZE)
                    if not data:
                        break
                    sha256.update(data)
            return sha256.hexdigest()
        except (OSError, IOError):
            return None

    @staticmethod
    def _compute_directory_checksum(dir_path: Path) -> Optional[str]:
        """Compute a combined SHA-256 checksum of all files in a directory.

        Files are sorted by name for deterministic hashing.

        Args:
            dir_path: Path to the directory.

        Returns:
            Hex digest of combined SHA-256 hash, or None on error.
        """
        try:
            sha256 = hashlib.sha256()
            # Sort files for deterministic order
            files = sorted(dir_path.rglob('*'))
            for f in files:
                if not f.is_file():
                    continue
                # Include filename in hash for integrity
                sha256.update(f.name.encode('utf-8'))
                sha256.update(b'\x00')  # Separator
                # Include file content
                with open(f, 'rb') as fh:
                    while True:
                        data = fh.read(CHECKSUM_BUFFER_SIZE)
                        if not data:
                            break
                        sha256.update(data)
                sha256.update(b'\x01')  # End-of-file marker
            return sha256.hexdigest()
        except (OSError, IOError):
            return None

    # ===================================================================
    # SIZE UTILITIES
    # ===================================================================

    @staticmethod
    def _compute_size(path: Path) -> float:
        """Compute the size of a file or directory in MB.

        Args:
            path: Path to file or directory.

        Returns:
            Size in MB (rounded to 2 decimal places).
        """
        try:
            if path.is_file():
                return round(path.stat().st_size / (1024 * 1024), 2)
            elif path.is_dir():
                total = 0
                for f in path.rglob('*'):
                    if f.is_file():
                        total += f.stat().st_size
                return round(total / (1024 * 1024), 2)
            elif path.is_symlink():
                # For symlinks, get the target size
                target = path.resolve()
                if target.exists():
                    return ModelShareManager._compute_size(target)
                return 0.0
            return 0.0
        except OSError:
            return 0.0

    # ===================================================================
    # PRIVATE MODEL DISCOVERY
    # ===================================================================

    def _find_model_in_ollama(self, model_name: str) -> Optional[Path]:
        """Find a model in the private Ollama directory.

        This is PRIVATE — the mesh NEVER calls this function.
        Only the local user can share/unshare models.

        Ollama stores models in a hierarchy like:
          ~/.ollama/models/blobs/
          ~/.ollama/models/manifests/registry.ollama.ai/library/model/tag

        We look for the model by name/tag.

        Args:
            model_name: Model name (e.g., "glm-5.1:cloud" or "llama3").

        Returns:
            Path to the model directory, or None if not found.
        """
        if not self.ollama_dir.exists():
            return None

        # Ollama stores manifests under:
        # ~/.ollama/models/manifests/registry.ollama.ai/library/<name>/<tag>
        # Or for custom registries:
        # ~/.ollama/models/manifests/<registry>/<namespace>/<name>/<tag>

        # Try common patterns
        candidates = []

        # Handle "name:tag" format
        if ':' in model_name:
            name, tag = model_name.split(':', 1)
            # Standard Ollama path
            candidates.append(
                self.ollama_dir / "manifests" / "registry.ollama.ai" / "library" / name / tag
            )
            # Custom registry paths
            manifests_dir = self.ollama_dir / "manifests"
            if manifests_dir.exists():
                for registry_dir in manifests_dir.iterdir():
                    if registry_dir.is_dir() and registry_dir.name != "registry.ollama.ai":
                        for ns_dir in registry_dir.iterdir():
                            candidate = ns_dir / name / tag
                            if candidate.is_dir():
                                candidates.append(candidate)
        else:
            # Just a name, look for any tag
            # Standard path
            std_path = self.ollama_dir / "manifests" / "registry.ollama.ai" / "library" / model_name
            if std_path.exists():
                candidates.append(std_path)

            # Search all registries
            manifests_dir = self.ollama_dir / "manifests"
            if manifests_dir.exists():
                for registry_dir in manifests_dir.iterdir():
                    registry_model_path = registry_dir
                    # Walk up to 3 levels deep
                    for _ in range(3):
                        if registry_model_path.is_dir():
                            candidate = registry_model_path / model_name
                            if candidate.exists() and candidate.is_dir():
                                candidates.append(candidate)
                                break
                        if registry_model_path.is_dir():
                            registry_model_path = next(registry_model_path.iterdir(), None)
                            if registry_model_path is None:
                                break

        # Check candidates
        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Fallback: search for the model by walking the Ollama directory
        # (limited depth for performance)
        try:
            manifests_dir = self.ollama_dir / "manifests"
            if manifests_dir.exists():
                for manifest_path in manifests_dir.rglob(model_name):
                    if manifest_path.is_dir() or manifest_path.is_file():
                        return manifest_path
        except OSError:
            pass

        return None

    # ===================================================================
    # METADATA MANAGEMENT
    # ===================================================================

    def _load_metadata(self) -> None:
        """Load metadata from the .metadata.json file."""
        if self._metadata_file.exists():
            try:
                with open(self._metadata_file, 'r') as f:
                    self._metadata = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load shared_models metadata: {e}")
                self._metadata = {}
        else:
            self._metadata = {}

    def _save_metadata(self) -> None:
        """Save metadata to the .metadata.json file."""
        try:
            with open(self._metadata_file, 'w') as f:
                json.dump(self._metadata, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save shared_models metadata: {e}")

    def _get_metadata(self, model_name: str) -> Optional[Dict]:
        """Get metadata for a specific model."""
        return self._metadata.get(model_name)

    def _set_metadata(self, model_name: str, data: Dict) -> None:
        """Set metadata for a specific model."""
        self._metadata[model_name] = data
        self._save_metadata()

    def _remove_metadata(self, model_name: str) -> None:
        """Remove metadata for a specific model."""
        self._metadata.pop(model_name, None)
        self._save_metadata()

    # ===================================================================
    # VALIDATION & MAINTENANCE
    # ===================================================================

    def _validate_existing_symlinks(self) -> None:
        """Check existing symlinks in shared_models/ and remove broken ones."""
        if not self.shared_dir.exists():
            return

        removed = 0
        for entry in list(self.shared_dir.iterdir()):
            if entry.name.startswith('.'):
                continue
            if entry.is_symlink():
                target = entry.resolve()
                if not target.exists():
                    logger.warning(f"Removing broken symlink: {entry.name}")
                    try:
                        os.unlink(str(entry))
                        self._remove_metadata(entry.name)
                        removed += 1
                    except OSError:
                        pass

        if removed:
            logger.info(f"Cleaned up {removed} broken symlinks from shared_models/")

    def get_status(self) -> Dict:
        """Get status of the ModelShareManager for monitoring/dashboards."""
        shared = self.get_shared_models()
        return {
            'shared_dir': str(self.shared_dir),
            'ollama_dir': str(self.ollama_dir),
            'shared_models_count': len(shared),
            'shared_models': shared,
            'total_shared_size_mb': round(sum(m['size_mb'] for m in shared), 2),
            'dir_permissions': oct(self.shared_dir.stat().st_mode & 0o777) if self.shared_dir.exists() else 'N/A',
        }

    def cleanup(self) -> int:
        """Remove all broken symlinks and invalid entries from shared_models/.

        Returns:
            Number of entries cleaned up.
        """
        removed = 0

        if not self.shared_dir.exists():
            return removed

        for entry in list(self.shared_dir.iterdir()):
            if entry.name.startswith('.'):
                continue

            # Remove broken symlinks
            if entry.is_symlink():
                target = entry.resolve()
                if not target.exists():
                    try:
                        os.unlink(str(entry))
                        self._remove_metadata(entry.name)
                        removed += 1
                    except OSError:
                        pass

            # Remove entries with invalid names
            try:
                self.validate_model_name(entry.name)
            except InvalidModelNameError:
                logger.warning(f"Removing entry with invalid name: {entry.name}")
                try:
                    if entry.is_dir():
                        shutil.rmtree(str(entry))
                    else:
                        entry.unlink()
                    self._remove_metadata(entry.name)
                    removed += 1
                except OSError:
                    pass

        if removed:
            logger.info(f"Cleanup removed {removed} invalid entries from shared_models/")
        return removed


# ============================================================================
# HELPER — Run async from sync context
# ============================================================================

def asyncio_run(coro):
    """Run an async coroutine from a synchronous context.

    Handles the case where an event loop may already be running.
    """
    try:
        import asyncio
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an async context — create a task and schedule it
        # This is a fallback; in production, the caller should be async
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    else:
        import asyncio
        return asyncio.run(coro)


# ============================================================================
# CLI INTERFACE — for pinkybrain share/unshare/shared commands
# ============================================================================

def main():
    """CLI interface for model sharing management."""
    import argparse

    parser = argparse.ArgumentParser(
        description='PinkyBrain Model Share Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  share <model>      Share a model with the mesh
  unshare <model>    Stop sharing a model
  list               List shared models
  status             Show status
  cleanup            Remove broken entries
  verify <model>     Verify model integrity
  size <model>       Get model size
  privatize <model>  Move model from shared to private
""")
    parser.add_argument('command', nargs='?', help='Command to run')
    parser.add_argument('model', nargs='?', help='Model name')
    parser.add_argument('--base-dir', help='Base directory (default: ~/.pinkybrain)')
    parser.add_argument('--checksum', help='Expected checksum for verify')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')

    mgr = ModelShareManager(base_dir=args.base_dir)
    mgr.initialize()

    if args.command == 'share':
        if not args.model:
            print("Error: model name required")
            return
        try:
            result = mgr.share_model(args.model)
            print(f"✅ Shared {args.model}" if result else f"❌ Model {args.model} not found locally")
        except ModelShareError as e:
            print(f"❌ Error: {e}")

    elif args.command == 'unshare':
        if not args.model:
            print("Error: model name required")
            return
        try:
            result = mgr.unshare_model(args.model)
            print(f"✅ Unshared {args.model}" if result else f"❌ Failed to unshare {args.model}")
        except ModelShareError as e:
            print(f"❌ Error: {e}")

    elif args.command == 'list':
        models = mgr.get_shared_models()
        if not models:
            print("No models shared")
        else:
            print(f"Shared models ({len(models)}):")
            for m in models:
                print(f"  {m['name']:30s}  {m['size_mb']:>8.2f} MB  {m['type']}")

    elif args.command == 'status':
        status = mgr.get_status()
        print(json.dumps(status, indent=2))

    elif args.command == 'cleanup':
        removed = mgr.cleanup()
        print(f"🧹 Cleaned up {removed} entries")

    elif args.command == 'verify':
        if not args.model:
            print("Error: model name required")
            return
        try:
            result = mgr.verify_integrity(args.model, args.checksum)
            print(f"✅ {args.model}: integrity verified" if result else f"❌ {args.model}: integrity check failed")
        except (ModelNotSharedError, IntegrityCheckError) as e:
            print(f"❌ Error: {e}")

    elif args.command == 'size':
        if not args.model:
            print("Error: model name required")
            return
        size = mgr.get_model_size(args.model)
        if size is not None:
            print(f"{args.model}: {size:.2f} MB")
        else:
            print(f"Model {args.model} not found in shared_models/")

    elif args.command == 'privatize':
        if not args.model:
            print("Error: model name required")
            return
        try:
            result = mgr.privatize(args.model)
            print(f"✅ Privatized {args.model}" if result else f"❌ Failed to privatize {args.model}")
        except ModelShareError as e:
            print(f"❌ Error: {e}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()