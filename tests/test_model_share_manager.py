#!/usr/bin/env python3
"""
🧪 Tests for ModelShareManager — PinkyBrain v5
================================================
Tests the boundary between private models and the public mesh.

Security tests are first-class citizens here. If a path traversal
or data leak test fails, the whole module is compromised.
"""

import hashlib
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from model_share_manager import (
    ModelShareManager,
    InvalidModelNameError,
    ModelNotFoundError,
    ModelAlreadySharedError,
    ModelNotSharedError,
    IntegrityCheckError,
    DownloadError,
    VALID_MODEL_NAME_PATTERN,
)


class TestModelNameValidation(unittest.TestCase):
    """Test model name validation — CRITICAL security boundary."""

    def setUp(self):
        self.mgr = ModelShareManager(
            base_dir=tempfile.mkdtemp(),
            ollama_dir=tempfile.mkdtemp()
        )
        self.mgr.initialize()

    def tearDown(self):
        shutil.rmtree(str(self.mgr.base_dir), ignore_errors=True)
        shutil.rmtree(str(self.mgr.ollama_dir), ignore_errors=True)

    # --- Valid names ---

    def test_simple_name(self):
        """Simple alphanumeric names should be valid."""
        self.assertEqual(self.mgr.validate_model_name("llama3"), "llama3")

    def test_name_with_dots(self):
        """Names with dots should be valid."""
        self.assertEqual(self.mgr.validate_model_name("glm-5.1"), "glm-5.1")

    def test_name_with_colon(self):
        """Names with colons (Ollama tags) should be valid."""
        self.assertEqual(self.mgr.validate_model_name("glm-5.1:cloud"), "glm-5.1:cloud")

    def test_name_with_hyphens(self):
        self.assertEqual(self.mgr.validate_model_name("mistral-7b"), "mistral-7b")

    def test_name_with_underscores(self):
        self.assertEqual(self.mgr.validate_model_name("my_model"), "my_model")

    def test_name_with_numbers(self):
        self.assertEqual(self.mgr.validate_model_name("model123"), "model123")

    def test_strips_whitespace(self):
        self.assertEqual(self.mgr.validate_model_name("  llama3  "), "llama3")

    # --- Invalid names — security critical ---

    def test_empty_name(self):
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("")

    def test_whitespace_only(self):
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("   ")

    def test_path_traversal_dotdot(self):
        """Path traversal with .. must be rejected."""
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("../../../etc/passwd")

    def test_path_traversal_mixed(self):
        """Mixed path traversal must be rejected."""
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("models/../../../etc")

    def test_absolute_path(self):
        """Absolute paths must be rejected."""
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("/etc/passwd")

    def test_backslash_path(self):
        """Windows-style paths must be rejected."""
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("..\\..\\windows\\system32")

    def test_null_byte(self):
        """Null bytes must be rejected (injection attack)."""
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("model\x00malicious")

    def test_hidden_file(self):
        """Names starting with . must be rejected (hidden files)."""
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name(".hidden")

    def test_name_too_long(self):
        """Names exceeding max length must be rejected."""
        long_name = "a" * 200
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name(long_name)

    def test_special_characters(self):
        """Names with shell-special characters must be rejected."""
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("model;rm -rf /")

    def test_pipe_character(self):
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("model|cat /etc/passwd")

    def test_dollar_sign(self):
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("model$HOME")

    def test_backtick(self):
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("model`whoami`")

    def test_newline(self):
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("model\nmalicious")

    def test_double_slash(self):
        with self.assertRaises(InvalidModelNameError):
            self.mgr.validate_model_name("models//etc/passwd")


