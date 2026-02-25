# Realtime Agents

Low-latency voice agents via WebSocket with the OpenAI Realtime API.

## Quick Start

```python
import asyncio
from agents import function_tool
from agents.realtime import RealtimeAgent, RealtimeRunner, RealtimeSession

@function_tool
def get_weather(city: str) -> str:
    return f"Sunny in {city}, 72F"

agent = RealtimeAgent(
    name="Greeter",
    instructions="You are a helpful voice assistant. Greet the user warmly.",
    tools=[get_weather],
)

runner = RealtimeRunner(
    model="gpt-realtime",
    # Voice: alloy, echo, fable, onyx, nova, shimmer
    voice="alloy",
    # Modalities: ["text", "audio"] or ["text"]
    modalities=["text", "audio"],
    # Audio format: pcm16, g711_ulaw, g711_alaw
    input_audio_format="pcm16",
    output_audio_format="pcm16",
    # Turn detection
    turn_detection={
        "type": "server_vad",  # or "semantic_vad"
        "threshold": 0.5,
        "silence_duration_ms": 500,
    },
    # Input transcription
    input_audio_transcription={"model": "gpt-4o-transcribe"},
)

async def main():
    async with runner.session(agent) as session:
        # Send text
        await session.send_text("Hello!")

        # Or send audio
        # await session.send_audio(audio_bytes)

        # Process events
        async for event in session:
            if event.type == "agent_start":
                print(f"Agent started: {event.agent.name}")
            elif event.type == "audio":
                # Play event.audio
                pass
            elif event.type == "transcript":
                print(f"Transcript: {event.text}")
            elif event.type == "tool_start":
                print(f"Tool: {event.tool_name}")
            elif event.type == "tool_end":
                print(f"Tool result: {event.output}")
            elif event.type == "handoff":
                print(f"Handoff to: {event.agent.name}")
            elif event.type == "error":
                print(f"Error: {event.error}")
            elif event.type == "agent_end":
                break

asyncio.run(main())
```

## Handoffs

```python
from agents.realtime import realtime_handoff

spanish = RealtimeAgent(name="Spanish", instructions="Respond in Spanish")
english = RealtimeAgent(
    name="English",
    instructions="Help in English. Hand off for Spanish.",
    handoffs=[realtime_handoff(spanish)],
)
```

## Guardrails (Output Only)

```python
from agents import output_guardrail, GuardrailFunctionOutput

@output_guardrail
async def check_output(ctx, agent, output):
    return GuardrailFunctionOutput(tripwire_triggered="harmful" in output)

agent = RealtimeAgent(
    name="Safe Agent",
    output_guardrails=[check_output],
)
```

Guardrails are debounced (default 100 chars) for real-time performance. They generate events, not exceptions.

## Authentication

```python
# Environment variable (default)
# export OPENAI_API_KEY=sk-...

# Direct API key
runner = RealtimeRunner(model="gpt-realtime", api_key="sk-...")

# Azure OpenAI
runner = RealtimeRunner(
    model="gpt-realtime",
    base_url="wss://my-resource.openai.azure.com/...",
    extra_headers={"api-key": "..."},
)
```

## SIP (Phone Calls)

```python
from agents.realtime import OpenAIRealtimeSIPModel

# Use SIP model for phone call integration via Realtime Calls API
```

## Key Differences from Voice Pipeline

| Feature | VoicePipeline | Realtime |
|---------|--------------|----------|
| Latency | Higher (3-stage) | Lower (native) |
| Connection | HTTP | WebSocket |
| Audio | Batch or stream | Real-time stream |
| Interruptions | Manual (lifecycle) | Server VAD |
| Guardrails | Input + Output | Output only |
