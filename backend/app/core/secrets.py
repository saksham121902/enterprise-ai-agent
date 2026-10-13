"""Secrets management abstraction layer.

Provides a unified interface for retrieving secrets from multiple backends:

- **Environment variables** (default) — suitable for development and containers
- **HashiCorp Vault** — enterprise-grade secret management
- **AWS Secrets Manager** — AWS-native secret storage
- **Azure Key Vault** — Azure-native secret storage

The active provider is determined by the ``SECRETS_PROVIDER`` environment
variable. Provider-specific dependencies (hvac, boto3, azure-*) are lazily
imported and only required when that provider is selected.

Usage::

    manager = get_secrets_manager()
    api_key = await manager.get_secret("OPENAI_API_KEY")
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SecretsProvider(ABC):
    """Abstract base class for secrets providers."""

    @abstractmethod
    async def get_secret(self, key: str) -> str | None:
        """Retrieve a secret value by key.

        Args:
            key: The secret key to look up.

        Returns:
            The secret value, or ``None`` if not found.
        """

    @abstractmethod
    async def set_secret(self, key: str, value: str) -> None:
        """Store a secret value.

        Args:
            key: The secret key.
            value: The secret value to store.
        """

    @abstractmethod
    async def delete_secret(self, key: str) -> None:
        """Delete a secret by key.

        Args:
            key: The secret key to remove.
        """

    async def get_secret_or_raise(self, key: str) -> str:
        """Retrieve a secret, raising ``ValueError`` if not found.

        Args:
            key: The secret key to look up.

        Returns:
            The secret value.

        Raises:
            ValueError: If the secret does not exist.
        """
        value = await self.get_secret(key)
        if value is None:
            msg = f"Required secret '{key}' not found in {type(self).__name__}"
            raise ValueError(msg)
        return value


class EnvironmentSecretsProvider(SecretsProvider):
    """Retrieve secrets from process environment variables.

    This is the default provider, suitable for local development
    and containerized environments where secrets are injected as env vars.
    """

    async def get_secret(self, key: str) -> str | None:
        """Get a secret from the current process environment."""
        return os.environ.get(key)

    async def set_secret(self, key: str, value: str) -> None:
        """Set an environment variable in the current process."""
        os.environ[key] = value
        logger.info("Secret set in environment", key=key)

    async def delete_secret(self, key: str) -> None:
        """Remove an environment variable from the current process."""
        os.environ.pop(key, None)
        logger.info("Secret removed from environment", key=key)


class VaultSecretsProvider(SecretsProvider):
    """Retrieve secrets from HashiCorp Vault KV v2 engine.

    Requires the ``hvac`` package: ``pip install enterprise-ai-agent[vault]``

    Args:
        url: Vault server URL (e.g., ``https://vault.example.com``).
        token: Vault authentication token.
        mount_point: KV secrets engine mount point (default: ``secret``).
    """

    def __init__(self, url: str, token: str, mount_point: str = "secret") -> None:
        self._url = url
        self._token = token
        self._mount_point = mount_point
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily initialize and authenticate the Vault client."""
        if self._client is None:
            try:
                import hvac  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "Vault support requires the 'hvac' package. "
                    "Install with: pip install enterprise-ai-agent[vault]"
                ) from exc

            self._client = hvac.Client(url=self._url, token=self._token)
            if not self._client.is_authenticated():
                raise ConnectionError("Vault authentication failed — check VAULT_TOKEN")
            logger.info("Vault client initialized", url=self._url)
        return self._client

    async def get_secret(self, key: str) -> str | None:
        """Read a secret from Vault KV v2."""
        try:
            client = self._get_client()
            response = client.secrets.kv.v2.read_secret_version(
                path=key,
                mount_point=self._mount_point,
            )
            data = response.get("data", {}).get("data", {})
            return data.get("value")
        except Exception:
            logger.warning("Failed to retrieve secret from Vault", key=key, exc_info=True)
            return None

    async def set_secret(self, key: str, value: str) -> None:
        """Write a secret to Vault KV v2."""
        client = self._get_client()
        client.secrets.kv.v2.create_or_update_secret(
            path=key,
            secret={"value": value},
            mount_point=self._mount_point,
        )
        logger.info("Secret stored in Vault", key=key)

    async def delete_secret(self, key: str) -> None:
        """Delete a secret and all its versions from Vault."""
        client = self._get_client()
        client.secrets.kv.v2.delete_metadata_and_all_versions(
            path=key,
            mount_point=self._mount_point,
        )
        logger.info("Secret deleted from Vault", key=key)