class TestSafePathConstruction(unittest.TestCase):
    """Test that _safe_shared_path prevents path traversal."""

    def setUp(self):
        self.mgr = ModelShareManager(
            base_dir=tempfile.mkdtemp(),
            ollama_dir=tempfile.mkdtemp()
        )
        self.mgr.initialize()

    def tearDown(self):
        shutil.rmtree(str(self.mgr.base_dir), ignore_errors=True)
        shutil.rmtree(str(self.mgr.ollama_dir), ignore_errors=True)

    def test_safe_path_normal_name(self):
        """Normal model names should resolve inside shared_models/."""
        path = self.mgr._safe_shared_path("llama3")
        self.assertTrue(str(path).startswith(str(self.mgr.shared_dir)))

    def test_safe_path_rejects_traversal(self):
        """Path traversal attempts must be caught."""
        with self.assertRaises(InvalidModelNameError):
            self.mgr._safe_shared_path("../../etc/passwd")

    def test_safe_path_rejects_slash(self):
        with self.assertRaises(InvalidModelNameError):
            self.mgr._safe_shared_path("subdir/model")

    def test_safe_path_with_colon_tag(self):
        """Ollama-style names with colons should work."""
        path = self.mgr._safe_shared_path("glm-5.1:cloud")
        expected = self.mgr.shared_dir / "glm-5.1:cloud"
        self.assertEqual(path, expected)


class TestDirectoryPermissions(unittest.TestCase):
    """Test that shared_models/ is created with correct permissions."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_shared_dir_exists(self):
        self.assertTrue(self.mgr.shared_dir.exists())

    def test_shared_dir_is_directory(self):
        self.assertTrue(self.mgr.shared_dir.is_dir())

    def test_shared_dir_permissions_0700(self):
        """shared_models/ must have 0700 permissions (owner only)."""
        mode = self.mgr.shared_dir.stat().st_mode & 0o777
        # On some systems, umask may affect this, but we enforce it
        self.assertEqual(mode, 0o700,
                         f"Expected 0700 permissions, got {oct(mode)}")


class TestShareModel(unittest.TestCase):
    """Test share_model functionality."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

        # Create a fake Ollama model
        self.model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "test-model" / "latest"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        (self.model_dir / "config.json").write_text('{"test": true}')
        (self.model_dir / "weights.bin").write_bytes(b'\x00' * 1024)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_share_model_creates_symlink(self):
        """share_model should create a symlink in shared_models/."""
        result = self.mgr.share_model("test-model:latest")
        self.assertTrue(result)
        link_path = self.mgr.shared_dir / "test-model:latest"
        self.assertTrue(link_path.is_symlink())

    def test_share_model_symlink_points_to_original(self):
        """The symlink should point to the original model location."""
        self.mgr.share_model("test-model:latest")
        link_path = self.mgr.shared_dir / "test-model:latest"
        target = link_path.resolve()
        self.assertTrue(target.exists())

    def test_share_model_not_found(self):
        """Sharing a model that doesn't exist should return False."""
        result = self.mgr.share_model("nonexistent-model")
        self.assertFalse(result)

    def test_share_model_already_shared_idempotent(self):
        """Sharing a model that's already shared returns True (idempotent)."""
        result1 = self.mgr.share_model("test-model:latest")
        self.assertTrue(result1)
        # Re-sharing the same model with same target is idempotent
        result2 = self.mgr.share_model("test-model:latest")
        self.assertTrue(result2)

    def test_share_model_name_collision(self):
        """Sharing when a non-symlink entry already exists raises error."""
        self.mgr.share_model("test-model:latest")
        self.mgr.unshare_model("test-model:latest")
        # Create a blocking directory (not a symlink) in shared_models/
        blocking_dir = self.mgr.shared_dir / "test-model:latest"
        blocking_dir.mkdir()
        (blocking_dir / "weights.bin").write_bytes(b'\x00' * 512)
        # Now try to share — the name already has a non-symlink entry
        with self.assertRaises(ModelAlreadySharedError):
            self.mgr.share_model("test-model:latest")

    def test_share_model_invalid_name(self):
        """Sharing with an invalid name should raise InvalidModelNameError."""
        with self.assertRaises(InvalidModelNameError):
            self.mgr.share_model("../../etc/passwd")

    def test_original_stays_intact(self):
        """The original model must not be modified when sharing."""
        original_path = self.model_dir
        original_config = (original_path / "config.json").read_text()
        self.mgr.share_model("test-model:latest")
        # Original should still exist and be unchanged
        self.assertTrue(original_path.exists())
        self.assertEqual((original_path / "config.json").read_text(), original_config)


