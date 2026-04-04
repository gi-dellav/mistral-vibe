from __future__ import annotations

import pytest

from glider.core.config import OtelExporterConfig, ProviderConfig, GliderConfig
from glider.core.types import Backend


class TestOtelExporterConfig:
    def test_derives_endpoint_from_mistral_provider(
        self, glider_config: GliderConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "sk-test")
        config = glider_config.model_copy(
            update={
                "providers": [
                    ProviderConfig(
                        name="mistral",
                        api_base="https://customer.mistral.ai/v1",
                        backend=Backend.MISTRAL,
                    )
                ]
            }
        )
        result = config.otel_exporter_config
        assert result is not None
        assert result.endpoint == "https://customer.mistral.ai/telemetry/v1/traces"
        assert result.headers == {"Authorization": "Bearer sk-test"}

    def test_uses_first_mistral_provider(
        self, glider_config: GliderConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EU_KEY", "sk-eu")
        config = glider_config.model_copy(
            update={
                "providers": [
                    ProviderConfig(
                        name="mistral-eu",
                        api_base="https://eu.mistral.ai/v1",
                        api_key_env_var="EU_KEY",
                        backend=Backend.MISTRAL,
                    ),
                    ProviderConfig(
                        name="mistral-us",
                        api_base="https://us.mistral.ai/v1",
                        api_key_env_var="US_KEY",
                        backend=Backend.MISTRAL,
                    ),
                ]
            }
        )
        result = config.otel_exporter_config
        assert result is not None
        assert result.endpoint == "https://eu.mistral.ai/telemetry/v1/traces"
        assert result.headers == {"Authorization": "Bearer sk-eu"}

    def test_falls_back_to_default_when_no_mistral_provider(
        self, glider_config: GliderConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "sk-fallback")
        config = glider_config.model_copy(
            update={
                "providers": [
                    ProviderConfig(
                        name="anthropic", api_base="https://api.anthropic.com/v1"
                    )
                ]
            }
        )
        result = config.otel_exporter_config
        assert result is not None
        assert result.endpoint == "https://api.mistral.ai/telemetry/v1/traces"
        assert result.headers == {"Authorization": "Bearer sk-fallback"}

    def test_default_providers(
        self, glider_config: GliderConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "sk-default")
        result = glider_config.otel_exporter_config
        assert result is not None
        assert result.endpoint == "https://api.mistral.ai/telemetry/v1/traces"

    def test_returns_none_and_warns_when_api_key_missing(
        self,
        glider_config: GliderConfig,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        with caplog.at_level("WARNING"):
            assert glider_config.otel_exporter_config is None
        assert "OTEL tracing enabled but MISTRAL_API_KEY is not set" in caplog.text

    def test_custom_api_key_env_var(
        self, glider_config: GliderConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        monkeypatch.setenv("MY_CUSTOM_KEY", "sk-custom")
        config = glider_config.model_copy(
            update={
                "providers": [
                    ProviderConfig(
                        name="mistral-onprem",
                        api_base="https://onprem.corp.com/v1",
                        api_key_env_var="MY_CUSTOM_KEY",
                        backend=Backend.MISTRAL,
                    )
                ]
            }
        )
        result = config.otel_exporter_config
        assert result is not None
        assert result.endpoint == "https://onprem.corp.com/telemetry/v1/traces"
        assert result.headers == {"Authorization": "Bearer sk-custom"}

    def test_explicit_otel_endpoint_bypasses_provider_derivation(
        self, glider_config: GliderConfig
    ) -> None:
        config = glider_config.model_copy(
            update={"otel_endpoint": "https://my-collector:4318/v1/traces"}
        )
        result = config.otel_exporter_config
        assert result is not None
        assert result == OtelExporterConfig(
            endpoint="https://my-collector:4318/v1/traces"
        )
        assert result.headers is None
