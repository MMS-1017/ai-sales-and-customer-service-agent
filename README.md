# AI Sales & Customer Service Agent

An AI-powered **Sales & Customer Service Agent for an electronics e-commerce store**, built with Flask, PostgreSQL, SQLAlchemy, LangGraph, RAG, ChromaDB, and an LLM.

The project is designed as a **modular monolith using MVC + Service + Agent + RAG layers**. The architecture keeps business logic outside Flask controllers, prevents the LLM from directly accessing the database, and separates authoritative transactional data from retrieval-oriented knowledge.

> **Assessment focus:** agent architecture, meaningful LangGraph usage, RAG, real database-backed function calling, Flask/backend architecture, ORM/database design, dashboard functionality, error handling, documentation, and the ability to explain and modify the implementation.

---

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Business Domain](#2-business-domain)
- [3. Core Features](#3-core-features)
- [4. Architecture](#4-architecture)
- [5. MVC and Supporting Layers](#5-mvc-and-supporting-layers)
- [6. Repository Structure](#6-repository-structure)
- [7. Database Design](#7-database-design)
- [8. Data Authority](#8-data-authority)
- [9. RAG Architecture](#9-rag-architecture)
- [10. RAG CRUD Synchronization](#10-rag-crud-synchronization)
- [11. LangGraph Agent](#11-langgraph-agent)
- [12. Agent State](#12-agent-state)
- [13. Tools and Function Calling](#13-tools-and-function-calling)
- [14. Conversation Context](#14-conversation-context)
- [15. Flask API and Controllers](#15-flask-api-and-controllers)
- [16. Admin Dashboard](#16-admin-dashboard)
- [17. Prompt and Grounding Rules](#17-prompt-and-grounding-rules)
- [18. Error Handling](#18-error-handling)
- [19. Security](#19-security)
- [20. Technology Stack](#20-technology-stack)
- [21. Environment Variables](#21-environment-variables)
- [22. Local Installation](#22-local-installation)
- [23. Database Setup and Seed Data](#23-database-setup-and-seed-data)
- [24. Running the Application](#24-running-the-application)
- [25. Docker](#25-docker)
- [26. Testing](#26-testing)
- [27. Example Conversations](#27-example-conversations)
- [28. End-to-End Demo](#28-end-to-end-demo)
- [29. RAG Update Demonstration](#29-rag-update-demonstration)
- [30. Failure Scenarios](#30-failure-scenarios)
- [31. Assessment Requirements Traceability](#31-assessment-requirements-traceability)
- [32. Design Decisions](#32-design-decisions)
- [33. Limitations](#33-limitations)
- [34. Future Improvements](#34-future-improvements)
- [35. Production Considerations](#35-production-considerations)
- [36. Development Workflow](#36-development-workflow)
- [37. Definition of Done](#37-definition-of-done)

---

# 1. Project Overview

This project implements an AI sales and customer-service assistant for an electronics store.

The assistant can:

- Answer product questions.
- Recommend products based on customer requirements.
- Answer policy, FAQ, shipping, warranty, and payment questions using RAG.
- Check real product availability from PostgreSQL.
- Create real orders through a database-backed tool.
- Maintain conversation context across multiple turns.
- Provide controlled responses when information is unavailable.
- Handle insufficient stock and other business failures safely.
- Allow administrators to manage products, orders, customers, and knowledge documents through a Flask/Jinja2 dashboard.
- Keep the Chroma retrieval index synchronized with knowledge-document CRUD operations.

The project deliberately avoids unnecessary distributed infrastructure. It is implemented as a **modular monolith**, making the system easier to understand, test, demonstrate, and defend during a technical interview.

---

# 2. Business Domain

## Electronics E-Commerce Store

The selected business domain is an electronics e-commerce store.

Example catalog:

- Samsung Galaxy S24
- iPhone 15
- Google Pixel 8
- MacBook Air M3

The catalog is seed/demo data and is editable through the admin dashboard.

### Main customer use cases

### Customer Service

Examples:

> What is your return policy?

> Do you offer installment payments?

> How long does shipping take?

> What is your warranty policy?

These questions are primarily answered through the RAG knowledge base.

### Sales

Examples:

> I need a phone under $700 with a good camera.

> Which phone would you recommend?

> I'm looking for a laptop for development.

Recommendations use the product database for current transactional facts such as price and stock, while RAG can provide descriptive knowledge and policies.

### Business Actions

Examples:

> Is the Samsung Galaxy S24 available?

> I want to buy 2 Samsung Galaxy S24.

Availability and order creation are handled through application tools backed by PostgreSQL.

---

# 3. Core Features

## AI Agent

- Intent understanding.
- Request routing.
- RAG retrieval.
- Tool selection/execution.
- Grounded response generation.
- Conversation context.
- Controlled error handling.

## Sales

- Product search.
- Product questions.
- Product recommendations.
- Current price lookup.
- Current stock lookup.

## Customer Service

- Return policy.
- Shipping policy.
- Warranty information.
- Payment methods.
- FAQs.
- General customer-service questions.

## RAG

- Knowledge-document storage in PostgreSQL.
- Deterministic chunking.
- Embedding generation.
- ChromaDB vector storage.
- Similarity retrieval.
- Metadata filtering.
- Add/update/delete synchronization.
- Vector-store rebuild script.
- Controlled response when relevant knowledge is unavailable.

## Business Tools

- Product availability check.
- Real order creation.
- Optional product search tool.

## Admin Dashboard

- Dashboard overview.
- Product management.
- Order viewing.
- Customer viewing.
- Knowledge-document CRUD.
- RAG synchronization through the knowledge service.

---

# 4. Architecture

The application follows a modular-monolith architecture.

```text
                         CUSTOMER / ADMIN
                                |
                                v
                  +---------------------------+
                  |           VIEWS           |
                  |     Jinja2 + HTML/CSS/JS |
                  +-------------+-------------+
                                |
                                v
                  +---------------------------+
                  |       CONTROLLERS         |
                  |       Flask Blueprints    |
                  +-------------+-------------+
                                |
                    calls Services / Agent
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
   +----------------------+              +----------------------+
   |       SERVICES      |              |     AGENT LAYER      |
   |---------------------|              |----------------------|
   | ProductService      |              | LangGraph            |
   | OrderService        |              | State                |
   | KnowledgeService    |              | Nodes                |
   +----------+-----------+              | Routing              |
              |                          | Tools                |
              v                          +----------+-----------+
   +----------------------+                         |
   |        MODELS        |                         |
   |     SQLAlchemy ORM   |                         |
   +----------+-----------+                         |
              |                          +----------+----------+
              v                          |                     |
      +---------------+                  v                     v
      |  PostgreSQL   |           +-------------+       +------------+
      | Source of     |           |     RAG     |       |    LLM     |
      | Truth         |           | ChromaDB    |       |  Provider  |
      +---------------+           +-------------+       +------------+
```

## Request Flow

A typical customer request follows this flow:

```text
Customer
   |
   v
Flask Controller
   |
   v
LangGraph Agent
   |
   +--> Understand Request
   |
   +--> Route Request
   |
   +--> Retrieve RAG Context (if needed)
   |
   +--> Execute Business Tool (if needed)
   |
   +--> Generate Response
   |
   v
Flask Controller
   |
   v
Customer
```

---

# 5. MVC and Supporting Layers

The project uses MVC as the presentation/application boundary, with dedicated Service, Agent, and RAG layers.

This is intentional: putting all business logic into Flask controllers would make the system harder to test and violate separation of concerns.

| Layer | Location | Responsibility |
|---|---|---|
| Model | `app/models/` | SQLAlchemy ORM entities |
| View | `app/views/` | Jinja2 templates, CSS, JavaScript |
| Controller | `app/controllers/` | Flask routes and request/response handling |
| Service | `app/services/` | Business rules, validation, transactions |
| Agent | `app/agent/` | LangGraph orchestration and tools |
| RAG | `app/rag/` | Embeddings, chunking, ChromaDB, retrieval |

## Model

Models define:

- Tables.
- Columns.
- Relationships.
- Database-level constraints.

Models should not contain complex business rules.

## View

Views contain:

- Jinja2 templates.
- HTML.
- CSS.
- Minimal JavaScript.

Views do not query the database directly.

## Controller

Controllers:

1. Receive an HTTP request.
2. Validate/parse request input at the interface boundary.
3. Call a Service or the Agent.
4. Return JSON or render a View.

Controllers should not:

- Query SQLAlchemy directly.
- Call the LLM directly.
- Call ChromaDB directly.
- Implement order/business rules.

## Service

Services contain business logic.

Examples:

```text
ProductService
OrderService
KnowledgeService
```

The Service layer is the main enforcement point for business rules.

## Agent

The Agent layer orchestrates:

- Intent understanding.
- Routing.
- Retrieval.
- Tool execution.
- Response generation.
- Conversation state.

The Agent does not directly manipulate SQLAlchemy models.

## RAG

The RAG layer owns:

- Text normalization.
- Chunking.
- Embeddings.
- ChromaDB storage.
- Retrieval.
- Vector synchronization.

RAG is not the source of truth for current stock or price.

---

# 6. Repository Structure

```text
ai-sales-agent/
│
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── customer.py
│   │   ├── product.py
│   │   ├── order.py
│   │   ├── order_item.py
│   │   └── knowledge.py
│   │
│   ├── views/
│   │   ├── templates/
│   │   │   ├── base.html
│   │   │   ├── chat.html
│   │   │   ├── dashboard.html
│   │   │   ├── products.html
│   │   │   ├── orders.html
│   │   │   ├── customers.html
│   │   │   └── knowledge.html
│   │   │
│   │   └── static/
│   │       ├── css/
│   │       │   └── style.css
│   │       └── js/
│   │           └── chat.js
│   │
│   ├── controllers/
│   │   ├── __init__.py
│   │   ├── chat_controller.py
│   │   └── admin_controller.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── product_service.py
│   │   ├── order_service.py
│   │   └── knowledge_service.py
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── graph.py
│   │   ├── nodes.py
│   │   ├── router.py
│   │   ├── prompts.py
│   │   └── tools.py
│   │
│   └── rag/
│       ├── __init__.py
│       ├── embeddings.py
│       ├── ingestion.py
│       ├── retriever.py
│       └── vectorstore.py
│
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_products.py
│   ├── test_orders.py
│   ├── test_rag.py
│   ├── test_tools.py
│   ├── test_agent.py
│   └── test_controllers.py
│
├── scripts/
│   ├── seed.py
│   └── rebuild_vector_store.py
│
├── chroma_data/
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── run.py
└── README.md
```

---

# 7. Database Design

PostgreSQL is the authoritative relational database.

## Entity Relationship Diagram

```text
+-------------------+
|    customers      |
+-------------------+
| id PK             |
| name              |
| email UNIQUE      |
| created_at        |
+---------+---------+
          |
          | 1
          |
          | N
+---------v---------+
|      orders       |
+-------------------+
| id PK             |
| customer_id FK    |
| status            |
| total_price       |
| created_at        |
| updated_at        |
+---------+---------+
          |
          | 1
          |
          | N
+---------v---------+
|    order_items    |
+-------------------+
| id PK             |
| order_id FK       |
| product_id FK     |
| quantity          |
| unit_price        |
+---------+---------+
          |
          | N
          |
          | 1
+---------v---------+
|     products      |
+-------------------+
| id PK             |
| name              |
| description       |
| price             |
| category          |
| stock_quantity    |
| is_active         |
| created_at        |
| updated_at        |
+-------------------+


+---------------------------+
|   knowledge_documents     |
+---------------------------+
| id PK                     |
| title                     |
| content                   |
| category                  |
| source                    |
| created_at                |
| updated_at                |
+---------------------------+
             |
             | ingestion
             v
       +-------------+
       |  ChromaDB   |
       | Vector Index|
       +-------------+
```

## Customers

Fields:

- `id`
- `name`
- `email`
- `created_at`

Constraints:

- Email is required.
- Email is unique.

Relationship:

```text
Customer 1 -> N Orders
```

## Products

Fields:

- `id`
- `name`
- `description`
- `price`
- `category`
- `stock_quantity`
- `is_active`
- `created_at`
- `updated_at`

Constraints:

- Name required.
- Description required.
- Category required.
- Price must be non-negative.
- Stock must be non-negative.

## Orders

Fields:

- `id`
- `customer_id`
- `status`
- `total_price`
- `created_at`
- `updated_at`

Possible statuses:

```text
pending
confirmed
cancelled
```

## Order Items

Fields:

- `id`
- `order_id`
- `product_id`
- `quantity`
- `unit_price`

`unit_price` is a **price snapshot**.

This means an historical order remains correct even if the product price changes later.

Example:

```text
Product price today: $649
Old order unit_price: $699
```

The old order still records `$699`.

## Knowledge Documents

Fields:

- `id`
- `title`
- `content`
- `category`
- `source`
- `created_at`
- `updated_at`

Possible categories:

```text
product
policy
shipping
warranty
payment
faq
```

---

# 8. Data Authority

One of the most important design decisions is separating authoritative transactional data from retrieval knowledge.

## PostgreSQL is authoritative for

- Current product price.
- Current stock.
- Customers.
- Orders.
- Order status.

## RAG is authoritative for

- Return policies.
- Shipping information.
- Warranty information.
- Payment methods.
- FAQs.
- Descriptive business knowledge.

## Conflict Rule

When retrieved text conflicts with PostgreSQL transactional data, PostgreSQL wins.

Example:

```text
RAG:
Samsung Galaxy S24 = $699

PostgreSQL:
Samsung Galaxy S24 = $649
```

The assistant must answer:

```text
$649
```

It must not trust a stale vectorized price.

This prevents an important class of RAG hallucination/staleness problems.

---

# 9. RAG Architecture

The RAG pipeline is:

```text
KnowledgeDocument
       |
       v
PostgreSQL
       |
       v
Normalize/Clean
       |
       v
Chunk
       |
       v
Embeddings
       |
       v
ChromaDB
       |
       v
Similarity Retrieval
       |
       v
Relevant Context
       |
       v
LLM
       |
       v
Grounded Response
```

## Why PostgreSQL + ChromaDB?

They have different responsibilities.

### PostgreSQL

Acts as the durable source of truth.

### ChromaDB

Acts as a retrieval index.

If ChromaDB is deleted or becomes inconsistent, the vector store can be rebuilt from PostgreSQL.

---

## Chunking

The initial strategy uses deterministic chunks of approximately:

```text
500–800 characters/tokens
```

with approximately:

```text
50–100 overlap
```

The exact implementation should keep these values configurable.

The objective is to preserve enough context inside each chunk while keeping retrieval focused.

---

## Metadata

Each vector contains metadata such as:

```text
document_id
title
category
source
```

This allows retrieval results to be traced back to their source document.

---

## Stable Chunk IDs

Chunks use deterministic IDs:

```text
doc-{document_id}-chunk-{chunk_index}
```

Example:

```text
doc-4-chunk-0
doc-4-chunk-1
doc-4-chunk-2
```

Stable IDs make update and delete operations reliable.

---

# 10. RAG CRUD Synchronization

Knowledge CRUD is a mandatory feature.

The database and vector index must stay synchronized.

## Create

```text
Admin Controller
      |
      v
KnowledgeService.create_document()
      |
      +--> PostgreSQL INSERT
      |
      +--> Chunk document
      |
      +--> Generate embeddings
      |
      +--> Chroma ADD
```

## Update

```text
Admin Controller
      |
      v
KnowledgeService.update_document()
      |
      +--> PostgreSQL UPDATE
      |
      +--> Delete old Chroma chunks
      |
      +--> Chunk new content
      |
      +--> Generate embeddings
      |
      +--> Chroma ADD
```

The old vectors must be removed.

Otherwise, the retriever could return stale information.

## Delete

```text
Admin Controller
      |
      v
KnowledgeService.delete_document()
      |
      +--> PostgreSQL DELETE
      |
      +--> Chroma DELETE all chunks for document
```

## Rebuild

A recovery script is provided:

```bash
python scripts/rebuild_vector_store.py
```

The script:

1. Clears/reinitializes the Chroma collection.
2. Reads all knowledge documents from PostgreSQL.
3. Chunks each document.
4. Generates embeddings.
5. Inserts the vectors into ChromaDB.

This provides a recovery mechanism if the vector index becomes inconsistent.

## Synchronization Failure

If PostgreSQL succeeds but vector synchronization fails:

- Do not silently claim success.
- Log the technical error.
- Surface a controlled admin error.
- Tell the administrator that the vector store needs rebuilding.

---

# 11. LangGraph Agent

The application uses LangGraph for explicit multi-step agent orchestration.

The graph is intentionally more than a single LLM call.

## High-Level Workflow

```text
START
  |
  v
understand_request
  |
  v
route_request
  |
  +--------------------------+
  |                          |
  v                          v
RAG path                 Tool path
  |                          |
  v                          v
retrieve_context         execute_tool
  |                          |
  +------------+-------------+
               |
               v
       generate_response
               |
               v
              END
```

A more robust implementation can use an explicit decision node:

```text
START
  |
  v
understand_request
  |
  v
retrieve_context (when needed)
  |
  v
agent_decision
  |
  +---- final answer ----> generate_response
  |
  +---- tool call -------> execute_tool
                              |
                              v
                       generate_response
                              |
                              v
                             END
```

---

# 12. Agent State

The graph maintains structured state.

Conceptually:

```python
class AgentState(TypedDict, total=False):
    messages: list
    intent: str
    customer_id: int | None
    retrieved_context: list
    tool_name: str | None
    tool_result: dict | None
    response: str | None
    error: str | None
```

## State Fields

### `messages`

Conversation history.

### `intent`

Detected request type.

Examples:

```text
product_search
product_question
recommendation
policy_question
availability_check
create_order
general_customer_service
unknown
```

### `customer_id`

Identifies the customer when a business action requires it.

### `retrieved_context`

RAG results supplied to the response-generation step.

### `tool_name`

The selected application tool.

### `tool_result`

Structured result returned from the tool.

### `response`

Final customer-facing response.

### `error`

Controlled internal error state.

---

# 13. Tools and Function Calling

The assistant uses tools for real business operations.

The LLM does not directly execute SQL.

Instead:

```text
LLM / Agent
    |
    v
Tool
    |
    v
Service
    |
    v
SQLAlchemy
    |
    v
PostgreSQL
```

---

## `check_product_availability`

Input:

```json
{
  "product_id": 1,
  "quantity": 1
}
```

Example result:

```json
{
  "available": true,
  "product_id": 1,
  "quantity_requested": 1,
  "stock_quantity": 15
}
```

The stock value comes from PostgreSQL.

---

## `create_order`

Input:

```json
{
  "customer_id": 1,
  "product_id": 1,
  "quantity": 2
}
```

Example successful result:

```json
{
  "success": true,
  "order_id": 123,
  "status": "confirmed",
  "total_price": 1399.98
}
```

This tool must actually:

1. Validate the customer.
2. Validate the product.
3. Validate product status.
4. Validate quantity.
5. Validate stock.
6. Read the current product price.
7. Create the order.
8. Create the order item.
9. Decrement stock.
10. Commit the transaction.

---

## Transactional Order Creation

```text
Validate customer
       |
       v
Validate product
       |
       v
Validate quantity
       |
       v
Validate stock
       |
       v
Read current price
       |
       v
Create Order
       |
       v
Create OrderItem
       |
       v
Decrement stock
       |
       v
COMMIT
```

If any step fails:

```text
ROLLBACK
```

No partial order should remain.

---

# 14. Conversation Context

The assistant supports multi-turn conversations.

Example:

```text
User:
I'm interested in the Samsung Galaxy S24.

Agent:
The Samsung Galaxy S24 is ...

User:
What's its price?

Agent:
The Samsung Galaxy S24 currently costs ...
```

The word `"its"` should be resolved from the conversation context.

Conversation state must be scoped per conversation.

Do not use a global Python variable for customer conversation state.

A conversation ID can be associated with the LangGraph state/checkpoint mechanism.

The system must ensure that one customer's conversation is never exposed to another customer.

---

# 15. Flask API and Controllers

The application uses the Flask application-factory pattern.

## Chat Controller

Main routes:

```text
GET  /chat
POST /api/chat
GET  /health
```

### `GET /chat`

Renders the chat interface.

### `POST /api/chat`

Request:

```json
{
  "message": "What is your return policy?",
  "conversation_id": "conversation-123"
}
```

Response:

```json
{
  "response": "Our return policy is ...",
  "conversation_id": "conversation-123"
}
```

### `GET /health`

Returns:

```json
{
  "status": "ok"
}
```

---

# 16. Admin Dashboard

The admin dashboard is implemented using Flask + Jinja2.

No React is required.

## Dashboard

Provides an overview of business data and navigation to:

- Products.
- Orders.
- Customers.
- Knowledge.

## Products

The administrator can:

- List products.
- Add products.
- Edit products.
- Delete/deactivate products.
- View stock.
- View current price.

## Orders

The administrator can view:

- Order ID.
- Customer.
- Status.
- Total.
- Creation time.
- Order items where appropriate.

## Customers

The administrator can view:

- Customer ID.
- Name.
- Email.
- Order count where convenient.

## Knowledge

The administrator can:

- List knowledge documents.
- Add documents.
- Edit documents.
- Delete documents.

Knowledge mutations go through:

```text
Admin Controller
      |
      v
KnowledgeService
      |
      +--> PostgreSQL
      |
      +--> ChromaDB synchronization
```

This is one of the key assessment demonstrations.

---

# 17. Prompt and Grounding Rules

The agent uses explicit grounding rules.

## System Prompt Principles

The assistant should:

- Act as an electronics-store sales/customer-service assistant.
- Be helpful and concise.
- Use retrieved knowledge when answering business-knowledge questions.
- Use tools for actions requiring current backend state.
- Never invent business facts.
- Ask for clarification when required information is missing.
- Prefer current PostgreSQL facts for price/stock/order information.
- Never claim an order was created unless the order tool confirms success.

## RAG Prompt

Conceptually:

```text
Answer using the supplied business context.

If the context does not contain the answer,
say that the information is unavailable.

Do not invent policies, prices, stock levels,
or order details.
```

## Tool Prompt

Conceptually:

```text
Never claim an action succeeded unless the
tool returned success.
```

---

# 18. Error Handling

The application handles errors at multiple layers.

## Database Errors

Examples:

- Connection failure.
- Constraint violation.
- Transaction failure.

Customer-facing response should be controlled.

Technical details go to logs.

## RAG Errors

Examples:

- Embedding failure.
- ChromaDB failure.
- Retrieval failure.

The application should not fabricate an answer.

## LLM Errors

Examples:

- Timeout.
- Provider error.
- Invalid structured output.

Return a safe message rather than exposing a stack trace.

## Tool Errors

Examples:

- Product not found.
- Customer not found.
- Invalid quantity.
- Insufficient stock.
- Product inactive.

These become structured tool results and are converted into customer-friendly responses.

## HTTP Errors

The application handles:

```text
400 Bad Request
404 Not Found
500 Internal Server Error
```

API errors should return structured JSON.

Dashboard errors should use Flask flash messages.

---

# 19. Security

The project includes basic security practices.

## Secrets

Secrets are stored in environment variables.

Never commit:

```text
.env
```

Never hard-code API keys.

## Database Access

The LLM must never generate and execute arbitrary SQL.

All database operations go through application code and SQLAlchemy.

## Input Validation

Validate:

- Form fields.
- API fields.
- Product IDs.
- Customer IDs.
- Quantities.
- Prices.
- Knowledge-document fields.

## No Arbitrary Code Execution

Do not use:

```python
eval(...)
```

Do not allow the LLM to execute arbitrary Python.

## Admin Authentication

For the assessment, basic admin routes may remain unauthenticated to keep scope manageable.

For production, authentication and authorization should be added.

## Sensitive Logging

Never log:

- API keys.
- Passwords.
- Unnecessary customer-sensitive information.

---

# 20. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.11+ | Main language |
| Flask | Web application/backend |
| Flask-SQLAlchemy | ORM integration |
| PostgreSQL | Relational source of truth |
| SQLAlchemy | Database ORM |
| Jinja2 | Server-side templates |
| HTML/CSS/JS | UI |
| LangGraph | Agent orchestration |
| LangChain | LLM/tool integrations where useful |
| ChromaDB | Vector retrieval |
| Sentence Transformers / embedding provider | Embeddings |
| LLM Provider | Language understanding and generation |
| Pydantic | Structured validation |
| pytest | Testing |
| Docker | Containerization |
| Docker Compose | Local multi-container environment |
| python-dotenv | Environment configuration |

Provider-specific LLM/embedding integrations should be isolated so they can be replaced without rewriting the entire graph.

---

# 21. Environment Variables

Create a local `.env` from `.env.example`.

Example:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_sales_agent

LLM_API_KEY=your_api_key
LLM_MODEL=your_model

EMBEDDING_MODEL=your_embedding_model

CHROMA_PATH=./chroma_data

FLASK_SECRET_KEY=change_me
```

## Variables

### `DATABASE_URL`

PostgreSQL connection string.

### `LLM_API_KEY`

API key for the selected LLM provider.

### `LLM_MODEL`

Model name used by the LLM adapter.

### `EMBEDDING_MODEL`

Embedding model used by the RAG layer.

### `CHROMA_PATH`

Persistent ChromaDB storage location.

### `FLASK_SECRET_KEY`

Flask session/security key.

> Never commit the real `.env` file.

---

# 22. Local Installation

## Prerequisites

Install:

- Python 3.11+
- Git
- PostgreSQL, or Docker Desktop with Docker Compose
- An API key for the selected LLM provider if using a hosted model

## Clone the Repository

```bash
git clone <repository-url>
cd ai-sales-agent
```

## Create Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Configure Environment

Windows:

```powershell
copy .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Edit `.env` with the required values.

---

# 23. Database Setup and Seed Data

The seed script provides deterministic development data.

Expected seed content:

### Products

At least:

```text
Samsung Galaxy S24
iPhone 15
Google Pixel 8
MacBook Air M3
```

### Customer

At least one demo customer.

### Knowledge Documents

At least:

```text
Return Policy
Shipping Policy
Warranty Policy
Payment Methods
```

Run:

```bash
python scripts/seed.py
```

The exact reset/reseed behavior should be documented by the implementation.

---

# 24. Running the Application

After PostgreSQL is running and the environment is configured:

```bash
python scripts/seed.py
python run.py
```

The application will be available at:

```text
http://127.0.0.1:5000
```

Health endpoint:

```text
http://127.0.0.1:5000/health
```

Chat:

```text
http://127.0.0.1:5000/chat
```

Admin dashboard:

```text
http://127.0.0.1:5000/admin
```

---

# 25. Docker

The project provides:

```text
Dockerfile
docker-compose.yml
```

The Compose environment contains at least:

```text
app
postgres
```

PostgreSQL data should use a persistent volume.

ChromaDB data should also be persisted through a mounted directory or volume.

## Start

```bash
docker compose up -d
```

## View Logs

```bash
docker compose logs -f app
```

## Stop

```bash
docker compose down
```

To remove persistent development data as well:

```bash
docker compose down -v
```

> Be careful with `-v`: it removes Docker volumes and therefore can delete local development database data.

All secrets and configuration should be provided through environment variables.

---

# 26. Testing

The test suite uses `pytest`.

Run:

```bash
pytest
```

or:

```bash
pytest -v
```

## Model Tests

Verify:

- Product creation.
- Customer uniqueness.
- Relationships.
- Database constraints.

## Product Tests

Verify:

- Valid product.
- Product lookup.
- Availability.
- Unavailable product.
- Stock validation.

## Order Tests

Verify:

- Successful order.
- Correct total.
- Correct order item.
- Stock decrement.
- Missing product.
- Invalid quantity.
- Insufficient stock.
- Transaction rollback.

## RAG Tests

Verify:

```text
Create document
      |
      v
Retrieve document
```

Then:

```text
Update document
      |
      v
Retrieve updated content
      |
      v
Old content must not be returned
```

Then:

```text
Delete document
      |
      v
Deleted content must no longer be retrieved
```

## Tool Tests

Verify:

- Availability tool.
- Create-order tool.
- Invalid input.
- Insufficient stock.
- Service integration.

## Agent Tests

Use mocked LLM/retriever/tool components where appropriate.

Verify:

```text
Policy question -> RAG
Availability -> availability tool
Purchase -> create-order tool
Unknown request -> safe response
```

The full test suite should not depend on external API availability.

---

# 27. Example Conversations

## Example 1 — Customer Service / RAG

```text
User:
What is your return policy?

Agent:
Our return policy allows ...
```

Expected behavior:

```text
User request
    |
    v
Intent = policy_question
    |
    v
RAG retrieval
    |
    v
Relevant return-policy chunks
    |
    v
Grounded response
```

---

## Example 2 — Product Recommendation

```text
User:
I need a phone under $700 with a good camera.
```

Expected behavior:

1. Understand recommendation intent.
2. Search current products.
3. Use PostgreSQL for current prices/availability.
4. Optionally use RAG for descriptive information.
5. Recommend suitable products.

The assistant must not present stale vectorized prices as current.

---

## Example 3 — Availability

```text
User:
Is the Samsung Galaxy S24 available?
```

Expected behavior:

```text
Intent
  |
  v
availability_check
  |
  v
check_product_availability
  |
  v
PostgreSQL
  |
  v
Current stock
```

---

## Example 4 — Real Order

```text
User:
I want to buy 2 Samsung Galaxy S24.
```

Expected behavior:

```text
Intent = create_order
       |
       v
create_order tool
       |
       v
OrderService
       |
       v
Validate
       |
       v
Create Order + OrderItem
       |
       v
Decrement stock
       |
       v
COMMIT
       |
       v
Return order ID
       |
       v
Agent confirms successful order
```

The order must be visible in the admin dashboard.

---

# 28. End-to-End Demo

The recommended assessment demonstration is:

## Step 1 — Start the Application

```bash
docker compose up -d
```

or start PostgreSQL locally and run:

```bash
python run.py
```

## Step 2 — Open Chat

Open:

```text
/chat
```

## Step 3 — Demonstrate RAG

Ask:

```text
What is your return policy?
```

Show that the answer is based on the knowledge base.

## Step 4 — Demonstrate Recommendation

Ask:

```text
I need a phone under $700 with a good camera.
```

Show that the recommendation uses current product data.

## Step 5 — Demonstrate Availability

Ask:

```text
Is the Samsung Galaxy S24 available?
```

Show the database-backed availability result.

## Step 6 — Demonstrate Real Business Action

Ask:

```text
I want to buy 2 Samsung Galaxy S24.
```

Show:

- Tool execution.
- Order creation.
- Stock decrement.
- Order ID.
- Successful transaction.

## Step 7 — Open Admin Dashboard

Navigate to:

```text
/admin/orders
```

Show the created order.

## Step 8 — Demonstrate RAG CRUD

Open:

```text
/admin/knowledge
```

Edit the return policy.

Example:

```text
30-day return policy
```

Change it to:

```text
45-day return policy
```

Save it.

Ask the agent:

```text
Can I return an item after 40 days?
```

The agent should use the updated knowledge.

## Step 9 — Demonstrate Conversation Context

Ask:

```text
I'm interested in the Samsung Galaxy S24.
```

Then:

```text
What's its price?
```

The agent should resolve `"its"` using conversation context.

## Step 10 — Demonstrate Failure Handling

Ask:

```text
I want to buy 100 Samsung Galaxy S24.
```

Expected behavior:

- No order created.
- No stock corruption.
- Helpful insufficient-stock response.
- Error handled through the application/service layer.

---

# 29. RAG Update Demonstration

This is one of the most important demonstrations because the assessment requires knowledge add/update/delete operations to be reflected in retrieval.

## Initial State

Knowledge document:

```text
Title: Return Policy

Customers can return eligible products within 30 days.
```

Ask:

```text
Can I return this after 20 days?
```

Expected:

```text
Yes, according to the current return policy...
```

## Update

Administrator changes:

```text
30 days
```

to:

```text
45 days
```

The system:

```text
PostgreSQL UPDATE
      |
      v
Delete old Chroma chunks
      |
      v
Chunk new document
      |
      v
Embed new chunks
      |
      v
Chroma ADD
```

## Verify

Ask:

```text
Can I return this after 40 days?
```

Expected:

```text
Yes, based on the updated 45-day policy...
```

The old 30-day vector must not remain available to retrieval.

---

# 30. Failure Scenarios

## Insufficient Stock

Request:

```text
Buy 100 Samsung Galaxy S24.
```

Expected:

```text
No order created.
Stock remains unchanged.
Customer receives a clear message.
```

## Product Not Found

Request:

```text
Buy 2 Unknown Phone XYZ.
```

Expected:

```text
Product not found.
No transaction is committed.
```

## Invalid Quantity

Request:

```text
Buy -5 Samsung Galaxy S24.
```

Expected:

```text
Tool/service rejects the request.
No database mutation.
```

## Missing RAG Knowledge

Request:

```text
What is your policy about a topic that does not exist in the knowledge base?
```

Expected:

```text
The assistant should state that the information
is unavailable rather than inventing a policy.
```

## LLM Failure

If the LLM provider is unavailable:

```text
Return a controlled error message.
Log technical details.
Do not expose stack traces.
```

## Vector Store Failure

If ChromaDB fails during synchronization:

```text
Do not silently claim synchronization succeeded.
Log the failure.
Inform the administrator.
Use rebuild_vector_store.py as the recovery path.
```

---

# 31. Assessment Requirements Traceability

| Assessment Requirement | Implementation |
|---|---|
| Customer service | LangGraph Agent + RAG + conversation context |
| Sales | Product search/recommendation |
| Product questions | Product database + RAG |
| Current prices | PostgreSQL |
| Conversation context | Per-conversation agent state/checkpointing |
| RAG | `app/rag/` + ChromaDB + embeddings |
| Add knowledge | Knowledge CRUD + vector synchronization |
| Update knowledge | Delete old vectors + insert updated vectors |
| Delete knowledge | Delete document vectors |
| Meaningful LangGraph | Intent → routing → retrieval/tool → response |
| Function calling | Availability and order tools |
| Real business action | `create_order` writes to PostgreSQL |
| Flask backend | Flask application factory + controllers |
| ORM | SQLAlchemy |
| Relational database | PostgreSQL |
| Dashboard | Flask + Jinja2 |
| Business data management | Products, orders, customers |
| RAG management | Knowledge CRUD |
| Error handling | Service/agent/controller error handling |
| Documentation | This README |
| Testing | pytest unit/integration tests |
| Docker | Dockerfile + Docker Compose |
| Meta Messenger | Optional future/bonus integration |

---

# 32. Design Decisions

## Why a Modular Monolith?

The assessment does not require distributed architecture.

A modular monolith provides:

- Simpler development.
- Easier debugging.
- Easier local setup.
- Clear module boundaries.
- Lower operational complexity.
- Better suitability for a junior-level technical assessment.

There is no need for:

- Kubernetes.
- Kafka.
- Redis.
- Microservices.
- React.

unless the project requirements change.

---

## Why MVC?

MVC provides a clear separation between:

```text
Model
View
Controller
```

But business logic is intentionally separated into Services.

This avoids a common problem where Flask route handlers become large functions containing:

- Database queries.
- Validation.
- Business logic.
- LLM calls.
- HTML rendering.

Instead:

```text
Controller -> Service -> Model/Database
Controller -> Agent -> Service/RAG/LLM
```

---

## Why a Service Layer?

Consider order creation.

The order operation contains multiple rules:

```text
Customer exists
Product exists
Product active
Quantity > 0
Stock sufficient
Calculate total
Create order
Create item
Decrement stock
Commit transaction
```

Putting these rules inside a Flask controller would make them difficult to reuse and test.

`OrderService` provides one centralized business operation.

---

## Why PostgreSQL as Source of Truth?

Transactional facts require consistency.

For example:

```text
Stock = 3
```

must come from the current database state.

A vector index is optimized for semantic retrieval, not transactional consistency.

---

## Why ChromaDB?

ChromaDB provides a simple local vector database suitable for:

- Semantic retrieval.
- Metadata.
- Persistent local development.
- Demonstrating RAG clearly.

The architecture keeps it replaceable.

---

## Why LangGraph?

LangGraph is useful because the assistant is not simply:

```text
Prompt -> LLM -> Response
```

The application has explicit workflow steps:

```text
Understand
   |
Route
   |
Retrieve / Tool
   |
Respond
```

This makes the agent behavior:

- More explicit.
- Easier to debug.
- Easier to test.
- Easier to extend.
- Easier to explain during an interview.

---

## Why Tools Instead of Letting the LLM Write SQL?

The LLM is probabilistic.

Database mutations require deterministic validation.

Therefore:

```text
LLM decides:
"I should create an order."

Application decides:
"Is this order valid?"
```

The LLM cannot bypass:

- Stock validation.
- Quantity validation.
- Product validation.
- Customer validation.
- Transaction handling.

---

# 33. Limitations

This implementation is intentionally scoped for the assessment.

## Authentication

The admin dashboard may be unauthenticated during assessment development.

Production deployment should add:

- Authentication.
- Authorization.
- Admin roles.
- CSRF protection.

## LLM Provider Dependency

The quality of natural-language understanding and response generation depends on the configured LLM provider.

## Simple Retrieval

The initial retriever uses standard semantic similarity.

More advanced systems could add:

- Reranking.
- Hybrid search.
- Query expansion.
- HyDE.
- Metadata-aware retrieval.
- Retrieval evaluation.

## Local Vector Database

ChromaDB is suitable for this assessment and local deployment.

A production system may use a managed/distributed vector database depending on scale.

## No Distributed Architecture

The application is a modular monolith.

It does not attempt to solve:

- Multi-region deployment.
- Distributed task queues.
- Horizontal event-driven processing.
- Large-scale service decomposition.

These are outside the core assessment scope.

## Admin Authentication

Authentication is intentionally kept out of the mandatory scope so that effort can focus on the required AI/agent/RAG/backend functionality.

## Messenger Integration

Meta Messenger is not part of the mandatory implementation and should only be added after the core system is stable.

---

# 34. Future Improvements

Potential improvements include:

## Meta Messenger

```text
Customer
   |
Messenger
   |
Meta Webhook
   |
Flask Controller
   |
LangGraph Agent
   |
RAG / Tools
   |
Response
   |
Messenger
```

The same Agent and Service layers should be reused.

## Authentication

Add:

- Admin login.
- Role-based access control.
- Session security.
- CSRF protection.

## Retrieval Quality

Add:

- Hybrid search.
- Reranking.
- Query rewriting.
- Metadata filtering.
- Retrieval evaluation.
- Better chunking strategies.

## Evaluation

Introduce:

- RAG evaluation datasets.
- Retrieval precision/recall.
- Answer faithfulness.
- Groundedness.
- Tool success rate.
- End-to-end task completion rate.

## Observability

Add:

- Structured logs.
- Tracing.
- Agent execution metrics.
- Tool latency.
- Retrieval latency.
- LLM latency.
- Error-rate monitoring.

## Production Vector Store

Replace local ChromaDB with a production-ready vector infrastructure if scale requires it.

---

# 35. Production Considerations

Before production deployment, the following should be addressed:

### Security

- Admin authentication.
- Authorization.
- CSRF protection.
- Secure secret management.
- HTTPS.
- Rate limiting.
- Input validation.
- Audit logging.

### Reliability

- Database connection pooling.
- Retry policies.
- Timeouts.
- Health checks.
- Transaction monitoring.
- Vector-store consistency monitoring.

### Observability

- Structured logs.
- Metrics.
- Distributed tracing.
- Agent/tool execution tracing.
- Alerting.

### AI Reliability

- Prompt/version management.
- RAG evaluation.
- Hallucination monitoring.
- Tool-call validation.
- Guardrails.
- Model fallback strategies.

### Scalability

If traffic grows significantly, components can later be separated into services.

The current modular boundaries make that transition easier because business logic is already separated from controllers and the agent.

---

# 36. Development Workflow

The project should be developed incrementally.

Recommended implementation order:

```text
Phase 1  - Foundation
Phase 2  - Database Models
Phase 3  - Services
Phase 4  - RAG
Phase 5  - LangGraph Agent
Phase 6  - Tools
Phase 7  - Chat UI/API
Phase 8  - Admin Dashboard
Phase 9  - Integration
Phase 10 - Testing & Hardening
Phase 11 - Documentation
Phase 12 - Optional Meta Messenger
```

## Phase 1 — Foundation

- Repository structure.
- Configuration.
- Flask application factory.
- Extensions.
- PostgreSQL connection.
- Docker Compose.
- Health endpoint.

## Phase 2 — Models

- Customer.
- Product.
- Order.
- OrderItem.
- KnowledgeDocument.
- Relationships.
- Constraints.
- Seed data.

## Phase 3 — Services

- ProductService.
- OrderService.
- KnowledgeService.
- Unit tests.
- Transaction tests.

## Phase 4 — RAG

- Embedding adapter.
- Chroma vector store.
- Chunking.
- Ingestion.
- Retriever.
- CRUD synchronization.
- Rebuild script.

## Phase 5 — Agent

- State.
- Prompts.
- Intent schema.
- Understanding node.
- Routing.
- Retrieval.
- Response generation.
- Error paths.

## Phase 6 — Tools

- Availability tool.
- Order tool.
- Pydantic schemas.
- Service integration.

## Phase 7 — Chat

- Chat controller.
- Chat view.
- API endpoint.
- Conversation ID.
- Conversation state.

## Phase 8 — Dashboard

- Dashboard.
- Product management.
- Orders.
- Customers.
- Knowledge CRUD.
- RAG synchronization feedback.

## Phase 9 — Integration

Verify:

```text
Chat -> Agent -> RAG
Chat -> Agent -> Tool -> Database
Admin -> Knowledge -> RAG
Admin -> Orders
```

## Phase 10 — Testing & Hardening

- Full test suite.
- Edge cases.
- Failure scenarios.
- Clean environment test.
- Docker test.

## Phase 11 — Documentation

Update:

- Architecture.
- ERD.
- LangGraph workflow.
- RAG workflow.
- Installation.
- Examples.
- Limitations.

## Phase 12 — Bonus

Only after all mandatory requirements work:

```text
Meta Messenger integration
```

---

# 37. Definition of Done

The project is considered complete only when a clean environment can perform the following:

```text
1. Start PostgreSQL.
2. Start Flask.
3. Seed the database.
4. Open the chat.
5. Ask a policy question.
6. Retrieve the answer through RAG.
7. Ask for a product recommendation.
8. Use current product information.
9. Check product stock.
10. Create a real order through a tool.
11. See the created order in the admin dashboard.
12. Edit a knowledge document.
13. Ask the same knowledge question again.
14. Verify that updated content is retrieved.
15. Delete a knowledge document.
16. Verify that deleted content is no longer retrieved.
17. Test insufficient stock.
18. Verify that failed orders do not corrupt stock.
19. Run the test suite successfully.
20. Run the application through Docker.
21. Follow the README from a clean environment.
```

---

# Assessment Alignment

The implementation is designed specifically around the core assessment expectations:

- **Agent Architecture:** explicit LangGraph workflow.
- **LangGraph:** meaningful multi-node orchestration.
- **RAG:** embeddings, ChromaDB, retrieval, CRUD synchronization.
- **Function Calling:** real DB-backed business action.
- **Backend:** Flask application factory and Controllers.
- **Database:** PostgreSQL + SQLAlchemy ORM.
- **Dashboard:** Flask + Jinja2.
- **Code Quality:** layered modular architecture.
- **Error Handling:** controlled failures and transaction safety.
- **Documentation:** architecture, setup, examples, and limitations.
- **Understanding:** every major layer has a clear responsibility and can be explained independently.

---

## License

This project is intended as a technical-assessment/demo application. Add an appropriate license if the repository will be publicly distributed.