class TestUnshareModel(unittest.TestCase):
    """Test unshare_model functionality."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

        # Create a fake Ollama model and share it
        self.model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "test-model" / "latest"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        (self.model_dir / "weights.bin").write_bytes(b'\x00' * 1024)
        self.mgr.share_model("test-model:latest")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_unshare_removes_symlink(self):
        """unshare_model should remove the symlink from shared_models/."""
        self.assertTrue(self.mgr.is_shared("test-model:latest"))
        result = self.mgr.unshare_model("test-model:latest")
        self.assertTrue(result)
        self.assertFalse(self.mgr.is_shared("test-model:latest"))

    def test_unshare_preserves_original(self):
        """The original model must remain intact after unsharing."""
        self.mgr.unshare_model("test-model:latest")
        self.assertTrue(self.model_dir.exists())
        self.assertTrue((self.model_dir / "weights.bin").exists())

    def test_unshare_not_shared(self):
        """Unsharing a model that's not shared should raise error."""
        with self.assertRaises(ModelNotSharedError):
            self.mgr.unshare_model("never-shared-model")

    def test_unshare_invalid_name(self):
        with self.assertRaises(InvalidModelNameError):
            self.mgr.unshare_model("../evil")


class TestGetSharedModels(unittest.TestCase):
    """Test get_shared_models functionality."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

        # Create and share two models
        for name in ["model-a", "model-b"]:
            model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / name / "latest"
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / "weights.bin").write_bytes(b'\x00' * 2048)
            self.mgr.share_model(f"{name}:latest")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_list_shared_models(self):
        """Should list all shared models."""
        models = self.mgr.get_shared_models()
        self.assertEqual(len(models), 2)
        names = {m['name'] for m in models}
        self.assertIn("model-a:latest", names)
        self.assertIn("model-b:latest", names)

    def test_shared_models_have_size(self):
        """Each shared model should have a size."""
        models = self.mgr.get_shared_models()
        for m in models:
            self.assertIn('size_mb', m)
            self.assertIsInstance(m['size_mb'], float)

    def test_shared_models_have_type(self):
        models = self.mgr.get_shared_models()
        for m in models:
            self.assertEqual(m['type'], 'symlink')

    def test_hidden_files_not_listed(self):
        """Metadata files (starting with .) should not appear in listing."""
        # Create a hidden file in shared_models/
        (self.mgr.shared_dir / ".hidden_file").write_text("should not appear")
        models = self.mgr.get_shared_models()
        names = {m['name'] for m in models}
        self.assertNotIn(".hidden_file", names)

    def test_broken_symlinks_cleaned_up(self):
        """Broken symlinks should be cleaned up during listing."""
        # Create a symlink to a nonexistent target
        target = Path(self.base) / "nonexistent_target"
        link = self.mgr.shared_dir / "broken-model"
        os.symlink(str(target), str(link))

        # The broken symlink should be cleaned up
        models = self.mgr.get_shared_models()
        names = {m['name'] for m in models}
        self.assertNotIn("broken-model", names)
        self.assertFalse(link.exists())


class TestPrivatize(unittest.TestCase):
    """Test privatize functionality — moving from shared to private."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

        # Create and share a model (symlink)
        self.model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "test-model" / "latest"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        (self.model_dir / "weights.bin").write_bytes(b'\x00' * 2048)

        # Also create a downloaded model in shared_models/ (actual directory)
        self.downloaded_dir = self.mgr.shared_dir / "downloaded-model"
        self.downloaded_dir.mkdir()
        (self.downloaded_dir / "weights.bin").write_bytes(b'\x00' * 4096)
        self.mgr._set_metadata("downloaded-model", {
            'shared_at': 0, 'source': 'mesh:node123', 'type': 'downloaded', 'size_mb': 0.0
        })

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_privatize_symlink(self):
        """Privatizing a symlink should just remove the symlink."""
        self.mgr.share_model("test-model:latest")
        self.assertTrue(self.mgr.is_shared("test-model:latest"))

        result = self.mgr.privatize("test-model:latest")
        self.assertTrue(result)
        self.assertFalse(self.mgr.is_shared("test-model:latest"))
        # Original should still exist
        self.assertTrue(self.model_dir.exists())

    def test_privatize_downloaded_model(self):
        """Privatizing a downloaded model should move it to Ollama private storage."""
        self.assertTrue(self.mgr.is_shared("downloaded-model"))

        result = self.mgr.privatize("downloaded-model")
        self.assertTrue(result)
        # Should no longer be in shared_models/
        self.assertFalse(self.mgr.is_shared("downloaded-model"))
        # Should be in Ollama private storage
        private_path = self.mgr.ollama_dir / "downloaded-model"
        self.assertTrue(private_path.exists())

    def test_privatize_not_shared(self):
        """Privatizing a model that's not shared should raise error."""
        with self.assertRaises(ModelNotSharedError):
            self.mgr.privatize("never-shared")


