# AI Sales & Customer Service Agent

An AI-powered sales and customer service assistant for an electronics e-commerce store, built with **Flask**, **PostgreSQL**, **LangGraph**, **RAG (ChromaDB)**, and **Groq LLM**.

> **Architecture:** Modular monolith using MVC + Service + Agent + RAG layers. Business logic is kept out of controllers, the LLM never touches the database directly, and transactional data is strictly separated from retrieval knowledge.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Design](#database-design)
- [LangGraph Agent](#langgraph-agent)
- [RAG Pipeline](#rag-pipeline)
- [API Reference](#api-reference)
- [Admin Dashboard](#admin-dashboard)
- [Environment Variables](#environment-variables)
- [Quick Start](#quick-start)
- [Docker](#docker)
- [Testing](#testing)
- [Example Conversations](#example-conversations)
- [Design Decisions](#design-decisions)
- [Limitations & Future Work](#limitations--future-work)

---

## Features

| Category | Capabilities |
|---|---|
| **AI Agent** | Intent classification · Multi-step routing · RAG retrieval · Tool execution · Grounded response generation · Multi-turn conversation · Pronoun resolution |
| **Sales** | Product search (exact + fuzzy) · Best-sellers by category · Price & stock lookup (live from PostgreSQL) · Order creation |
| **Customer Service** | Return / shipping / warranty / payment policies via RAG |
| **RAG** | PostgreSQL-backed knowledge store · Deterministic chunking · ChromaDB vector index · CRUD synchronization |
| **Admin Dashboard** | Product management · Order & customer views · Knowledge document CRUD with automatic RAG sync · Local-timezone timestamps |
| **Facebook Messenger** | Webhook integration for Messenger-based conversations |

---

## Architecture

```
              CUSTOMER / ADMIN
                     │
                     ▼
       ┌─────────────────────────┐
       │         VIEWS           │  Jinja2 + HTML/CSS/JS
       └────────────┬────────────┘
                    │
                    ▼
       ┌─────────────────────────┐
       │       CONTROLLERS       │  Flask Blueprints
       └────────────┬────────────┘
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
 ┌────────────────┐   ┌────────────────────┐
 │    SERVICES    │   │    AGENT LAYER     │
 │─────────────── │   │────────────────────│
 │ ProductService │   │ LangGraph Graph    │
 │ OrderService   │   │ Nodes & Routing    │
 │ KnowledgeSvc   │   │ Tools              │
 └───────┬────────┘   └────────┬───────────┘
         │                     │
         ▼              ┌──────┴──────┐
 ┌──────────────┐       ▼            ▼
 │    MODELS    │  ┌─────────┐  ┌─────────┐
 │ SQLAlchemy   │  │   RAG   │  │   LLM   │
 └──────┬───────┘  │ChromaDB │  │  Groq   │
        │          └─────────┘  └─────────┘
        ▼
 ┌──────────────┐
 │  PostgreSQL  │  ← Source of Truth
 └──────────────┘
```

### Agent Request Flow

```
Customer Message
  → Flask Controller
    → LangGraph Agent
        1. understand_request     (intent classification with labeled history)
        2. retrieve_context       (RAG, when relevant)
        3. agent_decision         (route to tool or direct response)
        4a. extract_product_request + resolve_product  (product intents — exact + fuzzy match)
        4b. extract_category      (recommendation intent — extracts optional category)
        5. prepare_tool_input
        6. execute_tool           (PostgreSQL-backed business operation)
        7. generate_response      (grounded LLM response with labeled conversation history)
  → Customer
```

### Layer Responsibilities

| Layer | Path | Responsibility |
|---|---|---|
| Model | `app/models/` | SQLAlchemy ORM entities & constraints |
| View | `app/views/` | Jinja2 templates, CSS, JS |
| Controller | `app/controllers/` | HTTP request/response only — no business logic |
| Service | `app/services/` | Business rules, validation, transactions |
| Agent | `app/agent/` | LangGraph orchestration, tools, prompts |
| RAG | `app/rag/` | Embeddings, chunking, ChromaDB, retrieval |

---

## Tech Stack

| Technology | Role |
|---|---|
| Python 3.11+ | Primary language |
| Flask 3 | Web framework |
| Flask-SQLAlchemy | ORM integration |
| PostgreSQL | Relational source of truth |
| LangGraph | Agent graph orchestration |
| LangChain / langchain-groq | LLM & tool integrations |
| Groq (`qwen/qwen3.8-27b`) | LLM provider |
| ChromaDB | Local vector database |
| Sentence Transformers (`all-MiniLM-L6-v2`) | Embedding model |
| rapidfuzz | Fuzzy product name matching (typo tolerance) |
| Pydantic | Structured output & validation |
| Jinja2 | Server-side HTML templates |
| pytest | Testing |
| Docker / Docker Compose | Containerisation |
| python-dotenv | Environment configuration |

---

## Project Structure

```
ai-sales-and-customer-service-agent/
│
├── app/
│   ├── __init__.py           # App factory
│   ├── config.py             # Config from environment
│   ├── extensions.py         # SQLAlchemy instance
│   │
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── customer.py
│   │   ├── product.py
│   │   ├── order.py
│   │   ├── order_item.py
│   │   └── knowledge.py
│   │
│   ├── views/
│   │   ├── templates/        # Jinja2 HTML templates
│   │   └── static/           # CSS & JS
│   │
│   ├── controllers/
│   │   ├── chat_controller.py
│   │   ├── admin_controller.py
│   │   └── facebook_controller.py
│   │
│   ├── services/
│   │   ├── product_service.py
│   │   ├── order_service.py
│   │   ├── knowledge_service.py  # Keeps PostgreSQL + ChromaDB in sync
│   │   ├── conversation_service.py
│   │   └── facebook_service.py
│   │
│   ├── agent/
│   │   ├── graph.py          # LangGraph graph definition
│   │   ├── nodes.py          # All node functions
│   │   ├── state.py          # AgentState TypedDict
│   │   ├── tools.py          # StructuredTool definitions
│   │   ├── prompts.py        # System & intent prompts
│   │   └── llm.py            # Groq LLM factory
│   │
│   └── rag/
│       ├── embeddings.py     # SentenceTransformer wrapper
│       ├── ingestion.py      # Chunking + embedding + indexing
│       ├── retriever.py      # Similarity retrieval
│       └── vectorstore.py    # ChromaDB client wrapper
│
├── tests/                    # pytest test suite
├── scripts/
│   └── seed.py               # Seed products, customers & knowledge docs
│
├── chroma_data/              # ChromaDB persistent storage
├── .env.example
├── requirements.txt
├── docker-compose.yml
├── run.py
└── README.md
```

---

## Database Design

### Entity Relationship

```
customers ──1──< orders ──1──< order_items >──1── products

knowledge_documents ──[ingestion]──> ChromaDB vector index
```

### Tables

#### `customers`
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `name` | String(120) | Required |
| `email` | String(255) | Required, Unique |
| `created_at` | DateTime(tz) | UTC |

#### `products`
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `name` | String(200) | Required |
| `description` | Text | Required |
| `price` | Numeric(10,2) | Required, ≥ 0 |
| `category` | String(100) | Required |
| `stock_quantity` | Integer | Required, ≥ 0 |
| `is_active` | Boolean | Default `True` |
| `created_at` / `updated_at` | DateTime(tz) | UTC |

#### `orders`
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `customer_id` | FK → customers | Required |
| `status` | String(20) | `pending` / `confirmed` / `cancelled` |
| `total_price` | Numeric(10,2) | Required |
| `created_at` / `updated_at` | DateTime(tz) | UTC |

#### `order_items`
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `order_id` | FK → orders | Required |
| `product_id` | FK → products | Required |
| `quantity` | Integer | Required |
| `unit_price` | Numeric(10,2) | Price snapshot at time of order |

> **`unit_price` is a price snapshot** — historical orders remain correct even if the product price changes later.

#### `knowledge_documents`
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `title` | String(255) | Required |
| `content` | Text | Required |
| `category` | String(50) | e.g. `policy`, `shipping`, `warranty`, `payment` |
| `source` | String(255) | Optional |
| `created_at` / `updated_at` | DateTime(tz) | UTC |

### Data Authority

| Source | Authoritative for |
|---|---|
| **PostgreSQL** | Current price, current stock, customers, orders, order status |
| **ChromaDB (RAG)** | Return policies, shipping info, warranty, payment methods, FAQs |

> **Conflict rule:** When RAG and PostgreSQL disagree on price or stock, **PostgreSQL always wins.** The LLM is instructed never to use stale vectorised prices.

---

## LangGraph Agent

### Graph Nodes

| Node | Purpose |
|---|---|
| `understand_request` | Classifies intent into one of 8 categories using labeled conversation history |
| `retrieve_context` | RAG retrieval (only for knowledge-based intents) |
| `agent_decision` | Decides which tool to call (or goes straight to response) |
| `extract_product_request` | Extracts product name & quantity using structured LLM output |
| `extract_category` | Extracts optional category keyword for best-seller queries (e.g. "headphones") |
| `resolve_product` | Two-stage match: exact SQL ILIKE → rapidfuzz fallback for typos/misspellings |
| `prepare_tool_input` | Builds validated tool input dict |
| `execute_tool` | Calls the selected StructuredTool |
| `generate_response` | Produces final grounded customer response |

### Supported Intents

```
product_search · product_question · recommendation
policy_question · availability_check · create_order
general_customer_service · unknown
```

### Agent State (`AgentState`)

```python
class AgentState(TypedDict, total=False):
    messages: list          # Conversation history (alternating customer/agent)
    intent: str             # Classified intent
    customer_id: int | None # Current customer

    retrieved_context: list # RAG results
    product_name: str | None
    category: str | None    # For best-seller / recommendation queries
    quantity: int | None
    product_id: int | None

    tool_name: str | None   # Selected tool
    tool_input: dict | None
    tool_result: dict | None

    response: str | None    # Final response
    error: str | None       # Controlled error state
```

### Tools

#### `get_product_details`
```json
// Input
{ "product_id": 1 }

// Output
{ "success": true, "product_name": "Samsung Galaxy S24",
  "price": "$699.99", "stock_quantity": 15, ... }
```

#### `check_product_availability`
```json
// Input
{ "product_id": 1, "quantity": 2 }

// Output
{ "success": true, "in_stock": true,
  "requested_quantity": 2, "available_quantity": 15 }
```

#### `create_order`
```json
// Input
{ "customer_id": 1, "product_id": 1, "quantity": 2 }

// Output (success)
{ "success": true, "order_id": 42, "status": "confirmed",
  "total_price": 1399.98, "remaining_stock": 13 }
```

`create_order` performs a full transactional sequence: validate customer → validate product → check stock → calculate total → create `Order` + `OrderItem` → decrement stock → `COMMIT`. A `ROLLBACK` is issued on any failure.

#### `get_best_sellers`
```json
// Input
{ "category": "headphones", "limit": 5 }   // category is optional

// Output
{ "success": true, "category_filter": "headphones",
  "products": [
    { "product_name": "Samsung Earbuds 4 Pro", "price": "$379.99",
      "stock_quantity": 10, "units_sold": 5 },
    ...
  ]
}
```

Returns active products ranked by total units sold (via `order_items`), optionally filtered by category. Used for `recommendation` intent queries like *"what are the best selling headphones?"*.

---

## RAG Pipeline

```
KnowledgeDocument (PostgreSQL)
  → Normalize / strip whitespace
  → Chunk (700 chars, 100 overlap)
  → Embed (SentenceTransformer)
  → Upsert → ChromaDB
        (chunk IDs: doc-{id}-chunk-{index})
```

### CRUD Synchronisation

| Operation | Flow |
|---|---|
| **Create** | INSERT PostgreSQL → chunk → embed → ChromaDB ADD |
| **Update** | New chunks upserted → obsolete old chunks deleted → PostgreSQL COMMIT |
| **Delete** | ChromaDB chunks deleted by metadata filter → PostgreSQL DELETE |

All knowledge CRUD goes through `KnowledgeService`, never direct ORM creation, ensuring PostgreSQL and ChromaDB stay in sync.

> If the vector store becomes inconsistent, run `python scripts/seed.py` (for fresh environments) or rebuild from the admin panel.

---

## API Reference

### Chat

| Method | Path | Description |
|---|---|---|
| `GET` | `/chat` | Chat UI |
| `POST` | `/api/chat` | Send a message |
| `GET` | `/health` | Health check |

**`POST /api/chat`**
```json
// Request
{
  "message": "What is your return policy?",
  "customer_id": 1,
  "conversation_id": "session-abc"
}

// Response
{
  "success": true,
  "conversation_id": "session-abc",
  "response": "Our return policy allows ...",
  "intent": "policy_question",
  "tool_result": null
}
```

### Admin

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/` | Dashboard overview |
| `GET` | `/admin/products` | List products |
| `POST` | `/admin/products/create` | Add product |
| `POST` | `/admin/products/<id>/edit` | Edit product |
| `POST` | `/admin/products/<id>/deactivate` | Deactivate product |
| `GET` | `/admin/orders` | List orders |
| `GET` | `/admin/customers` | List customers |
| `GET` | `/admin/knowledge` | List knowledge documents |
| `POST` | `/admin/knowledge/create` | Add document (syncs RAG) |
| `POST` | `/admin/knowledge/<id>/edit` | Update document (syncs RAG) |
| `POST` | `/admin/knowledge/<id>/delete` | Delete document (syncs RAG) |

### Facebook Messenger

| Method | Path | Description |
|---|---|---|
| `GET` | `/webhooks/facebook` | Webhook verification |
| `POST` | `/webhooks/facebook` | Receive Messenger events |

---

## Admin Dashboard

The Jinja2-based dashboard provides:

- **Overview** — total products, orders, customers, knowledge documents
- **Products** — list, create, edit, deactivate; shows live price and stock
- **Orders** — full order history with customer, status, total, and timestamps
- **Customers** — customer directory
- **Knowledge** — create / edit / delete knowledge documents; every mutation automatically syncs ChromaDB

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```env
# Flask
FLASK_SECRET_KEY=change-me

# PostgreSQL
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ai_sales_agent
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ai_sales_agent_test

# Groq LLM
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=qwen/qwen3.8-27b

# Embeddings & Vector Store
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHROMA_PATH=./chroma_data

# Admin UI timezone — any IANA string, e.g. Asia/Riyadh, Europe/Istanbul, America/New_York
# Defaults to UTC if not set.
DISPLAY_TIMEZONE=UTC

# Facebook Messenger (optional)
FACEBOOK_VERIFY_TOKEN=your_verify_token
FACEBOOK_PAGE_ACCESS_TOKEN=your_page_access_token
FACEBOOK_PAGE_ID=your_page_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_GRAPH_VERSION=v24.0
```

> ⚠️ Never commit `.env` — it is in `.gitignore`.

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (or Docker Desktop)
- Groq API key ([console.groq.com](https://console.groq.com))
- ngrok ([ngrok.com](https://ngrok.com)) — only needed for Facebook Messenger integration

### 1 — Clone

```bash
git clone <repository-url>
cd ai-sales-and-customer-service-agent
```

### 2 — Virtual Environment

```powershell
# Windows
python -m venv .venv
.venv\Scripts\Activate.ps1
```

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

### 4 — Configure Environment

```powershell
copy .env.example .env   # Windows
```
```bash
cp .env.example .env     # Linux / macOS
```

Edit `.env` — at minimum set `GROQ_API_KEY` and `DATABASE_URL`.

### 5 — Start PostgreSQL

```bash
docker compose up -d postgres
```

Or use a local PostgreSQL instance.

### 6 — Seed the Database

```bash
python -m scripts.seed
```

This creates:
- 4 demo products (Samsung Galaxy S24, iPhone 15, Google Pixel 8, MacBook Air M3)
- 1 demo customer
- 4 knowledge documents (Return Policy, Shipping Policy, Warranty Policy, Payment Methods) — ingested into both PostgreSQL **and** ChromaDB

### 7 — Run

```bash
python run.py
```

| URL | Description |
|---|---|
| `http://127.0.0.1:5000` | Redirects to `/chat` |
| `http://127.0.0.1:5000/chat` | Chat interface |
| `http://127.0.0.1:5000/admin/` | Admin dashboard |
| `http://127.0.0.1:5000/health` | Health check |

---

## Facebook Messenger Setup (optional)

The agent supports Facebook Messenger via a webhook. In development, use **ngrok** to expose your local Flask server to the internet.

### 1 — Start the App

```bash
python run.py
```

### 2 — Expose with ngrok

In a separate terminal:

```bash
ngrok http 5000
```

Copy the **Forwarding** URL, e.g. `https://a1b2-xx-xx-xx-xx.ngrok-free.app`.

### 3 — Configure `.env`

Add the Facebook credentials to your `.env`:

```env
FACEBOOK_VERIFY_TOKEN=ai_sales_agent_verify_2026
FACEBOOK_PAGE_ACCESS_TOKEN=<your-page-access-token>
FACEBOOK_PAGE_ID=<your-page-id>
FACEBOOK_APP_SECRET=<your-app-secret>
FACEBOOK_GRAPH_VERSION=v24.0
```

Restart the app after updating `.env`.

### 4 — Register the Webhook in Meta Developer Portal

1. Go to [developers.facebook.com](https://developers.facebook.com) → your App → **Messenger** → **Webhooks**.
2. Click **Add Callback URL** and enter:
   ```
   https://<your-ngrok-url>/webhooks/facebook
   ```
3. Enter your **Verify Token** (must match `FACEBOOK_VERIFY_TOKEN` in `.env`).
4. Click **Verify and Save** — the app responds to the `GET /webhooks/facebook` handshake automatically.
5. Under **Webhook Fields**, subscribe to **`messages`**.

### 5 — Subscribe the Page

In the **Messenger** settings, connect the webhook to your Facebook Page.

### 6 — Test

Send a message to your Facebook Page from Messenger. The agent will reply using the same LangGraph pipeline as the web chat.

> **Note:** ngrok URLs change on each restart unless you use a paid static domain. Update the callback URL in the Meta portal whenever the URL changes.

| Webhook Route | Method | Purpose |
|---|---|---|
| `/webhooks/facebook` | `GET` | Verify token handshake with Meta |
| `/webhooks/facebook` | `POST` | Receive and process Messenger messages |

---

## Docker

The `docker-compose.yml` provides a PostgreSQL service with a persistent volume.

```bash
# Start PostgreSQL
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down

# Stop and remove all data volumes
docker compose down -v
```

> ⚠️ `-v` removes the Docker volume and deletes all database data.

---

## Testing

The test suite requires `TEST_DATABASE_URL` to be set (see `.env.example`).

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# With coverage
pytest --cov=app
```

### Test Coverage

| Module | Tests |
|---|---|
| `test_product_service.py` | Product lookup, search, availability |
| `test_order_service.py` | Order creation, validation, stock decrement, rollback |
| `test_knowledge_service.py` | RAG create/update/delete and retrieval verification |
| `test_knowledge_consistency.py` | PostgreSQL rollback when vector ingestion fails |
| `test_tools.py` | All three agent tools via real DB |
| `test_agent_nodes.py` | `prepare_tool_input`, error guard on `generate_response` |
| `test_agent_routing.py` | Intent → tool routing, conditional edge functions |
| `test_agent_edge_cases.py` | Missing quantity, missing product, edge routing |
| `test_integration_order_flow.py` | End-to-end order flow with mocked LLM |
| `test_controllers.py` | Chat API endpoints |
| `test_admin_controller.py` | Admin page HTTP responses |
| `test_admin_crud.py` | Admin product & knowledge CRUD validation |

The full test suite **does not call external APIs** — the LLM is mocked in all agent tests.

---

## Example Conversations

### Policy Question (RAG)
```
User:  What is your return policy?
Agent: Our return policy allows you to return eligible products within
       30 days of purchase, provided they are in good condition with
       original packaging...
```
Flow: `policy_question` → RAG retrieval → grounded response

### Product Inquiry
```
User:  Tell me about the Samsung Galaxy S24.
Agent: The Samsung Galaxy S24 is priced at $699.99 and we currently
       have 15 units in stock. [description from DB]
```
Flow: `product_question` → `get_product_details` tool → PostgreSQL

### Availability Check
```
User:  Can I buy 3 Samsung Galaxy S24?
Agent: Yes, we have 15 Samsung Galaxy S24 units available, so
       3 units are in stock for you.
```
Flow: `availability_check` → `check_product_availability` tool → PostgreSQL

### Order Creation
```
User:  I want to buy 2 Samsung Galaxy S24.
Agent: Your order has been placed! Order #42 confirmed.
       2 × Samsung Galaxy S24 @ $699.99 = $1,399.98
```
Flow: `create_order` → `OrderService` → PostgreSQL transaction

### Insufficient Stock
```
User:  I want to buy 100 Samsung Galaxy S24.
Agent: I'm sorry, but only 15 units are currently available.
       Would you like to order a smaller quantity?
```
No order created. No stock modified. Clean controlled response.

### Best Sellers / Recommendation
```
User:  What are the best selling headphones?
Agent: Here are our top-selling headphones:
       1. Samsung Earbuds 4 Pro — $379.99 (5 sold)
       2. ...
```
Flow: `recommendation` → `extract_category` ("headphones") → `get_best_sellers` tool → PostgreSQL ranked by `order_items`

### Fuzzy Product Matching (Typo Tolerance)
```
User:  I am interested in samsng galaxy s24     ← typo
Agent: Great news! I found the Samsung Galaxy S24 for you...
```
Flow: `product_search` → exact ILIKE (no match) → rapidfuzz fallback (~85% score) → resolved to Samsung Galaxy S24

### Multi-Turn Context
```
User:  I'm interested in the Samsung Galaxy S24.
Agent: The Samsung Galaxy S24 is ...

User:  What's its price?           ← "its" resolved from labeled history
Agent: The Samsung Galaxy S24 is currently priced at $699.99.

User:  Do you have it now?         ← "it" resolved across turns
Agent: Yes, we currently have 15 units of the Samsung Galaxy S24 in stock.
```

---

## Design Decisions

### Why a Modular Monolith?
Simple to develop, test, and deploy locally without Kubernetes, Kafka, Redis, or microservices. Module boundaries are already clearly drawn, making a future split into services straightforward if needed.

### Why a Service Layer?
Order creation alone has 10+ steps (validate → calculate → create → decrement → commit). Embedding these rules in Flask controllers makes them impossible to reuse and difficult to test. `OrderService` is the single authoritative implementation.

### Why PostgreSQL as Source of Truth for Price/Stock?
A vector index is optimised for semantic similarity, not transactional consistency. Storing price in ChromaDB would create a stale-data problem whenever products are updated. PostgreSQL provides ACID guarantees; ChromaDB does not.

### Why LangGraph?
The agent is not a simple prompt → response loop. It has explicit decision nodes (route to RAG vs tool, resolve product, validate inputs) that benefit from a structured graph. LangGraph makes the workflow inspectable and testable at each node.

### Why Tools Instead of LLM-Generated SQL?
The LLM is probabilistic. Database mutations (stock decrement, order creation) require deterministic validation. Tools provide a typed, validated interface between the LLM's intent and the database transaction — the LLM cannot bypass stock checks or skip transaction rollback.

### Why ChromaDB?
Simple local vector database with persistent storage, no external service required. The RAG layer is isolated behind `ChromaVectorStore` and `KnowledgeRetriever` interfaces, making it straightforward to swap in a production vector store.

---

## Limitations & Future Work

### Current Limitations

| Area | Limitation |
|---|---|
| **Auth** | Admin dashboard has no authentication (intentional for scope) |
| **Conversation state** | In-memory only — lost on restart, not shared across processes |
| **Retrieval** | Basic cosine similarity only |
| **Facebook** | Webhook errors are logged but not retried |

### Future Improvements

**Authentication & Security**
- Admin login, RBAC, CSRF protection, HTTPS, rate limiting

**Retrieval Quality**
- Hybrid search (dense + sparse), reranking, query rewriting, HyDE, retrieval evaluation

**Conversation State**
- Persistent session store (Redis / PostgreSQL), authenticated sessions

**Observability**
- Structured logging, distributed tracing, agent execution tracing, LLM cost tracking

**AI Reliability**
- Prompt versioning, RAG evaluation datasets, hallucination monitoring, guardrails, model fallback

**Scalability**
- The modular boundaries already isolate services cleanly — individual components (agent, knowledge ingestion) can be extracted into separate services when traffic demands it.

---

## Production Checklist

Before deploying to production:

- [ ] Add admin authentication and RBAC
- [ ] Enable CSRF protection
- [ ] Move to a managed PostgreSQL instance with connection pooling
- [ ] Move conversation state to Redis or a persistent session store
- [ ] Replace ChromaDB with a managed vector database (e.g. Pinecone, Weaviate)
- [ ] Add structured logging and distributed tracing
- [ ] Configure LLM timeouts and retry/fallback policies
- [ ] Enable HTTPS and rate limiting
- [ ] Set up RAG evaluation to monitor retrieval quality
- [ ] Configure secret management (e.g. AWS Secrets Manager, Vault)
---

## WhatsApp Integration (WAHA)

The WhatsApp channel is an adapter around the existing `agent_graph`; it does not create a second agent.

### 1. Configure `.env`

Copy `.env.example` to `.env`, then set your existing database and Groq values plus:

```env
WAHA_BASE_URL=http://localhost:3000
WAHA_API_KEY=the_same_api_key_used_by_waha
WAHA_SESSION=default
WAHA_WEBHOOK_SECRET=
WAHA_DEFAULT_ENGINE=NOWEB
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=use_a_strong_password
WHATSAPP_SWAGGER_USERNAME=admin
WHATSAPP_SWAGGER_PASSWORD=use_another_strong_password
```

Use the same `WAHA_API_KEY` in the Flask app and the WAHA container. Do not commit `.env` or share its values.

### 2. Start PostgreSQL and WAHA

```bash
docker compose up -d postgres waha
docker compose ps
```

Open WAHA at `http://localhost:3000` and sign in with the dashboard credentials from `.env`. Create/start the `default` session and scan the QR code using WhatsApp → Linked devices.

### 3. Start Flask

In a second terminal, from the project root and with your Python virtual environment activated:

```bash
pip install -r requirements.txt
python scripts/seed.py
python run.py
```

The app should respond at `http://localhost:5000/health`. The dashboard/chat is at `http://localhost:5000/chat`.

### 4. Configure the WAHA webhook

In WAHA's dashboard/API settings, configure a webhook:

- URL: `http://host.docker.internal:5000/webhooks/whatsapp`
- Event: `message`
- Session: `default` (if the UI asks for a session filter)

`host.docker.internal` is important here: WAHA runs inside Docker while Flask runs directly on the Windows host. If Flask is also moved into the same Compose network, use `http://app:5000/webhooks/whatsapp` instead (where `app` is the Flask service name).

If you configure a custom webhook header, set `X-Webhook-Secret` to the same value as `WAHA_WEBHOOK_SECRET` in `.env`. Leave `WAHA_WEBHOOK_SECRET` empty for a local test if you do not configure that header.

### 5. Test from WhatsApp

Send a direct message to the linked WhatsApp account, for example:

- `Hello`
- `What is your return policy?`
- `Is Samsung Galaxy S24 available?`
- `I want to buy 2 Samsung Galaxy S24`

The webhook maps each WhatsApp chat to a customer record and invokes the existing LangGraph agent. Check the order in the Flask dashboard after the purchase test.

### Notes / current limitations

- Conversation history currently uses the project's in-memory `ConversationService`; it resets when Flask restarts and is not shared across multiple workers.
- This local integration handles direct chats only; group chats are ignored.
- The webhook endpoint should be exposed securely before any public/production deployment. Configure webhook authentication and HTTPS, and consider persistent message deduplication before production use.
- WAHA uses a WhatsApp Web-based integration. Review its operational and account risks before relying on it for a business-critical production channel.
