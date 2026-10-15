"""Unit tests for LLM factory provider fallback and demo mode."""

import asyncio
import json
import unittest
from unittest.mock import patch

from app.llm.factory import LLMService


class TestLLMFactory(unittest.TestCase):
    """Test LLM service provider detection, fallback, and demo mode."""

    def setUp(self):
        self.service = LLMService(
            primary_provider="openai",
            fallback_providers=["google", "anthropic"],
        )

    def test_provider_configuration_detection(self):
        """Test _is_provider_configured accurately checks settings & environment."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("app.llm.factory.get_settings") as mock_settings,
        ):
                mock_settings.return_value.openai_api_key = ""
                mock_settings.return_value.anthropic_api_key = ""
                mock_settings.return_value.google_api_key = ""
                mock_settings.return_value.ollama_base_url = ""

                self.assertFalse(self.service._is_provider_configured("openai"))
                self.assertFalse(self.service._is_provider_configured("anthropic"))
                self.assertFalse(self.service._is_provider_configured("google"))

                mock_settings.return_value.openai_api_key = "sk-test-mock-key"
                self.assertTrue(self.service._is_provider_configured("openai"))

    def test_graceful_demo_response_when_no_keys(self):
        """When no provider keys are configured, generate() returns a structured demo response."""
        with patch.object(self.service, "_is_provider_configured", return_value=False):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(
                self.service.generate("Hello, who are you?")
            )
            loop.close()

            self.assertEqual(response.model, "demo-mode")
            self.assertEqual(response.provider, "enterprise-agent")
            self.assertIn("Enterprise AI Assistant", response.content)
            self.assertGreater(response.total_tokens, 0)

    def test_json_demo_response_for_supervisor(self):
        """When prompt asks for JSON, demo mode returns valid JSON with route_to direct."""
        with patch.object(self.service, "_is_provider_configured", return_value=False):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(
                self.service.generate(
                    prompt='Respond with a JSON object containing: "reasoning", "route_to", "direct_response"'
                )
            )
            loop.close()

            parsed = json.loads(response.content)
            self.assertEqual(parsed.get("route_to"), "direct")
            self.assertIn("direct_response", parsed)
            self.assertIn("Enterprise AI", parsed["direct_response"])


if __name__ == "__main__":
    unittest.main()
