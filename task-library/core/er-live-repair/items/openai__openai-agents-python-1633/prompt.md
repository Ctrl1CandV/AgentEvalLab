## Issue (openai/openai-agents-python)

Configure realtime agents with Azure OpenAI's Realtime API
### Please read this first

- **Have you read the docs?**[Agents SDK docs](https://openai.github.io/openai-agents-python/)
- **Have you searched for related issues?** Others may have faced similar issue
- 
### Describe the bug

When using the OpenAI Agents SDK in Python with Azure OpenAI as the default model (via the async Azure client), the SDK ignores the Azure configuration and still requires OPENAI_API_KEY. As a result, real-time mode fails because the SDK always attempts to authenticate against OpenAI’s public API instead of using the Azure client credentials.

### Debug information
- Agents SDK version: 0.2.9
- Python 3.11

### Repro steps

Using the Realtime Quickstart Guide and setting the AsyncAzureOpenAI client via `set_default_openai_client`

```python
import asyncio
import logging

from agents import set_default_openai_client
from agents.realtime import RealtimeAgent, RealtimeRunner
from openai import AsyncAzureOpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    try:
        azure_openai_client = AsyncAzureOpenAI(
            api_key="****",
            api_version="2025-03-01-preview",
            azure_endpoint="https://***.openai.azure.com",
            # azure_deployment=azure_deployment, # somehow we don't need this anymore
        )
        set_default_openai_client(azure_openai_client)
        logger.info("✅ Azure OpenAI client configured successfully")
    except Exception as e:
        logger.error(f"❌ Failed to configure Azure OpenAI client: {e}")
        raise

    # Create the agent
    agent = RealtimeAgent(
        name="Assistant",
        instructions="You are a helpful voice assistant. Keep responses brief and conversational.",
    )

    # Set up the runner with configuration
    runner = RealtimeRunner(
        starting_agent=agent,
        config={
            "model_settings": {
                "model_name": "gpt-4o-mini-realtime-preview",
                "voice": "alloy",
                "modalities": ["text", "audio"],
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 200,
                },
            }
        },
    )

    # Start the session
    session = await runner.run(model_config={})

    async with session:
        print("Session started! The agent will stream audio responses in real-time.")

        # Process events
        async for event in session:
            if event.type == "response.audio_transcript.done":
                print(f"Assistant: {event.transcript}")
            elif event.type == "conversation.item.input_audio_transcription.completed":
                print(f"User: {event.transcript}")
            elif event.type == "error":
                print(f"Error: {event.error}")
                break


if __name__ == "__main__":
    asyncio.run(main())
```


### Expected behavior

If the default model is configured with the Azure client, the SDK should use the provided Azure credentials for real-time mode and shouldn't ask for `OPENAI_API_KEY`.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.

## Names the tests use

The project's tests for this issue use these names; give them exactly as listed:

- When the realtime model's connection config includes `headers`, exactly those headers are sent: they replace the defaults, so no `Authorization` or `OpenAI-Beta` header is added.
