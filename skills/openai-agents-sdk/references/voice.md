# Voice Pipeline

## Installation
```bash
pip install "openai-agents[voice]"
```

## Architecture
Three-stage pipeline:
1. **STT**: Speech-to-text (transcription)
2. **Agent workflow**: Your agentic logic
3. **TTS**: Text-to-speech (synthesis)

## Quick Start

```python
import numpy as np
from agents import Agent, function_tool
from agents.voice import VoicePipeline, SingleAgentVoiceWorkflow, AudioInput

@function_tool
def get_weather(city: str) -> str:
    return f"Sunny in {city}"

agent = Agent(
    name="Voice Assistant",
    instructions="You are a helpful voice assistant.",
    model="gpt-5.2",
    tools=[get_weather],
)

pipeline = VoicePipeline(workflow=SingleAgentVoiceWorkflow(agent))

# From audio buffer (numpy array, 24kHz)
audio_input = AudioInput(buffer=np.zeros(24000, dtype=np.int16))
result = await pipeline.run(audio_input)

# Stream audio output
async for event in result.stream():
    if event.type == "voice_stream_event_audio":
        # Play event.data with sounddevice or similar
        pass
    elif event.type == "voice_stream_event_lifecycle":
        print(f"Lifecycle: {event.event}")  # turn_started / turn_ended
```

## Input Types

- `AudioInput`: Complete audio, no endpoint detection
- `StreamedAudioInput`: Streaming chunks with activity detection

## Pipeline Config

```python
from agents.voice import VoicePipelineConfig

config = VoicePipelineConfig(
    tracing_disabled=False,
    trace_include_sensitive_data=True,
    trace_include_sensitive_audio_data=False,
    workflow_name="my_voice_app",
    group_id="session_123",
    trace_metadata={"version": "1.0"},
)

pipeline = VoicePipeline(workflow=workflow, config=config)
```

## Multi-Agent Voice

```python
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

spanish = Agent(name="Spanish", instructions="Respond in Spanish", model="gpt-5.2")
english = Agent(
    name="English",
    instructions=prompt_with_handoff_instructions("Help in English. Hand off for Spanish."),
    model="gpt-5.2",
    handoffs=[spanish],
)

pipeline = VoicePipeline(workflow=SingleAgentVoiceWorkflow(english))
```

## Events

- `VoiceStreamEventAudio` — audio chunks to play
- `VoiceStreamEventLifecycle` — turn_started / turn_ended
- `VoiceStreamEventError` — error information

**Note:** No built-in interruption support for `StreamedAudioInput`. Use lifecycle events to manage microphone state.
