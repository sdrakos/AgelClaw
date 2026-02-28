# Sessions (Conversation Persistence)

## SQLiteSession (Quick Dev)

```python
from agents import Agent, Runner, SQLiteSession

agent = Agent(name="Assistant", instructions="Reply concisely.")
session = SQLiteSession("conversation_123")

r1 = await Runner.run(agent, "What city is the Golden Gate Bridge in?", session=session)
print(r1.final_output)  # "San Francisco"

r2 = await Runner.run(agent, "What state is it in?", session=session)  # has history
print(r2.final_output)  # "California"
```

## SQLAlchemySession (Production)

```bash
pip install "openai-agents[sqlalchemy]"
```

### From URL
```python
from agents.extensions.memory import SQLAlchemySession

session = SQLAlchemySession.from_url(
    "user-123",
    url="sqlite+aiosqlite:///:memory:",  # or postgresql+asyncpg://...
    create_tables=True,
)
```

### From Engine
```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
session = SQLAlchemySession("user-456", engine=engine, create_tables=True)
```

## AdvancedSQLiteSession (Branching + Analytics)

```bash
pip install openai-agents
```

```python
from agents.extensions.memory import AdvancedSQLiteSession

session = AdvancedSQLiteSession(
    session_id="conv_123",
    db_path="conversations.db",
    create_tables=True,
)

result = await Runner.run(agent, "Hello", session=session)
await session.store_run_usage(result)  # Track token usage
```

### Usage Tracking
```python
session_usage = await session.get_session_usage()
branch_usage = await session.get_session_usage(branch_id="main")
turn_usage = await session.get_turn_usage(user_turn_number=2)
```

### Conversation Branching
```python
turns = await session.get_conversation_turns()
branch_id = await session.create_branch_from_turn(2)  # Branch from turn 2
branches = await session.list_branches()
await session.switch_to_branch(branch_id)
await session.delete_branch(branch_id, force=True)
```

### Structured Queries
```python
conversation = await session.get_conversation_by_turns()
tool_usage = await session.get_tool_usage()
matching = await session.find_turns_by_content("weather")
```

## Manual History (No Session)

```python
result = await Runner.run(agent, "First message")
new_input = result.to_input_list() + [{"role": "user", "content": "Follow up"}]
result = await Runner.run(agent, new_input)
```
