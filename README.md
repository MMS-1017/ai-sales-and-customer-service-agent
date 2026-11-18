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
- [Product Matching Pipeline](#product-matching-pipeline)
- [LangGraph Agent](#langgraph-agent)
- [RAG Pipeline](#rag-pipeline)
- [Media Processing (Vision & Audio)](#media-processing-vision--audio)
- [WhatsApp Integration (WAHA)](#whatsapp-integration-waha)
- [Web Chat Integration](#web-chat-integration)
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
| **Sales** | Deterministic 5-stage product matching · Product comparison · Best-sellers by category · Price & stock lookup (live from PostgreSQL) · Safe order creation with row locking (`with_for_update`) |
| **Multi-Modal AI** | Image understanding via Groq Vision (`meta-llama/llama-4-scout-17b-16e-instruct`) · Audio transcription via Groq Whisper (`whisper-large-v3-turbo`) |
| **WhatsApp (WAHA)** | Inbound webhook processing · Webhook secret verification · Thread-safe LRU message deduplication · Graceful non-blocking media fallback |
| **Web Chat** | Modern real-time UI · Multipart media uploads (images + voice audio) · File format & size validation with user-friendly errors |
| **Customer Service** | Return / shipping / warranty / payment policies via RAG |
| **RAG** | PostgreSQL-backed knowledge store · Deterministic chunking · ChromaDB vector index · CRUD synchronization |
| **Admin Dashboard** | Product management · Order & customer views · Knowledge document CRUD with automatic RAG sync · Local-timezone timestamps |

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
Customer Message (Text, Image, or Audio)
  → Flask Controller (Web Chat or WhatsApp Webhook with LRU Deduplication)
    → MediaService (Groq Vision / Whisper transcription if media present)
      → LangGraph Agent
          1. understand_request            (intent classification with labeled history)
          2. retrieve_context              (RAG, when relevant)
          3. agent_decision                (route to tool, comparison, or direct response)
          4a. extract_product_request + resolve_product (5-stage deterministic matching)
          4b. extract_category             (recommendation intent — category extraction)
          4c. extract_comparison_products + fetch_comparison_products (product comparison)
          5. prepare_tool_input            (validates parameters & customer ID)
          6. execute_tool                  (PostgreSQL-backed business operation with row locking)
          7. generate_response             (grounded LLM response with labeled conversation history)
  → Customer (Web Chat / WhatsApp API)
```

### Layer Responsibilities

| Layer | Path | Responsibility |
|---|---|---|
| Model | `app/models/` | SQLAlchemy ORM entities, relationships & constraints |
| View | `app/views/` | Jinja2 templates, modern chat UI, static CSS & JS |
| Controller | `app/controllers/` | HTTP request/response, validation, webhook deduplication |
| Service | `app/services/` | Business rules, 5-stage product matching, transactions, media processing |
| Agent | `app/agent/` | LangGraph workflow, state, nodes, routing, tools, prompts |
| RAG | `app/rag/` | Embeddings, deterministic chunking, ChromaDB, similarity retrieval |

---

## Tech Stack

| Technology | Role |
|---|---|
| Python 3.11+ | Primary language |
| Flask 3 | Web application framework |
| Flask-SQLAlchemy | ORM integration with PostgreSQL |
| PostgreSQL | Relational database & authoritative source of truth |
| LangGraph | Agent state-graph orchestration |
| LangChain / langchain-groq | LLM & tool calling orchestration |
| Groq LLM (`qwen/qwen3.8-27b`) | Conversational reasoning & structured output |
| Groq Vision (`meta-llama/llama-4-scout-17b-16e-instruct`) | Product image understanding |
| Groq Whisper (`whisper-large-v3-turbo`) | Voice note speech-to-text transcription |
| WAHA (WhatsApp HTTP API) | Headless WhatsApp integration |
| ChromaDB | Persistent local vector database |
| Sentence Transformers (`all-MiniLM-L6-v2`) | Document embedding model (lazy-loaded) |
| rapidfuzz | Fuzzy string matching & token similarity |
| Pydantic | Structured LLM extraction schemas |
| Jinja2 | Server-side web templates |
| pytest | Automated test suite (85 tests) |
| Docker / Docker Compose | Multi-container environment (PostgreSQL + WAHA) |
| python-dotenv | Environment variable configuration |

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

## Product Matching Pipeline

The system features a **deterministic, 5-stage product matching pipeline** in `ProductService.match_product`, completely isolated from non-deterministic LLM hallucinations.

### The Confirmed Anker R50i Bug & Root Cause

**The Bug:**
When a customer asked for `anker r50i`, the system logged:
```text
PRODUCT NAME: anker r50i
QUANTITY: None

MATCHED PRODUCTS (exact):
[(11, 'anker r50i'), (14, 'anker r50i NC')]
```
The agent incorrectly claimed both products matched, treated it as ambiguous, and asked the customer to clarify instead of directly selecting the exact product.

**The Root Cause:**
1. Substring Matching in SQL: The legacy search executed `Product.name.ilike(f"%{query}%")`. Because `"anker r50i"` is a substring of `"anker r50i NC"`, the query matched both rows in PostgreSQL.
2. Premature Ambiguity: Because the list length was `> 1`, the code immediately aborted to an ambiguity error without checking whether one candidate had an **exact full-name equality**.
3. Lack of Suffix & Modifier Discrimination: Model modifiers (like `"NC"`, `"Pro"`, `"Ultra"`) and accessory terms (like `"case"`, `"charger"`) were not distinguished from base product names.

### The 5-Stage Matching Pipeline

```
Raw Customer Query
  │
  ▼
[ Stage 1: Normalization ]
  • Lowercase & trim whitespace
  • Collapse multiple spaces
  • Strip punctuation (preserve alphanumeric model numbers)
  • Compute compact key (e.g. "anker-r50i" → "ankerr50i")
  │
  ▼
[ Stage 2: Exact Matching ]
  • Exact normalized string equality (norm_name == norm_query)
  • Exact compact key equality (compact_key(name) == comp_query)
  • If EXACTLY ONE match: Return immediately (Confidence: 1.0)
  • Longer supersets (e.g. "anker r50i NC") are strictly excluded
  │
  ▼ (if no exact match)
[ Stage 3: Alias Matching ]
  • Check aliases and model numbers
  • Exact alias match returns immediately
  │
  ▼ (if no alias match)
[ Stage 4: Partial & Relevance Matching with Context & Accessory Protection ]
  • Accessory Guard: Explicit accessory terms (e.g. "case", "charger") disqualify non-accessory base products
  • Variant Guard: Explicit variant modifiers (e.g. "Pro", "Ultra", "NC") disqualify products lacking that variant
  • Multi-Level Token Matching: Non-filler query tokens match across product name, category synonyms (e.g. "phone", "earbuds", "laptop"), and description brand attributes (e.g. "Apple" in "Apple iPhone 15")
  • Variant Discrimination: Penalizes unrequested variants (e.g. "NC") when the base model is covered, while preserving ambiguity for broad queries (e.g. "anker")
  • Score ranking with coverage, length ratio, and prefix weighting
  │
  ▼
[ Stage 5: Ambiguity Handling ]
  • Single top candidate or dominant leader (score ≥ 80, margin ≥ 12): Return candidate
  • Multiple genuinely close candidates: Return formatted clarification options
  • No candidates: Return clean "Product not found" response
```

### Verified Test Matrix

| Query | Expected Result | Actual Result | Verification |
|---|---|---|---|
| `anker r50i` | Product ID 11 only | Product ID 11 (`match_type: exact`) | ✅ `tests/test_product_matching.py` |
| `anker r50i NC` | Product ID 14 only | Product ID 14 (`match_type: exact`) | ✅ `tests/test_product_matching.py` |
| `anker` | Ambiguity (IDs 11 & 14) | Clarification listing both candidates | ✅ `tests/test_product_matching.py` |
| `anker r50i case` | Not found (no false earbuds match) | `success: False`, not-found error | ✅ `tests/test_product_matching.py` |
| `Apple iPhone 15` | Product ID 30 (iPhone 15) | Product ID 30 (`match_type: partial`) | ✅ `tests/test_product_matching.py` |
| `anker r50i earbuds` | Product ID 11 | Product ID 11 (`match_type: partial`) | ✅ `tests/test_product_matching.py` |
| `Samsung S24 Ultra phone` | Product ID 20 (S24 Ultra) | Product ID 20 (`match_type: partial`) | ✅ `tests/test_product_matching.py` |
| `soundcore r50i` | Product ID 11 (via alias) | Product ID 11 (`match_type: alias`) | ✅ `tests/test_product_matching.py` |
| `anker r50i Pro` | Not found (variant mismatch) | `success: False`, not-found error | ✅ `tests/test_product_matching.py` |
| `ANKER R50I` | Product ID 11 | Product ID 11 (casing insensitive) | ✅ `tests/test_product_matching.py` |
| `  anker   r50i  ` | Product ID 11 | Product ID 11 (whitespace normalized) | ✅ `tests/test_product_matching.py` |
| `anker r-50i` | Product ID 11 | Product ID 11 (compact key tolerance) | ✅ `tests/test_product_matching.py` |
| `nonexistent item` | Not found error | Clean "Product not found" response | ✅ `tests/test_product_matching.py` |

---

## LangGraph Agent

### Graph Nodes

| Node | Purpose |
|---|---|
| `understand_request` | Classifies intent into one of 9 categories using labeled conversation history |
| `retrieve_context` | RAG retrieval from ChromaDB (for policy/knowledge-based intents) |
| `agent_decision` | Routes to tool execution, product comparison, or direct LLM response |
| `extract_product_request` | Extracts product name & quantity using structured LLM output |
| `extract_category` | Extracts optional category keyword for best-seller queries |
| `extract_comparison_products` | Extracts multiple product names from query for side-by-side comparison |
| `fetch_comparison_products` | Fetches specifications for multiple products deterministically using `match_product` |
| `resolve_product` | 5-stage deterministic matching pipeline (exact → alias → partial → ambiguity) |
| `prepare_tool_input` | Validates parameters (including customer ID) before database operations |
| `execute_tool` | Calls the selected StructuredTool (ACID transaction with row locking) |
| `generate_response` | Produces final grounded customer response |

### Supported Intents

```
product_search · product_question · recommendation · compare_products
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

## Media Processing (Vision & Audio)

The system supports multi-modal user interactions across Web Chat and WhatsApp using Groq's dedicated multi-modal models:

- **Image Understanding:** Powered by `meta-llama/llama-4-scout-17b-16e-instruct` via Groq's Vision API. When a user uploads a product photo, the model identifies the device brand, model, color, and visible condition, allowing the agent to resolve product queries directly from images.
- **Audio / Voice Note Transcription:** Powered by `whisper-large-v3-turbo` via Groq's Speech-to-Text API. Voice notes recorded in Web Chat or sent over WhatsApp are automatically transcribed into normalized text and fed seamlessly into the agent workflow.

### Media Configuration & Safeguards

```env
GROQ_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
GROQ_STT_MODEL=whisper-large-v3-turbo
MEDIA_MAX_IMAGE_MB=10
MEDIA_MAX_AUDIO_MB=25
```

- **Strict MIME Type Validation:** Only safe, recognized image formats (`image/jpeg`, `image/png`, `image/webp`) and audio formats (`audio/mpeg`, `audio/wav`, `audio/ogg`, `audio/mp4`, `audio/x-m4a`) are accepted.
- **Size Limit Enforcement:** Requests exceeding `MEDIA_MAX_IMAGE_MB` or `MEDIA_MAX_AUDIO_MB` are rejected with HTTP 400 Bad Request before file processing.
- **Fault-Tolerant Media Processing:** If external API transcription or vision fails (e.g. rate limits or temporary provider downtime), the media failure is logged, user text is preserved, and the request completes without throwing an unhandled 500 error.

---

## Web Chat Integration

The Web Chat UI (`/chat`) provides an interactive interface supporting:

- **Real-Time Text Chat:** Conversational history maintained per session.
- **Image File Uploads:** Drag-and-drop or file picker with instant preview.
- **Voice Message Recording:** In-browser audio recording via MediaRecorder API with audio waveform playback.
- **Multipart Form Handling:** Seamless submission of text + optional media via `POST /api/chat`.
- **Client & Server Validation:** Both frontend and backend reject invalid file formats and oversized files with clear, actionable user messages.

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

# Groq LLM & Multi-Modal Models
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=qwen/qwen3.8-27b
GROQ_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
GROQ_STT_MODEL=whisper-large-v3-turbo

# Upload Size Limits
MEDIA_MAX_IMAGE_MB=10
MEDIA_MAX_AUDIO_MB=25

# Embeddings & Vector Store
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHROMA_PATH=./chroma_data

# Admin UI timezone (e.g. Asia/Riyadh, Europe/Istanbul, America/New_York)
DISPLAY_TIMEZONE=UTC

# WhatsApp / WAHA Integration
WAHA_BASE_URL=http://localhost:3000
WAHA_API_KEY=your_waha_api_key
WAHA_SESSION=default
WAHA_WEBHOOK_SECRET=change_this_to_a_long_random_secret
WHATSAPP_DEFAULT_ENGINE=NOWEB
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=change_this_dashboard_password
WHATSAPP_SWAGGER_USERNAME=admin
WHATSAPP_SWAGGER_PASSWORD=change_this_swagger_password

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

The automated test suite contains **90 tests across 16 test modules**, executing in isolated PostgreSQL test transactions with mocked external APIs:

| Module | Tests | Focus Areas |
|---|:---:|---|
| `test_product_matching.py` | 18 | Exact match, Anker R50i ID 11 only, Anker R50i NC ID 14 only, broad query ambiguity, accessory guard ("case"), natural brand & category queries ("Apple iPhone 15", "anker r50i earbuds", "Samsung S24 Ultra phone"), alias matching & ambiguity, variant mismatch rejection, casing/whitespace/hyphen tolerance, unknown products |
| `test_whatsapp_resilience.py` | 7 | Webhook secret authentication, fromMe drop, group chat ignore, thread-safe LRU deduplication, media download failure resilience, media AI failure fallback, empty payload |
| `test_web_chat_media.py` | 8 | Text-only chat, unsupported MIME rejection (400), non-image rejection (400), file size limit rejection (400), Groq Vision flow, Groq Whisper flow, graceful media failure fallback, non-numeric customer ID rejection (400) |
| `test_order_integrity.py` | 3 | Database-authoritative pricing (ignores client-supplied price), atomic transaction rollback on failure (zero partial records), mandatory customer_id validation |
| `test_product_service.py` | 3 | Product retrieval by ID, SQL substring search, stock availability check |
| `test_order_service.py` | 5 | Successful order creation, invalid quantity, nonexistent customer/product rejection, insufficient stock rejection |
| `test_knowledge_service.py` | 4 | Knowledge document creation, RAG vector ingestion, document update with vector refresh, document deletion with vector removal |
| `test_knowledge_consistency.py` | 1 | PostgreSQL transaction rollback when vector ingestion fails |
| `test_tools.py` | 5 | `get_product_details`, `get_product_details_invalid_product`, `check_product_availability`, `check_product_availability_insufficient_stock`, `create_order` StructuredTool validation |
| `test_agent_nodes.py` | 7 | Tool input preparation (product details, availability, create order, missing quantity/product), LLM response guards against tool error hallucination |
| `test_agent_routing.py` | 8 | Intent-to-tool routing edges, conditional graph routing (availability, order, product question, policy, general customer service, prepare tool error/success) |
| `test_agent_edge_cases.py` | 7 | Missing quantity fallback to 1 for check vs error for order, missing product handling, policy route bypass, resolve product routing |
| `test_integration_order_flow.py` | 1 | End-to-end multi-turn conversation order placement with database stock verification |
| `test_controllers.py` | 5 | Health endpoint, root redirect, empty message rejection, missing message rejection, chat API valid message processing |
| `test_admin_controller.py` | 5 | Admin dashboard overview, products page, orders page, customers page, knowledge page |
| `test_admin_crud.py` | 4 | Negative values rejection, invalid numeric values rejection, negative stock rejection, knowledge CRUD synchronization |
| **Total** | **90** | **100% Passing (0 failed, 0 skipped, 0 errors)** |

The full test suite **does not call external APIs** — the LLM, Vision, Whisper, and WAHA network calls are completely mocked.

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

### Webhook Reliability & Production Protections

- **Message Deduplication:** Built-in thread-safe LRU deduplication (`WebhookDeduplicator`) caches message IDs with a 10-minute TTL (capacity: 10,000 entries). WAHA retry deliveries are detected and dropped immediately with HTTP 200, guaranteeing that duplicate webhook deliveries never trigger duplicate orders or duplicate replies.
- **Fault-Tolerant Media Handling:** When incoming messages include images or voice notes, media download or transcription errors are caught and logged without aborting the webhook. The customer's text content is still processed, and the agent responds gracefully rather than throwing an unhandled 500 error.
- **Webhook Secret Verification:** When `WAHA_WEBHOOK_SECRET` is set in `.env`, the controller verifies the incoming `X-Webhook-Secret` header using constant-time comparison, immediately rejecting unauthorized requests with 401.
- **Chat & Sender Filtering:** Group messages (`@g.us`) and self-sent messages (`fromMe: true`) are safely filtered out before hitting the agent.
- **Conversation History:** Maps each WhatsApp chat ID to a consistent customer record and maintains conversational context across turns.