class TestModelSize(unittest.TestCase):
    """Test get_model_size functionality."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

        # Create and share a model
        self.model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "big-model" / "v1"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        (self.model_dir / "weights.bin").write_bytes(b'\x00' * (5 * 1024 * 1024))  # 5 MB
        self.mgr.share_model("big-model:v1")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_get_model_size_shared(self):
        """Should return size for a shared model."""
        size = self.mgr.get_model_size("big-model:v1")
        self.assertIsNotNone(size)
        self.assertGreater(size, 0)

    def test_get_model_size_not_shared(self):
        """Should return None for a model that's not shared."""
        size = self.mgr.get_model_size("nonexistent")
        self.assertIsNone(size)

    def test_get_model_size_invalid_name(self):
        with self.assertRaises(InvalidModelNameError):
            self.mgr.get_model_size("../../etc/passwd")


class TestVerifyIntegrity(unittest.TestCase):
    """Test verify_integrity functionality."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

        # Create and share a model
        self.model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "verify-model" / "v1"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        (self.model_dir / "weights.bin").write_bytes(b'test data for checksum')
        self.mgr.share_model("verify-model:v1")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_verify_integrity_ok(self):
        """A valid shared model should pass integrity check."""
        result = self.mgr.verify_integrity("verify-model:v1")
        self.assertTrue(result)

    def test_verify_integrity_with_checksum(self):
        """Should verify against a provided checksum."""
        # Compute expected checksum
        weights_file = self.model_dir / "weights.bin"
        expected = hashlib.sha256(weights_file.read_bytes()).hexdigest()

        # For a directory, compute combined checksum
        expected_dir = self.mgr._compute_directory_checksum(self.model_dir)
        result = self.mgr.verify_integrity("verify-model:v1", expected_checksum=expected_dir)
        self.assertTrue(result)

    def test_verify_integrity_wrong_checksum(self):
        """Should fail if checksum doesn't match."""
        with self.assertRaises(IntegrityCheckError):
            self.mgr.verify_integrity("verify-model:v1", expected_checksum="0000deadbeef")

    def test_verify_not_shared(self):
        """Should raise error for non-shared model."""
        with self.assertRaises(ModelNotSharedError):
            self.mgr.verify_integrity("nonexistent-model")

    def test_verify_broken_symlink(self):
        """Should fail if symlink target is broken."""
        # Create a symlink to a removed target
        target = Path(self.base) / "removed_target"
        target.mkdir()
        link = self.mgr.shared_dir / "broken-link"
        os.symlink(str(target), str(link))
        shutil.rmtree(str(target))

        with self.assertRaises(IntegrityCheckError):
            self.mgr.verify_integrity("broken-link")