class AWSSecretsProvider(SecretsProvider):
    """Retrieve secrets from AWS Secrets Manager.

    Secrets are stored as a single JSON object in AWS. Individual keys
    are extracted from that JSON. Requires ``boto3``:
    ``pip install enterprise-ai-agent[aws]``

    Args:
        region: AWS region (e.g., ``us-east-1``).
        secret_name: The name of the AWS Secrets Manager secret.
    """

    def __init__(self, region: str, secret_name: str) -> None:
        self._region = region
        self._secret_name = secret_name
        self._client: Any = None
        self._cache: dict[str, str] = {}

    def _get_client(self) -> Any:
        """Lazily initialize the boto3 Secrets Manager client."""
        if self._client is None:
            try:
                import boto3  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "AWS support requires the 'boto3' package. "
                    "Install with: pip install enterprise-ai-agent[aws]"
                ) from exc

            self._client = boto3.client("secretsmanager", region_name=self._region)
            logger.info("AWS Secrets Manager client initialized", region=self._region)
        return self._client

    async def _load_secrets(self) -> dict[str, str]:
        """Load and cache the full secret JSON from AWS."""
        if not self._cache:
            client = self._get_client()
            response = client.get_secret_value(SecretId=self._secret_name)
            self._cache = json.loads(response["SecretString"])
        return self._cache

    async def get_secret(self, key: str) -> str | None:
        """Get a single key from the AWS secret JSON."""
        try:
            secrets = await self._load_secrets()
            return secrets.get(key)
        except Exception:
            logger.warning("Failed to retrieve secret from AWS", key=key, exc_info=True)
            return None

    async def set_secret(self, key: str, value: str) -> None:
        """Update a key in the AWS secret JSON."""
        client = self._get_client()
        secrets = await self._load_secrets()
        secrets[key] = value
        client.update_secret(
            SecretId=self._secret_name,
            SecretString=json.dumps(secrets),
        )
        self._cache = secrets
        logger.info("Secret stored in AWS Secrets Manager", key=key)

    async def delete_secret(self, key: str) -> None:
        """Remove a key from the AWS secret JSON."""
        secrets = await self._load_secrets()
        secrets.pop(key, None)
        client = self._get_client()
        client.update_secret(
            SecretId=self._secret_name,
            SecretString=json.dumps(secrets),
        )
        self._cache = secrets
        logger.info("Secret deleted from AWS Secrets Manager", key=key)


