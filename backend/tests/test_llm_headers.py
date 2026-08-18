import asyncio

from app.llm import LLMClient, LLMConfig, LLMError


def test_missing_api_key_does_not_create_invalid_authorization_header():
    client = LLMClient(LLMConfig({"provider": "deepseek", "api_key": ""}))
    try:
        assert "Authorization" not in client._http.headers
    finally:
        asyncio.run(client.close())


def test_missing_api_key_has_actionable_error():
    async def run():
        client = LLMClient(LLMConfig({"provider": "deepseek", "api_key": ""}))
        try:
            await client.chat([{"role": "user", "content": "test"}])
        except LLMError as error:
            assert "API Key" in str(error)
        else:
            raise AssertionError("missing API key should fail before making a request")
        finally:
            await client.close()

    asyncio.run(run())