class TestCleanup(unittest.TestCase):
    """Test cleanup functionality."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_cleanup_removes_broken_symlinks(self):
        """Broken symlinks should be removed during cleanup."""
        # Create a broken symlink
        target = Path(self.base) / "nonexistent"
        link = self.mgr.shared_dir / "broken-model"
        os.symlink(str(target), str(link))

        removed = self.mgr.cleanup()
        self.assertEqual(removed, 1)
        self.assertFalse(link.exists())

    def test_cleanup_removes_invalid_names(self):
        """Entries with invalid model names should be removed."""
        # Create a file with an invalid name (path traversal)
        evil = self.mgr.shared_dir / "../evil"
        # This might not create outside the dir, so create a file with special chars
        invalid = self.mgr.shared_dir / "model;rm -rf"
        invalid.mkdir()

        removed = self.mgr.cleanup()
        self.assertGreaterEqual(removed, 1)

    def test_cleanup_preserves_valid_models(self):
        """Valid shared models should not be removed during cleanup."""
        # Create a valid model and share it
        model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "good-model" / "v1"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_bytes(b'\x00' * 512)
        self.mgr.share_model("good-model:v1")

        removed = self.mgr.cleanup()
        self.assertEqual(removed, 0)
        self.assertTrue(self.mgr.is_shared("good-model:v1"))


class TestMetadata(unittest.TestCase):
    """Test metadata management."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_metadata_persists(self):
        """Metadata should persist across re-initializations."""
        # Create and share a model
        model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "persist-test" / "v1"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_bytes(b'\x00' * 512)
        self.mgr.share_model("persist-test:v1")

        # Check metadata exists
        meta = self.mgr._get_metadata("persist-test:v1")
        self.assertIsNotNone(meta)
        self.assertIn('shared_at', meta)

        # Re-initialize and check metadata still exists
        mgr2 = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        mgr2.initialize()
        meta2 = mgr2._get_metadata("persist-test:v1")
        self.assertIsNotNone(meta2)
        self.assertEqual(meta['shared_at'], meta2['shared_at'])

    def test_metadata_removed_on_unshare(self):
        """Metadata should be removed when unsharing."""
        model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "rm-test" / "v1"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_bytes(b'\x00' * 512)
        self.mgr.share_model("rm-test:v1")

        meta = self.mgr._get_metadata("rm-test:v1")
        self.assertIsNotNone(meta)

        self.mgr.unshare_model("rm-test:v1")
        meta = self.mgr._get_metadata("rm-test:v1")
        self.assertIsNone(meta)


class TestIsShared(unittest.TestCase):
    """Test is_shared check."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

        # Create and share a model
        model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "shared-model" / "v1"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_bytes(b'\x00' * 512)
        self.mgr.share_model("shared-model:v1")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_is_shared_true(self):
        self.assertTrue(self.mgr.is_shared("shared-model:v1"))

    def test_is_shared_false(self):
        self.assertFalse(self.mgr.is_shared("nonexistent-model"))

    def test_is_shared_after_unshare(self):
        self.mgr.unshare_model("shared-model:v1")
        self.assertFalse(self.mgr.is_shared("shared-model:v1"))


class TestGetStatus(unittest.TestCase):
    """Test get_status output."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

        # Create and share a model
        model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "status-model" / "v1"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_bytes(b'\x00' * 1024)
        self.mgr.share_model("status-model:v1")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_status_contains_shared_dir(self):
        status = self.mgr.get_status()
        self.assertIn('shared_dir', status)
        self.assertEqual(status['shared_dir'], str(self.mgr.shared_dir))

    def test_status_contains_model_count(self):
        status = self.mgr.get_status()
        self.assertIn('shared_models_count', status)
        self.assertEqual(status['shared_models_count'], 1)

    def test_status_contains_permissions(self):
        status = self.mgr.get_status()
        self.assertIn('dir_permissions', status)
        self.assertEqual(status['dir_permissions'], '0o700')

    def test_status_contains_total_size(self):
        status = self.mgr.get_status()
        self.assertIn('total_shared_size_mb', status)


