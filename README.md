# TechCorp Customer Support Agent

An AI-powered customer support chatbot built with OpenAI, MCP (Model Context Protocol), and Streamlit. The agent can browse products, verify customers, look up orders, and place new orders — all through natural conversation backed by real tools.

## Architecture

```
User ↔ Streamlit UI ↔ Agent Loop (OpenAI) ↔ MCP Server (remote)
                                                  ↕
                                           Product catalog
                                           Customer database
                                           Order management
```

**Streamlit UI** (`app/streamlit_app.py`) — chat interface with MCP tool explorer, suggested questions, activity log, and streaming responses.

**Agent Loop** (`app/agent/chat.py`) — streams OpenAI completions, detects tool calls, executes them via MCP, and loops until a final text response.

**MCP Client** (`app/mcp_client.py`) — connects to a remote MCP server using `fastmcp`. The server exposes 8 tools for product/customer/order operations.

**Guardrails** (`app/agent/guardrails.py`) — pre-call auth checks, post-call state extraction, order confirmation enforcement, loop limits.

**FastAPI** (`app/api/`) — optional REST API with SSE streaming (not required for Streamlit mode).

## Features

- **Product browsing** — list, search, filter by category, get details
- **Customer verification** — email + PIN authentication
- **Order management** — view orders, order details, place new orders
- **Streaming responses** — tokens appear in real-time
- **MCP tool explorer** — sidebar shows all 8 tools with descriptions and parameters
- **Activity log** — tracks tool calls with timestamps and success/error status
- **Suggested questions** — context-aware prompts (different before/after auth)
- **Demo credentials** — sidebar shows test accounts for easy exploration
- **Guardrails** — auth enforcement, order confirmation, loop limits, result truncation

## Tech Stack

- **LLM**: OpenAI (`gpt-5-mini` default, configurable)
- **Tool Protocol**: MCP via `fastmcp`
- **Frontend**: Streamlit
- **API** (optional): FastAPI + Uvicorn
- **Config**: `pydantic-settings` (reads `.env` or env vars)
- **Testing**: pytest + pytest-asyncio

## Project Structure

```
├── app/
│   ├── streamlit_app.py      # Streamlit UI (main entry point)
│   ├── config.py              # Settings (env vars / .env)
│   ├── mcp_client.py          # MCP server connection + tool calls
│   ├── tools.py               # Tool classification + schema conversion
│   ├── agent/
│   │   ├── chat.py            # Core agent loop (streaming)
│   │   ├── state.py           # ConversationState dataclass
│   │   ├── prompts.py         # System prompt + guardrail context
│   │   └── guardrails.py      # Pre/post-call + loop guardrails
│   └── api/
│       ├── main.py            # FastAPI app
│       ├── routes.py          # /chat (SSE) + /health endpoints
│       └── models.py          # Request/response schemas
├── tests/                     # 46 tests
├── .streamlit/config.toml     # Streamlit theme
├── .env.example               # Environment template
├── requirements.txt           # Python dependencies
└── README.md
```

## Setup

### Prerequisites

- Python 3.10+
- OpenAI API key

### Install

```bash
git clone <repo-url>
cd genai
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `OPENAI_MODEL` | `gpt-5-mini` | Model to use |
| `MCP_SERVER_URL` | `https://vipfapwm3x.us-east-1.awsapprunner.com/mcp` | MCP server endpoint |

## Running

### Streamlit (recommended)

```bash
streamlit run app/streamlit_app.py
```

Opens at `http://localhost:8501`.

### FastAPI (optional REST API)

```bash
uvicorn app.api.main:app --reload
```

API docs at `http://localhost:8000/docs`.

## Streamlit Cloud Deployment

1. Push the repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo
4. Set **Main file path**: `app/streamlit_app.py`
5. Add secrets in the Streamlit Cloud dashboard:
   ```toml
   OPENAI_API_KEY = "sk-..."
   ```
6. Deploy

`pydantic-settings` reads environment variables automatically — Streamlit Cloud injects secrets as env vars.

## MCP Server

The remote MCP server at `https://vipfapwm3x.us-east-1.awsapprunner.com/mcp` provides 8 tools:

| Tool | Auth Required | Description |
|------|:---:|-------------|
| `list_products` | No | List products with optional category/active filters |
| `get_product` | No | Get product details by SKU |
| `search_products` | No | Search products by keyword |
| `verify_customer_pin` | No | Verify customer email + PIN |
| `get_customer` | Yes | Get customer profile |
| `list_orders` | Yes | List customer orders |
| `get_order` | Yes | Get order details |
| `create_order` | Yes | Place a new order |

### Demo Customers

| Name | Email | PIN |
|------|-------|-----|
| Donald Garcia | donaldgarcia@example.net | 7912 |
| Michelle James | michellejames@example.com | 1520 |
| Amanda Spencer | spenceamanda@example.org | 2535 |

## Testing

```bash
python -m pytest tests/ -v
```

All 46 tests cover:
- MCP client (connection, tool calls, error handling)
- Agent chat loop (streaming, tool execution, multi-turn)
- Guardrails (auth checks, order confirmation, loop limits)
- State management (reset, authentication)
- Prompt construction
- API endpoints (health, chat SSE)
