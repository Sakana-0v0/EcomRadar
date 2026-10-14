"""CredentialStore 单元测试.

AES-256 加密凭证存储:
- Fernet (AES-128-CBC + HMAC-SHA256) 加密
- master key 通过环境变量注入
- 加密后存入 Redis/Memory
- 验证: 不能明文泄露, round-trip 正确, 篡改检测
"""
import pytest
import os

from app.services.security.credential_store import (
    CredentialStore,
    InMemoryCredentialStore,
    EncryptedCredential,
)


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("ECOMRADAR_CREDENTIAL_KEY", "test-master-key-for-unit-tests-only")


class TestEncryptedCredential:
    def test_round_trip(self):
        cred = EncryptedCredential(
            tenant_id="t1",
            provider="notion",
            api_key="secret-key-123",
            extra={"team": "a"},
        )
        assert cred.tenant_id == "t1"
        assert cred.api_key == "secret-key-123"

    def test_to_dict_excludes_api_key(self):
        """序列化时排除敏感字段."""
        cred = EncryptedCredential(
            tenant_id="t1", provider="notion", api_key="secret"
        )
        d = cred.to_dict()
        assert "api_key" not in d
        assert d["tenant_id"] == "t1"


class TestInMemoryCredentialStore:
    @pytest.mark.asyncio
    async def test_save_and_load(self):
        store = InMemoryCredentialStore()
        await store.save(EncryptedCredential(
            tenant_id="t1", provider="notion", api_key="secret-key",
        ))
        loaded = await store.load("t1", "notion")
        assert loaded is not None
        assert loaded.api_key == "secret-key"

    @pytest.mark.asyncio
    async def test_storage_is_encrypted(self):
        """存储层不存明文."""
        store = InMemoryCredentialStore()
        await store.save(EncryptedCredential(
            tenant_id="t1", provider="notion", api_key="my-secret-key",
        ))
        raw = store._store["t1:notion"]
        assert "my-secret-key" not in raw.ciphertext
        assert raw.ciphertext != "my-secret-key"

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self):
        store = InMemoryCredentialStore()
        loaded = await store.load("nonexistent", "notion")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_overwrite(self):
        store = InMemoryCredentialStore()
        await store.save(EncryptedCredential(tenant_id="t1", provider="notion", api_key="v1"))
        await store.save(EncryptedCredential(tenant_id="t1", provider="notion", api_key="v2"))
        loaded = await store.load("t1", "notion")
        assert loaded.api_key == "v2"

    @pytest.mark.asyncio
    async def test_different_providers_isolated(self):
        store = InMemoryCredentialStore()
        await store.save(EncryptedCredential(tenant_id="t1", provider="notion", api_key="n-key"))
        await store.save(EncryptedCredential(tenant_id="t1", provider="feishu", api_key="f-key"))
        assert (await store.load("t1", "notion")).api_key == "n-key"
        assert (await store.load("t1", "feishu")).api_key == "f-key"

    @pytest.mark.asyncio
    async def test_delete(self):
        store = InMemoryCredentialStore()
        await store.save(EncryptedCredential(tenant_id="t1", provider="notion", api_key="k"))
        await store.delete("t1", "notion")
        assert await store.load("t1", "notion") is None

    @pytest.mark.asyncio
    async def test_tampering_detected(self):
        """加密数据被篡改,解密应失败."""
        store = InMemoryCredentialStore()
        await store.save(EncryptedCredential(tenant_id="t1", provider="notion", api_key="k"))
        raw = store._store["t1:notion"]
        raw.ciphertext = raw.ciphertext[:-5] + "AAAAA"
        with pytest.raises(Exception):
            await store.load("t1", "notion")

    def test_factory_returns_inmemory(self):
        store = CredentialStore.create(backend="memory")
        assert isinstance(store, InMemoryCredentialStore)

    def test_factory_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("ECOMRADAR_CREDENTIAL_KEY", raising=False)
        with pytest.raises(ValueError):
            CredentialStore.create(backend="memory")