class TestNoPrivateDataLeak(unittest.TestCase):
    """Security tests: ensure no private data leaks to the mesh."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_get_shared_models_no_paths(self):
        """get_shared_models should NOT include private file paths."""
        model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "leak-test" / "v1"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_bytes(b'\x00' * 512)
        self.mgr.share_model("leak-test:v1")

        models = self.mgr.get_shared_models()
        self.assertEqual(len(models), 1)

        # The returned dict should NOT contain the private path
        model = models[0]
        self.assertNotIn('source', model)
        self.assertNotIn('path', model)

        # Only safe fields should be present
        self.assertIn('name', model)
        self.assertIn('size_mb', model)
        self.assertIn('shared_since', model)
        self.assertIn('type', model)

    def test_status_no_private_keys(self):
        """Status should not leak private configuration."""
        status = self.mgr.get_status()
        # No private keys, secrets, or p2p_secret
        status_str = json.dumps(status)
        self.assertNotIn('p2p_secret', status_str)
        self.assertNotIn('private_key', status_str)
        self.assertNotIn('secret', status_str)

    def test_mesh_cannot_see_unshared(self):
        """The mesh should only see models in shared_models/, not private ones."""
        # Create a private model but don't share it
        model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "private-model" / "v1"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_bytes(b'\x00' * 512)

        # Only shared models should be visible
        models = self.mgr.get_shared_models()
        names = {m['name'] for m in models}
        self.assertNotIn("private-model:v1", names)
        self.assertNotIn("private-model", names)


class TestComputeChecksum(unittest.TestCase):
    """Test checksum computation."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.test_file = Path(self.base) / "test.bin"
        self.test_file.write_bytes(b'Hello, World! This is test data for checksum.')

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_compute_checksum_file(self):
        """Should compute SHA-256 of a file."""
        checksum = ModelShareManager._compute_checksum(self.test_file)
        self.assertIsNotNone(checksum)
        # Verify it's a valid hex string of correct length
        self.assertEqual(len(checksum), 64)  # SHA-256 = 64 hex chars
        # Verify it matches manual computation
        expected = hashlib.sha256(self.test_file.read_bytes()).hexdigest()
        self.assertEqual(checksum, expected)

    def test_compute_checksum_consistent(self):
        """Same file should always produce same checksum."""
        c1 = ModelShareManager._compute_checksum(self.test_file)
        c2 = ModelShareManager._compute_checksum(self.test_file)
        self.assertEqual(c1, c2)

    def test_compute_checksum_nonexistent(self):
        """Nonexistent file should return None."""
        result = ModelShareManager._compute_checksum(Path("/nonexistent/file"))
        self.assertIsNone(result)

    def test_compute_directory_checksum(self):
        """Should compute a combined checksum of all files in a directory."""
        test_dir = Path(self.base) / "test_dir"
        test_dir.mkdir()
        (test_dir / "file1.bin").write_bytes(b'content 1')
        (test_dir / "file2.bin").write_bytes(b'content 2')

        checksum = ModelShareManager._compute_directory_checksum(test_dir)
        self.assertIsNotNone(checksum)
        self.assertEqual(len(checksum), 64)

    def test_directory_checksum_deterministic(self):
        """Directory checksum should be deterministic (sorted files)."""
        test_dir = Path(self.base) / "test_dir2"
        test_dir.mkdir()
        (test_dir / "aaa.bin").write_bytes(b'content a')
        (test_dir / "zzz.bin").write_bytes(b'content z')

        c1 = ModelShareManager._compute_directory_checksum(test_dir)
        c2 = ModelShareManager._compute_directory_checksum(test_dir)
        self.assertEqual(c1, c2)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_initialize_idempotent(self):
        """Calling initialize() multiple times should be safe."""
        self.mgr.initialize()
        self.mgr.initialize()
        self.assertTrue(self.mgr.shared_dir.exists())

    def test_unshare_then_reshare(self):
        """Should be able to re-share a model after unsharing."""
        model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "reshare-test" / "v1"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_bytes(b'\x00' * 512)

        # Share
        self.assertTrue(self.mgr.share_model("reshare-test:v1"))
        self.assertTrue(self.mgr.is_shared("reshare-test:v1"))

        # Unshare
        self.assertTrue(self.mgr.unshare_model("reshare-test:v1"))
        self.assertFalse(self.mgr.is_shared("reshare-test:v1"))

        # Re-share
        self.assertTrue(self.mgr.share_model("reshare-test:v1"))
        self.assertTrue(self.mgr.is_shared("reshare-test:v1"))

    def test_multiple_models(self):
        """Should handle sharing multiple models."""
        for i in range(5):
            name = f"model-{i}"
            model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / name / "v1"
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / "weights.bin").write_bytes(b'\x00' * (1024 * (i + 1)))
            self.mgr.share_model(f"{name}:v1")

        models = self.mgr.get_shared_models()
        self.assertEqual(len(models), 5)

    def test_empty_shared_dir(self):
        """Should handle empty shared_models/ gracefully."""
        models = self.mgr.get_shared_models()
        self.assertEqual(len(models), 0)

    def test_model_name_with_many_colons(self):
        """Ollama allows multiple colons in model names."""
        # Single colon is valid (name:tag)
        self.assertEqual(self.mgr.validate_model_name("model:tag"), "model:tag")
        # But we don't support multiple colons
        # The regex only allows [a-zA-Z0-9._:-] so this is valid
        self.assertEqual(self.mgr.validate_model_name("a:b:c"), "a:b:c")


