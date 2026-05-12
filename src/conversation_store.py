#!/usr/bin/env python3
"""
💾 CONVERSATION STORE — PinkyBrain v5 Persistent Conversation Memory
====================================================================

Your conversations stay on YOUR machine. Period.

Features:
  1. Auto-save — Every message saved locally as you type
  2. Resume — Come back tomorrow, conversations are still there
  3. Search — Find conversations by keyword, date, model, or tag
  4. Export — Markdown, JSON, or plain text
  5. Privacy — Conversations NEVER leave your machine without consent
  6. Encryption — Optional local encryption with user-derived key
  7. Privacy levels — private / synced / shared / public

Security:
  - No data leaks to public mesh without explicit consent
  - "private" conversations are NEVER synced
  - Strict input validation (no injection in filenames)
  - 100MB max per conversation file
  - Path traversal protection
  - Sanitized exports (no executable code)
"""

import hashlib
import json
import logging
import os
import re
import shutil
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger('PinkyBrain.ConversationStore')

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_CONVERSATIONS_DIR = os.path.expanduser("~/.pinkybrain/conversations")
MAX_CONVERSATION_SIZE_BYTES = 100 * 1024 * 1024  # 100MB
MAX_FILENAME_LENGTH = 255
SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]+$')
MAX_MESSAGES_PER_CONVERSATION = 100_000
MAX_MESSAGE_CONTENT_LENGTH = 1_000_000  # 1MB per message content


class PrivacyLevel(Enum):
    """Privacy levels for conversations — default is ALWAYS private."""
    PRIVATE = "private"      # Stays local, never synced
    SYNCED = "synced"         # Synced via private P2P network only
    SHARED = "shared"         # Can be shared with specific peers
    PUBLIC = "public"         # Added to public mesh knowledge base (opt-in explicit)


class ExportFormat(Enum):
    """Supported export formats."""
    MARKDOWN = "markdown"
    JSON = "json"
    TEXT = "text"


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def _sanitize_filename(name: str) -> str:
    """
    Strict filename sanitization. Prevents path traversal and injection.

    REJECTS filenames containing dangerous characters (slashes, dots, backslashes).
    Only allows: alphanumeric, underscore, hyphen.
    Max 255 characters.
    Must be non-empty.
    """
    if not name or not name.strip():
        raise ValueError("Filename must not be empty")

    # Reject dangerous characters outright — no silent substitution
    dangerous_chars = set('/\\:.')
    for ch in dangerous_chars:
        if ch in name:
            raise ValueError(
                f"Invalid filename: '{name}'. "
                f"Contains dangerous character '{ch}'. "
                f"Only alphanumeric, underscore, and hyphen allowed."
            )

    # Must match the safe pattern exactly
    if not SAFE_FILENAME_PATTERN.match(name.strip()):
        raise ValueError(
            f"Invalid filename: '{name}'. "
            f"Only alphanumeric, underscore, and hyphen allowed."
        )

    sanitized = name.strip()

    if len(sanitized) > MAX_FILENAME_LENGTH:
        sanitized = sanitized[:MAX_FILENAME_LENGTH]

    return sanitized


def _validate_path_safety(base_dir: str, file_path: str) -> Path:
    """
    Validate that a file path resolves within the base directory.
    Prevents path traversal attacks (../../../etc/passwd).
    """
    base = Path(base_dir).resolve()
    target = Path(file_path).resolve()

    if not str(target).startswith(str(base)):
        raise ValueError(
            f"Path traversal detected: '{file_path}' resolves outside of '{base_dir}'"
        )

    return target


def _sanitize_export_content(content: str) -> str:
    """
    Sanitize content for export to prevent executable code injection.
    Removes script tags, event handlers, and other dangerous patterns.
    """
    # Remove <script> tags and their content
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
    # Remove event handlers (onclick, onload, etc.)
    content = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)
    # Remove javascript: URLs
    content = re.sub(r'javascript\s*:', '', content, flags=re.IGNORECASE)
    # Remove data: URLs with executable content
    content = re.sub(r'data\s*:\s*text/html[^"\']*', 'data:REDACTED', content, flags=re.IGNORECASE)
    return content


