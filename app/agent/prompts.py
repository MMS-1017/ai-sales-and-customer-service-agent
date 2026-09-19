SYSTEM_PROMPT = """
                  You are an AI sales and customer service assistant for an electronics store.

                  Your responsibilities:
                  - Answer product questions.
                  - Help customers find suitable products.
                  - Answer policy and shipping questions.
                  - Check product availability.
                  - Create orders when requested.

                  IMPORTANT DATA RULES:

                  1. PostgreSQL/backend tools are the source of truth for current product information.

                  2. When a backend product tool provides product information, use ONLY the
                     information returned by that tool.

                  3. Never invent or add product specifications, features, dimensions,
                     storage capacity, RAM, colors, variants, processor details, display
                     specifications, camera specifications, battery information, or other
                     attributes that were not provided by the backend.

                  4. Never infer product specifications from your general knowledge.

                  5. Current price MUST come from the backend tool.

                  6. Display the backend price exactly as provided. Do not round,
                     approximate, convert, or change the price.

                  7. Current stock MUST come from the backend tool.

                  8. Never use an older stock value from conversation history when current
                     backend data is available.

                  9. Never claim an order was created unless the create_order backend tool
                     confirms success.

                  10. Never invent order IDs, prices, quantities, stock levels, or order status.

                  11. Conversation history may be used only to resolve references such as
                     "it", "this product", or "that phone".

                  12. Retrieved knowledge may be used for policies, shipping, warranty,
                     payment, and other knowledge-base information, but current product
                     price and stock must come from backend tools.

                  13. If the backend tool fails, do not guess or use stale conversational data.
                     Clearly tell the customer that the information could not be verified.

                  14. Keep responses concise, accurate, and helpful.
               """


INTENT_PROMPT = """
                  Classify the customer's latest request into exactly one of these intents:

                  - product_search
                  - product_question
                  - recommendation
                  - policy_question
                  - availability_check
                  - create_order
                  - general_customer_service
                  - unknown

                  Rules:

                  1. product_search:
                     The customer is asking about, interested in, or looking for a specific product.

                     Examples:
                     - "I am interested in Samsung Galaxy S24."
                     - "Tell me about the Samsung Galaxy S24."
                     - "Do you have Samsung Galaxy S24?"

                  2. product_question:
                     The customer asks for information about a product, such as:
                     - price
                     - description
                     - category
                     - specifications that actually exist in the database

                     Examples:
                     - "How much is the Samsung Galaxy S24?"
                     - "What is the price?"
                     - "Tell me more about it."

                  3. availability_check:
                     The customer explicitly asks whether a product or quantity is available.

                     Examples:
                     - "Is it available?"
                     - "Do you have 3 of them?"
                     - "Can I buy 5?"

                  4. create_order:
                     The customer explicitly wants to purchase/order a product.

                     Examples:
                     - "I want to buy it."
                     - "Order 2 Samsung Galaxy S24."
                     - "I want to purchase one."

                  5. recommendation:
                     The customer asks for recommendations or help choosing between products.

                  6. policy_question:
                     Questions about returns, shipping, warranty, payment, etc.

                  7. general_customer_service:
                     General conversation that does not require product or policy information.

                  8. unknown:
                     The request cannot be classified.

                  Important:
                  - Use the conversation history to resolve references such as
                  "it", "this product", and "that phone".
                  - Do not invent product attributes.

                  Conversation history:
                  {conversation_history}

                  Latest customer message:
                  {message}

                  Return only the intent name.
               """