class TestDownloadFromMesh(unittest.TestCase):
    """Test download_from_mesh (placeholder functionality)."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.ollama = tempfile.mkdtemp()
        self.mgr = ModelShareManager(base_dir=self.base, ollama_dir=self.ollama)
        self.mgr.initialize()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.ollama, ignore_errors=True)

    def test_download_no_tracker(self):
        """Download without tracker should raise error."""
        with self.assertRaises(DownloadError):
            self.mgr.download_from_mesh("some-model")

    def test_download_invalid_name(self):
        """Download with invalid model name should raise error."""
        with self.assertRaises(InvalidModelNameError):
            self.mgr.download_from_mesh("../../../etc/passwd")

    def test_download_already_exists(self):
        """Download of an already-shared model should succeed (no-op)."""
        # Create a shared model
        model_dir = Path(self.ollama) / "manifests" / "registry.ollama.ai" / "library" / "existing" / "v1"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_bytes(b'\x00' * 512)
        self.mgr.share_model("existing:v1")

        # Trying to "download" an already shared model should return True
        result = self.mgr.download_from_mesh("existing:v1")
        self.assertTrue(result)


class TestComputeSize(unittest.TestCase):
    """Test size computation."""

    def setUp(self):
        self.base = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_file_size(self):
        """Should compute size of a file."""
        test_file = Path(self.base) / "test.bin"
        test_file.write_bytes(b'\x00' * (2 * 1024 * 1024))  # 2 MB
        size = ModelShareManager._compute_size(test_file)
        self.assertAlmostEqual(size, 2.0, places=1)

    def test_directory_size(self):
        """Should compute size of a directory."""
        test_dir = Path(self.base) / "test_dir"
        test_dir.mkdir()
        (test_dir / "file1.bin").write_bytes(b'\x00' * 1024 * 1024)  # 1 MB
        (test_dir / "file2.bin").write_bytes(b'\x00' * 1024 * 1024)  # 1 MB
        size = ModelShareManager._compute_size(test_dir)
        self.assertAlmostEqual(size, 2.0, places=1)

    def test_symlink_size(self):
        """Should follow symlinks and return target size."""
        target = Path(self.base) / "target.bin"
        target.write_bytes(b'\x00' * (3 * 1024 * 1024))  # 3 MB
        link = Path(self.base) / "link.bin"
        os.symlink(str(target), str(link))
        size = ModelShareManager._compute_size(link)
        self.assertAlmostEqual(size, 3.0, places=1)

    def test_nonexistent_size(self):
        """Nonexistent path should return 0."""
        size = ModelShareManager._compute_size(Path("/nonexistent/path"))
        self.assertEqual(size, 0.0)


if __name__ == '__main__':
    unittest.main()