# ---------------------------------------------------------------------------
# Encryption (optional, local-only)
# ---------------------------------------------------------------------------

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    import base64 as _base64

    _ENCRYPTION_AVAILABLE = True
except ImportError:
    _ENCRYPTION_AVAILABLE = False
    logger.warning("cryptography package not available. Encryption disabled. "
                   "Install with: pip install cryptography")


def _derive_key(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """Derive a Fernet encryption key from a password using PBKDF2."""
    if not _ENCRYPTION_AVAILABLE:
        raise RuntimeError("Encryption requires the 'cryptography' package. "
                           "Install with: pip install cryptography")

    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,  # OWASP 2023 recommendation
        backend=default_backend()
    )
    key = _base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
    return key, salt


def _encrypt_data(data: bytes, password: str) -> bytes:
    """Encrypt data with a password-derived key. Returns salt + encrypted data."""
    key, salt = _derive_key(password)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data)
    return salt + encrypted  # Prepend salt for decryption


def _decrypt_data(data: bytes, password: str) -> bytes:
    """Decrypt data with a password-derived key. Expects salt prepended."""
    if len(data) < 16:
        raise ValueError("Encrypted data too short — missing salt")

    salt = data[:16]
    encrypted = data[16:]
    key, _ = _derive_key(password, salt)
    fernet = Fernet(key)
    return fernet.decrypt(encrypted)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class Message:
    """A single message in a conversation."""

    def __init__(
        self,
        role: str,
        content: str,
        model: Optional[str] = None,
        node: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid message role: '{role}'. Must be 'user', 'assistant', or 'system'.")

        if len(content) > MAX_MESSAGE_CONTENT_LENGTH:
            raise ValueError(
                f"Message content exceeds maximum length ({MAX_MESSAGE_CONTENT_LENGTH} chars). "
                f"Got {len(content)} chars."
            )

        self.role = role
        self.content = content
        self.model = model
        self.node = node
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.model:
            d["model"] = self.model
        if self.node:
            d["node"] = self.node
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif ts is None:
            ts = datetime.now(timezone.utc)
        return cls(
            role=data["role"],
            content=data["content"],
            model=data.get("model"),
            node=data.get("node"),
            timestamp=ts,
            metadata=data.get("metadata", {}),
        )


class Conversation:
    """A conversation with metadata and messages."""

    def __init__(
        self,
        conv_id: Optional[str] = None,
        title: Optional[str] = None,
        privacy: PrivacyLevel = PrivacyLevel.PRIVATE,
        created: Optional[datetime] = None,
        updated: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        now = datetime.now(timezone.utc)
        self.conv_id = conv_id or f"conv_{now.strftime('%Y-%m-%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.title = title or "Untitled"
        self.privacy = privacy
        self.created = created or now
        self.updated = updated or now
        self.messages: List[Message] = []
        self.metadata = metadata or {
            "model": None,
            "tokens_used": 0,
            "tags": [],
        }

    def add_message(self, message: Message) -> None:
        """Add a message and update conversation metadata."""
        if len(self.messages) >= MAX_MESSAGES_PER_CONVERSATION:
            raise ValueError(
                f"Conversation has reached maximum messages ({MAX_MESSAGES_PER_CONVERSATION})"
            )
        self.messages.append(message)
        self.updated = datetime.now(timezone.utc)

        # Track model from first assistant message
        if message.role == "assistant" and message.model and not self.metadata.get("model"):
            self.metadata["model"] = message.model

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conv_id": self.conv_id,
            "title": self.title,
            "privacy": self.privacy.value,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        created = data.get("created")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        elif created is None:
            created = datetime.now(timezone.utc)

        updated = data.get("updated")
        if isinstance(updated, str):
            updated = datetime.fromisoformat(updated)
        elif updated is None:
            updated = datetime.now(timezone.utc)

        privacy_str = data.get("privacy", "private")
        try:
            privacy = PrivacyLevel(privacy_str)
        except ValueError:
            logger.warning(f"Unknown privacy level '{privacy_str}', defaulting to PRIVATE")
            privacy = PrivacyLevel.PRIVATE

        conv = cls(
            conv_id=data.get("conv_id"),
            title=data.get("title", "Untitled"),
            privacy=privacy,
            created=created,
            updated=updated,
            metadata=data.get("metadata", {}),
        )

        for msg_data in data.get("messages", []):
            conv.messages.append(Message.from_dict(msg_data))

        return conv


# ---------------------------------------------------------------------------
# Conversation Store
# ---------------------------------------------------------------------------

class ConversationStore:
    """
    Persistent conversation storage.

    Stores conversations as JSON files in ~/.pinkybrain/conversations/.
    Each conversation = 1 JSON file with metadata + messages.

    Privacy levels:
      - private (default): stays local, NEVER synced
      - synced: sync via P2P private network only
      - shared: share with specific peers
      - public: added to public mesh (opt-in explicit)

    Security:
      - No path traversal
      - Filename validation
      - Size limits
      - Content sanitization on export
      - Encryption support (optional)
    """

    def __init__(
        self,
        conversations_dir: Optional[str] = None,
        encryption_password: Optional[str] = None,
    ):
        self.conversations_dir = conversations_dir or DEFAULT_CONVERSATIONS_DIR
        self._encryption_password = encryption_password
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create conversations directory if it doesn't exist."""
        os.makedirs(self.conversations_dir, exist_ok=True)

    def _conv_path(self, conv_id: str) -> Path:
        """Get the file path for a conversation, with safety checks."""
        # Sanitize the conv_id to prevent injection
        safe_id = _sanitize_filename(conv_id)
        file_path = os.path.join(self.conversations_dir, f"{safe_id}.json")
        validated = _validate_path_safety(self.conversations_dir, file_path)
        return validated

    def _check_size_limit(self, conv: Conversation) -> None:
        """Ensure conversation doesn't exceed size limit."""
        data = json.dumps(conv.to_dict()).encode('utf-8')
        if len(data) > MAX_CONVERSATION_SIZE_BYTES:
            size_mb = len(data) / (1024 * 1024)
            limit_mb = MAX_CONVERSATION_SIZE_BYTES / (1024 * 1024)
            raise ValueError(
                f"Conversation size ({size_mb:.1f}MB) exceeds limit ({limit_mb:.0f}MB). "
                f"Consider starting a new conversation."
            )

    # -------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------

    def create_conversation(
        self,
        title: Optional[str] = None,
        privacy: PrivacyLevel = PrivacyLevel.PRIVATE,
        tags: Optional[List[str]] = None,
        conv_id: Optional[str] = None,
    ) -> Conversation:
        """Create a new conversation and save it."""
        conv = Conversation(
            conv_id=conv_id,
            title=title or "Untitled",
            privacy=privacy,
        )
        if tags:
            conv.metadata["tags"] = tags
        self.save_conversation(conv)
        logger.info(f"Created conversation: {conv.conv_id} (privacy={privacy.value})")
        return conv

    def save_conversation(self, conv: Conversation) -> None:
        """Save a conversation to disk. Validates and persists."""
        self._check_size_limit(conv)
        data = json.dumps(conv.to_dict(), indent=2, ensure_ascii=False).encode('utf-8')

        file_path = self._conv_path(conv.conv_id)

        if self._encryption_password:
            data = _encrypt_data(data, self._encryption_password)

        # Atomic write: write to temp file, then rename
        temp_path = str(file_path) + ".tmp"
        with open(temp_path, 'wb') as f:
            f.write(data)
        os.replace(temp_path, str(file_path))

    def load_conversation(self, conv_id: str) -> Conversation:
        """Load a conversation from disk."""
        file_path = self._conv_path(conv_id)

        if not file_path.exists():
            raise FileNotFoundError(f"Conversation not found: {conv_id}")

        with open(file_path, 'rb') as f:
            data = f.read()

        if self._encryption_password:
            data = _decrypt_data(data, self._encryption_password)

        conv_dict = json.loads(data.decode('utf-8'))
        return Conversation.from_dict(conv_dict)

    def delete_conversation(self, conv_id: str) -> None:
        """Delete a conversation."""
        file_path = self._conv_path(conv_id)

        if not file_path.exists():
            raise FileNotFoundError(f"Conversation not found: {conv_id}")

        # Use trash-like approach: move to .trash/ instead of permanent delete
        trash_dir = os.path.join(self.conversations_dir, ".trash")
        os.makedirs(trash_dir, exist_ok=True)
        trash_path = os.path.join(trash_dir, file_path.name)
        # If already in trash, overwrite
        shutil.move(str(file_path), trash_path)
        logger.info(f"Moved conversation {conv_id} to trash")

    def list_conversations(
        self,
        privacy: Optional[PrivacyLevel] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List all conversations (metadata only, no messages).
        Returns list of {conv_id, title, privacy, created, updated, message_count, tags, model}.
        """
        results = []
        conv_dir = Path(self.conversations_dir)

        for file_path in sorted(conv_dir.glob("conv_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                if self._encryption_password:
                    conv = self._load_conversation_from_file(file_path)
                else:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        conv_dict = json.load(f)
                    conv = Conversation.from_dict(conv_dict)
            except Exception as e:
                logger.warning(f"Failed to load {file_path.name}: {e}")
                continue

            if privacy and conv.privacy != privacy:
                continue

            results.append({
                "conv_id": conv.conv_id,
                "title": conv.title,
                "privacy": conv.privacy.value,
                "created": conv.created.isoformat(),
                "updated": conv.updated.isoformat(),
                "message_count": len(conv.messages),
                "tags": conv.metadata.get("tags", []),
                "model": conv.metadata.get("model"),
            })

        # Apply offset and limit
        results = results[offset:]
        if limit:
            results = results[:limit]

        return results

    def _load_conversation_from_file(self, file_path: Path) -> Conversation:
        """Load a conversation from a specific file path."""
        with open(file_path, 'rb') as f:
            data = f.read()

        if self._encryption_password:
            data = _decrypt_data(data, self._encryption_password)

        conv_dict = json.loads(data.decode('utf-8'))
        return Conversation.from_dict(conv_dict)

    # -------------------------------------------------------------------
    # Auto-save / Message Operations
    # -------------------------------------------------------------------

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        node: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Conversation:
        """Add a message to a conversation and auto-save."""
        conv = self.load_conversation(conv_id)
        msg = Message(
            role=role,
            content=content,
            model=model,
            node=node,
            metadata=metadata,
        )
        conv.add_message(msg)
        self.save_conversation(conv)
        return conv

    def add_message_to_conversation(
        self,
        conv: Conversation,
        role: str,
        content: str,
        model: Optional[str] = None,
        node: Optional[str] = None,
    ) -> Conversation:
        """Add a message to an in-memory conversation (call save_conversation separately if needed)."""
        msg = Message(role=role, content=content, model=model, node=node)
        conv.add_message(msg)
        return conv

    # -------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------

    def search(
        self,
        query: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        model: Optional[str] = None,
        tags: Optional[List[str]] = None,
        privacy: Optional[PrivacyLevel] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search conversations by keyword, date, model, or tags.

        Returns matching conversations with matching message highlights.
        """
        results = []
        conv_dir = Path(self.conversations_dir)

        for file_path in sorted(conv_dir.glob("conv_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                conv = self._load_conversation_from_file(file_path)
            except Exception as e:
                logger.warning(f"Failed to load {file_path.name}: {e}")
                continue

            # Filter by privacy
            if privacy and conv.privacy != privacy:
                continue

            # Filter by date range
            if date_from and conv.created < date_from:
                continue
            if date_to and conv.created > date_to:
                continue

            # Filter by model
            if model and conv.metadata.get("model") != model:
                continue

            # Filter by tags (all tags must match)
            if tags:
                conv_tags = set(conv.metadata.get("tags", []))
                if not set(tags).issubset(conv_tags):
                    continue

            # Filter by keyword query
            match_messages = []
            if query:
                query_lower = query.lower()
                for msg in conv.messages:
                    if query_lower in msg.content.lower():
                        match_messages.append({
                            "role": msg.role,
                            "content": msg.content[:200],  # Truncate for preview
                            "timestamp": msg.timestamp.isoformat(),
                        })

                # Also check title
                if query_lower not in conv.title.lower() and not match_messages:
                    continue

            result = {
                "conv_id": conv.conv_id,
                "title": conv.title,
                "privacy": conv.privacy.value,
                "created": conv.created.isoformat(),
                "updated": conv.updated.isoformat(),
                "message_count": len(conv.messages),
                "tags": conv.metadata.get("tags", []),
                "model": conv.metadata.get("model"),
            }

            if match_messages:
                result["matches"] = match_messages

            results.append(result)

            if len(results) >= limit:
                break

        return results

    # -------------------------------------------------------------------
    # Tags
    # -------------------------------------------------------------------

    def add_tag(self, conv_id: str, tag: str) -> Conversation:
        """Add a tag to a conversation."""
        conv = self.load_conversation(conv_id)
        tags = conv.metadata.get("tags", [])
        if tag not in tags:
            tags.append(tag)
            conv.metadata["tags"] = tags
            self.save_conversation(conv)
        return conv

    def remove_tag(self, conv_id: str, tag: str) -> Conversation:
        """Remove a tag from a conversation."""
        conv = self.load_conversation(conv_id)
        tags = conv.metadata.get("tags", [])
        if tag in tags:
            tags.remove(tag)
            conv.metadata["tags"] = tags
            self.save_conversation(conv)
        return conv

    # -------------------------------------------------------------------
    # Privacy
    # -------------------------------------------------------------------

    def set_privacy(self, conv_id: str, privacy: PrivacyLevel) -> Conversation:
        """Change the privacy level of a conversation.

        IMPORTANT: Setting privacy to anything other than PRIVATE requires
        explicit user consent. The UI should confirm before upgrading privacy.
        """
        conv = self.load_conversation(conv_id)
        old_privacy = conv.privacy
        conv.privacy = privacy
        self.save_conversation(conv)
        logger.info(f"Privacy changed: {conv_id} {old_privacy.value} → {privacy.value}")
        return conv

    def get_syncable_conversations(self) -> List[Conversation]:
        """Get conversations that can be synced (synced, shared, or public). 
        PRIVATE conversations are NEVER returned here."""
        results = []
        conv_dir = Path(self.conversations_dir)

        for file_path in conv_dir.glob("conv_*.json"):
            try:
                conv = self._load_conversation_from_file(file_path)
            except Exception:
                continue

            if conv.privacy != PrivacyLevel.PRIVATE:
                results.append(conv)

        return results

    # -------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------

    def export_conversation(
        self,
        conv_id: str,
        fmt: ExportFormat = ExportFormat.MARKDOWN,
        output_dir: Optional[str] = None,
    ) -> str:
        """
        Export a single conversation to the specified format.
        Returns the path to the exported file.
        """
        conv = self.load_conversation(conv_id)
        return self._export_conv(conv, fmt, output_dir)

    def export_all(
        self,
        fmt: ExportFormat = ExportFormat.MARKDOWN,
        output_dir: Optional[str] = None,
        privacy: Optional[PrivacyLevel] = None,
    ) -> List[str]:
        """
        Export all conversations (optionally filtered by privacy).
        Returns list of exported file paths.
        """
        exported = []
        conv_dir = Path(self.conversations_dir)

        for file_path in conv_dir.glob("conv_*.json"):
            try:
                conv = self._load_conversation_from_file(file_path)
            except Exception:
                continue

            if privacy and conv.privacy != privacy:
                continue

            path = self._export_conv(conv, fmt, output_dir)
            exported.append(path)

        return exported

    def _export_conv(
        self,
        conv: Conversation,
        fmt: ExportFormat,
        output_dir: Optional[str] = None,
    ) -> str:
        """Export a single conversation. Returns file path."""
        if output_dir is None:
            output_dir = os.path.join(self.conversations_dir, "exports")
        os.makedirs(output_dir, exist_ok=True)

        safe_id = _sanitize_filename(conv.conv_id)
        ext = fmt.value if fmt == ExportFormat.JSON else fmt.value
        out_path = os.path.join(output_dir, f"{safe_id}.{ext}")

        if fmt == ExportFormat.MARKDOWN:
            content = self._to_markdown(conv)
        elif fmt == ExportFormat.JSON:
            content = self._to_export_json(conv)
        elif fmt == ExportFormat.TEXT:
            content = self._to_text(conv)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

        # Sanitize for safety
        content = _sanitize_export_content(content)

        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Exported {conv.conv_id} to {out_path}")
        return out_path

    def _to_markdown(self, conv: Conversation) -> str:
        """Convert conversation to Markdown format."""
        lines = [
            f"# {conv.title}",
            f"",
            f"**Conversation ID:** {conv.conv_id}  ",
            f"**Created:** {conv.created.isoformat()}  ",
            f"**Privacy:** {conv.privacy.value}  ",
            f"**Model:** {conv.metadata.get('model', 'N/A')}  ",
            f"**Tags:** {', '.join(conv.metadata.get('tags', [])) or 'None'}  ",
            f"",
            f"---",
            f"",
        ]

        for msg in conv.messages:
            role_label = {
                "user": "🧑 You",
                "assistant": "🤖 Assistant",
                "system": "⚙️ System",
            }.get(msg.role, msg.role)

            ts = msg.timestamp.strftime("%Y-%m-%d %H:%M UTC")
            model_info = f" ({msg.model})" if msg.model else ""

            lines.append(f"### {role_label}{model_info} — {ts}")
            lines.append(f"")
            lines.append(msg.content)
            lines.append(f"")
            lines.append(f"---")
            lines.append(f"")

        return "\n".join(lines)

    def _to_export_json(self, conv: Conversation) -> str:
        """Convert conversation to JSON export format."""
        return json.dumps(conv.to_dict(), indent=2, ensure_ascii=False)

    def _to_text(self, conv: Conversation) -> str:
        """Convert conversation to plain text format."""
        lines = [
            f"Conversation: {conv.title}",
            f"ID: {conv.conv_id}",
            f"Created: {conv.created.isoformat()}",
            f"Privacy: {conv.privacy.value}",
            f"",
        ]

        for msg in conv.messages:
            role = msg.role.upper()
            ts = msg.timestamp.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"[{ts}] {role}:")
            lines.append(msg.content)
            lines.append("")

        return "\n".join(lines)

    # -------------------------------------------------------------------
    # Resume / Latest
    # -------------------------------------------------------------------

    def get_latest_conversation(self) -> Optional[Conversation]:
        """Get the most recently updated conversation."""
        conv_dir = Path(self.conversations_dir)
        latest = None
        latest_time = 0

        for file_path in conv_dir.glob("conv_*.json"):
            mtime = file_path.stat().st_mtime
            if mtime > latest_time:
                latest_time = mtime
                latest = file_path

        if latest is None:
            return None

        return self._load_conversation_from_file(latest)

    def resume_conversation(self, conv_id: Optional[str] = None) -> Conversation:
        """
        Resume a conversation. If conv_id is provided, load that one.
        Otherwise, load the most recent conversation.
        If no conversations exist, create a new one.
        """
        if conv_id:
            return self.load_conversation(conv_id)

        latest = self.get_latest_conversation()
        if latest:
            return latest

        return self.create_conversation()

    # -------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored conversations."""
        conv_dir = Path(self.conversations_dir)
        total = 0
        total_messages = 0
        privacy_counts = {p.value: 0 for p in PrivacyLevel}
        models = {}
        total_size = 0

        for file_path in conv_dir.glob("conv_*.json"):
            try:
                conv = self._load_conversation_from_file(file_path)
                total += 1
                total_messages += len(conv.messages)
                privacy_counts[conv.privacy.value] += 1

                model = conv.metadata.get("model")
                if model:
                    models[model] = models.get(model, 0) + 1

                total_size += file_path.stat().st_size
            except Exception:
                continue

        return {
            "total_conversations": total,
            "total_messages": total_messages,
            "privacy_breakdown": privacy_counts,
            "models_used": models,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    # -------------------------------------------------------------------
    # Encryption
    # -------------------------------------------------------------------

    def enable_encryption(self, password: str) -> None:
        """Enable encryption for the store. Re-encrypts all existing conversations."""
        if not _ENCRYPTION_AVAILABLE:
            raise RuntimeError("Encryption requires the 'cryptography' package.")

        old_password = self._encryption_password
        self._encryption_password = password

        conv_dir = Path(self.conversations_dir)
        re_encrypted = 0

        for file_path in conv_dir.glob("conv_*.json"):
            try:
                # Load with old password (if any)
                with open(file_path, 'rb') as f:
                    data = f.read()

                if old_password:
                    data = _decrypt_data(data, old_password)

                conv_dict = json.loads(data.decode('utf-8'))
                conv = Conversation.from_dict(conv_dict)

                # Save with new encryption
                self.save_conversation(conv)
                re_encrypted += 1
            except Exception as e:
                logger.error(f"Failed to re-encrypt {file_path.name}: {e}")

        logger.info(f"Encryption enabled. Re-encrypted {re_encrypted} conversations.")

    def disable_encryption(self) -> None:
        """Disable encryption. Decrypts all conversations."""
        if not self._encryption_password:
            return

        password = self._encryption_password
        self._encryption_password = None

        conv_dir = Path(self.conversations_dir)

        for file_path in conv_dir.glob("conv_*.json"):
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()

                data = _decrypt_data(data, password)
                conv_dict = json.loads(data.decode('utf-8'))
                conv = Conversation.from_dict(conv_dict)

                # Save unencrypted
                self.save_conversation(conv)
            except Exception as e:
                logger.error(f"Failed to decrypt {file_path.name}: {e}")

        logger.info("Encryption disabled. All conversations decrypted.")

    # -------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------

    def empty_trash(self) -> int:
        """Permanently delete all conversations in trash. Returns count deleted."""
        trash_dir = os.path.join(self.conversations_dir, ".trash")
        if not os.path.exists(trash_dir):
            return 0

        count = 0
        for f in os.listdir(trash_dir):
            fp = os.path.join(trash_dir, f)
            if os.path.isfile(fp) and f.endswith('.json'):
                os.remove(fp)
                count += 1

        return count


# ---------------------------------------------------------------------------
# Convenience functions (for CLI usage)
# ---------------------------------------------------------------------------

_default_store: Optional[ConversationStore] = None


def get_store(encryption_password: Optional[str] = None) -> ConversationStore:
    """Get the default ConversationStore singleton."""
    global _default_store
    if _default_store is None:
        _default_store = ConversationStore(encryption_password=encryption_password)
    return _default_store


def quick_chat(
    message: str,
    conv_id: Optional[str] = None,
    model: Optional[str] = None,
    privacy: PrivacyLevel = PrivacyLevel.PRIVATE,
) -> Conversation:
    """
    Quick-start a chat. Creates or resumes a conversation and adds a user message.
    This is the simplest way to start — auto-saves immediately.
    """
    store = get_store()

    if conv_id:
        conv = store.load_conversation(conv_id)
    else:
        conv = store.resume_conversation()

    msg = Message(role="user", content=message)
    conv.add_message(msg)
    store.save_conversation(conv)
    return conv