class AzureSecretsProvider(SecretsProvider):
    """Retrieve secrets from Azure Key Vault.

    Uses ``DefaultAzureCredential`` for authentication (supports managed
    identity, environment variables, Azure CLI, etc.). Requires:
    ``pip install enterprise-ai-agent[azure]``

    Args:
        vault_url: Azure Key Vault URL (e.g., ``https://myvault.vault.azure.net``).
    """

    def __init__(self, vault_url: str) -> None:
        self._vault_url = vault_url
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily initialize the Azure Key Vault SecretClient."""
        if self._client is None:
            try:
                from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
                from azure.keyvault.secrets import SecretClient  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "Azure support requires 'azure-identity' and 'azure-keyvault-secrets'. "
                    "Install with: pip install enterprise-ai-agent[azure]"
                ) from exc

            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=self._vault_url, credential=credential)
            logger.info("Azure Key Vault client initialized", vault_url=self._vault_url)
        return self._client

    async def get_secret(self, key: str) -> str | None:
        """Get a secret from Azure Key Vault.

        Azure Key Vault does not allow underscores in secret names,
        so underscores are automatically converted to hyphens.
        """
        try:
            client = self._get_client()
            azure_key = key.replace("_", "-").lower()
            secret = client.get_secret(azure_key)
            return secret.value
        except Exception:
            logger.warning("Failed to retrieve secret from Azure", key=key, exc_info=True)
            return None

    async def set_secret(self, key: str, value: str) -> None:
        """Store a secret in Azure Key Vault."""
        client = self._get_client()
        azure_key = key.replace("_", "-").lower()
        client.set_secret(azure_key, value)
        logger.info("Secret stored in Azure Key Vault", key=key)

    async def delete_secret(self, key: str) -> None:
        """Begin deletion of a secret from Azure Key Vault."""
        client = self._get_client()
        azure_key = key.replace("_", "-").lower()
        client.begin_delete_secret(azure_key)
        logger.info("Secret deletion initiated in Azure Key Vault", key=key)


def create_secrets_provider(
    provider: str = "env",
    vault_url: str = "",
    vault_token: str = "",
    vault_mount_point: str = "secret",
    aws_region: str = "",
    aws_secret_name: str = "",
    azure_vault_url: str = "",
) -> SecretsProvider:
    """Factory: create the appropriate secrets provider based on configuration.

    Args:
        provider: Provider name (``env``, ``vault``, ``aws``, ``azure``).
        vault_url: HashiCorp Vault URL.
        vault_token: HashiCorp Vault authentication token.
        vault_mount_point: Vault KV mount point.
        aws_region: AWS region for Secrets Manager.
        aws_secret_name: AWS Secrets Manager secret name.
        azure_vault_url: Azure Key Vault URL.

    Returns:
        An initialized ``SecretsProvider`` instance.

    Raises:
        ValueError: If the provider name is not recognized or required
            parameters are missing.
    """
    p = provider.lower()
    if p == "env":
        return EnvironmentSecretsProvider()
    elif p == "vault":
        if not vault_url or not vault_token:
            raise ValueError("Vault provider requires VAULT_URL and VAULT_TOKEN")
        return VaultSecretsProvider(vault_url, vault_token, vault_mount_point)
    elif p == "aws":
        if not aws_region or not aws_secret_name:
            raise ValueError("AWS provider requires AWS_REGION and AWS_SECRET_NAME")
        return AWSSecretsProvider(aws_region, aws_secret_name)
    elif p == "azure":
        if not azure_vault_url:
            raise ValueError("Azure provider requires AZURE_VAULT_URL")
        return AzureSecretsProvider(azure_vault_url)
    else:
        raise ValueError(
            f"Unknown secrets provider: '{provider}'. "
            "Valid options: env, vault, aws, azure"
        )


_secrets_manager: SecretsProvider | None = None


def get_secrets_manager() -> SecretsProvider:
    """Get or create the global secrets manager instance.

    The provider type is determined by the ``SECRETS_PROVIDER`` environment
    variable (defaults to ``env``).

    Returns:
        The global ``SecretsProvider`` singleton.
    """
    global _secrets_manager  # noqa: PLW0603
    if _secrets_manager is None:
        _secrets_manager = create_secrets_provider(
            provider=os.environ.get("SECRETS_PROVIDER", "env"),
            vault_url=os.environ.get("VAULT_URL", ""),
            vault_token=os.environ.get("VAULT_TOKEN", ""),
            vault_mount_point=os.environ.get("VAULT_MOUNT_POINT", "secret"),
            aws_region=os.environ.get("AWS_REGION", ""),
            aws_secret_name=os.environ.get("AWS_SECRET_NAME", ""),
            azure_vault_url=os.environ.get("AZURE_VAULT_URL", ""),
        )
    return _secrets_manager
