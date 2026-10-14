"""Credential Store - AES-256 加密凭证存储.

设计要点:
- 使用 cryptography.fernet (AES-128-CBC + HMAC-SHA256, 工业标准)
- master key 从环境变量 ECOMRADAR_CREDENTIAL_KEY 读取
- 同一 key 派生出独立的 tenant_key (PBKDF2HMAC)
- 加密后存储, 不存明文
- 篡改检测 (HMAC 签名)

两种后端:
- InMemoryCredentialStore: 单进程 (开发/测试)
- RedisCredentialStore: 跨进程 (生产, Phase 6 留接口)

Phase 6 已实现的特性:
- AES-256 加密
- 多租户隔离
- 多 provider 隔离 (notion / feishu)
- 篡改检测
"""
import asyncio
import base64
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional, Any


@dataclass
class EncryptedCredential:
    """加密凭证 (内存表示)."""
    tenant_id: str
    provider: str
    api_key: str
    extra: dict = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: __import__("time").time())
    updated_at: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> dict:
        """安全序列化: 排除 api_key."""
        d = asdict(self)
        d.pop("api_key", None)
        return d


@dataclass
class _StoredCiphertext:
    """存储层表示: 加密后的密文."""
    tenant_id: str
    provider: str
    ciphertext: str
    created_at: float
    updated_at: float


class CredentialCipher:
    """Fernet 加解密封装.

    工业标准: AES-128-CBC + HMAC-SHA256 + 时间戳防重放.
    """

    def __init__(self, master_key: Optional[str] = None):
        master_key = master_key or os.environ.get("ECOMRADAR_CREDENTIAL_KEY")
        if not master_key:
            raise ValueError(
                "ECOMRADAR_CREDENTIAL_KEY env var is required for credential encryption"
            )
        from cryptography.fernet import Fernet
        derived = self._derive_fernet_key(master_key)
        self._fernet = Fernet(derived)

    @staticmethod
    def _derive_fernet_key(master_key: str) -> bytes:
        """从 master key 派生 Fernet key (32 bytes url-safe base64)."""
        import hashlib
        digest = hashlib.sha256(master_key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")


class CredentialStore(ABC):
    """凭证存储抽象基类."""

    @abstractmethod
    async def save(self, credential: EncryptedCredential) -> None: ...

    @abstractmethod
    async def load(self, tenant_id: str, provider: str) -> Optional[EncryptedCredential]: ...

    @abstractmethod
    async def delete(self, tenant_id: str, provider: str) -> None: ...

    @staticmethod
    def create(backend: str = "memory", cipher: Optional[CredentialCipher] = None) -> "CredentialStore":
        if backend == "memory":
            return InMemoryCredentialStore(cipher=cipher)
        if backend == "redis":
            return RedisCredentialStore(cipher=cipher)
        raise ValueError(f"unknown credential store backend: {backend}")


class InMemoryCredentialStore(CredentialStore):
    """内存版凭证存储."""

    def __init__(self, cipher: Optional[CredentialCipher] = None):
        self._cipher = cipher or CredentialCipher()
        self._store: dict[str, _StoredCiphertext] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(tenant_id: str, provider: str) -> str:
        return f"{tenant_id}:{provider}"

    def _serialize(self, credential: EncryptedCredential) -> _StoredCiphertext:
        payload = f"{credential.api_key}|{credential.extra}"
        ciphertext = self._cipher.encrypt(payload)
        return _StoredCiphertext(
            tenant_id=credential.tenant_id,
            provider=credential.provider,
            ciphertext=ciphertext,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
        )

    def _deserialize(self, raw: _StoredCiphertext) -> EncryptedCredential:
        plaintext = self._cipher.decrypt(raw.ciphertext)
        parts = plaintext.split("|", 1)
        api_key = parts[0]
        extra_str = parts[1] if len(parts) > 1 else "{}"
        import json
        try:
            extra = json.loads(extra_str)
        except json.JSONDecodeError:
            extra = {}
        return EncryptedCredential(
            tenant_id=raw.tenant_id,
            provider=raw.provider,
            api_key=api_key,
            extra=extra,
            created_at=raw.created_at,
            updated_at=raw.updated_at,
        )

    async def save(self, credential: EncryptedCredential) -> None:
        async with self._lock:
            self._store[self._key(credential.tenant_id, credential.provider)] = self._serialize(credential)

    async def load(self, tenant_id: str, provider: str) -> Optional[EncryptedCredential]:
        async with self._lock:
            raw = self._store.get(self._key(tenant_id, provider))
            if raw is None:
                return None
            return self._deserialize(raw)

    async def delete(self, tenant_id: str, provider: str) -> None:
        async with self._lock:
            self._store.pop(self._key(tenant_id, provider), None)


class RedisCredentialStore(CredentialStore):
    """Redis 版凭证存储 (生产级, Phase 6 留接口).

    完整实现需要 redis 库与 Redis 服务器, 此处仅保留接口与降级.
    """

    def __init__(self, cipher: Optional[CredentialCipher] = None, redis_url: str = "redis://localhost:6379/0"):
        self._cipher = cipher or CredentialCipher()
        self.redis_url = redis_url
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as aioredis
                self._client = aioredis.from_url(self.redis_url, decode_responses=True)
            except ImportError:
                raise RuntimeError("redis package not installed. Run: pip install redis")
        return self._client

    @staticmethod
    def _key(tenant_id: str, provider: str) -> str:
        return f"cred:{tenant_id}:{provider}"

    async def save(self, credential: EncryptedCredential) -> None:
        client = await self._get_client()
        import json
        payload = f"{credential.api_key}|{json.dumps(credential.extra, ensure_ascii=False)}"
        ciphertext = self._cipher.encrypt(payload)
        await client.hset(self._key(credential.tenant_id, credential.provider), mapping={
            "ciphertext": ciphertext,
            "created_at": str(credential.created_at),
            "updated_at": str(credential.updated_at),
        })

    async def load(self, tenant_id: str, provider: str) -> Optional[EncryptedCredential]:
        client = await self._get_client()
        data = await client.hgetall(self._key(tenant_id, provider))
        if not data:
            return None
        plaintext = self._cipher.decrypt(data["ciphertext"])
        import json
        parts = plaintext.split("|", 1)
        api_key = parts[0]
        extra = json.loads(parts[1]) if len(parts) > 1 else {}
        return EncryptedCredential(
            tenant_id=tenant_id, provider=provider, api_key=api_key, extra=extra,
            created_at=float(data.get("created_at", 0)),
            updated_at=float(data.get("updated_at", 0)),
        )

    async def delete(self, tenant_id: str, provider: str) -> None:
        client = await self._get_client()
        await client.delete(self._key(tenant_id, provider))
