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

                  7. Use backend data to determine whether a product is available.

                  8. Never reveal exact stock quantities or the number of units remaining.
                     Tell the customer only whether the product is available or unavailable.

                  9. Never use an older stock value from conversation history when current
                     backend data is available.

                  10. Never claim an order was created unless the create_order backend tool
                     confirms success.

                  11. Never invent order IDs, prices, quantities, availability, or order status.

                  12. Conversation history may be used only to resolve references such as
                     "it", "this product", or "that phone".

                  13. Retrieved knowledge may be used for policies, shipping, warranty,
                     payment, and other knowledge-base information, but current product
                     price and availability must come from backend tools.

                  14. If the backend tool fails, do not guess or use stale conversational data.
                     Clearly tell the customer that the information could not be verified.

                  15. Keep responses concise, accurate, and helpful.
               """


INTENT_PROMPT = """
                  Classify the customer's latest request into exactly one of these intents:

                  - product_search
                  - product_question
                  - product_comparison
                  - recommendation
                  - policy_question
                  - availability_check
                  - create_order
                  - general_customer_service
                  - unknown

                  Rules:

                  1. product_comparison:
                     The customer asks to compare two or more products, or asks about the
                     difference between products that were listed or discussed earlier.
                     Use this intent for references such as "what is the difference between them?",
                     "compare these", "which one is better?", or "what is the difference between
                     each one?" when multiple products are present in the conversation history.

                  2. product_search:
                     The customer is asking about, interested in, or looking for a SPECIFIC named product.
                     The customer must mention a recognizable product name or model number.
                     Do NOT use this intent if the customer mentions only a category (e.g. 'headphones', 'laptops').

                     Examples:
                     - "I am interested in Samsung Galaxy S24."
                     - "Tell me about the Samsung Galaxy S24."
                     - "Do you have Samsung Galaxy S24?"

                  3. product_question:
                     The customer asks for information about a product, such as:
                     - price
                     - description
                     - category
                     - specifications that actually exist in the database

                     Examples:
                     - "How much is the Samsung Galaxy S24?"
                     - "What is the price?"
                     - "Tell me more about it."

                  4. availability_check:
                     The customer explicitly asks whether a product or quantity is available.

                     Examples:
                     - "Is it available?"
                     - "Do you have 3 of them?"
                     - "Can I buy 5?"

                  5. create_order:
                     The customer explicitly wants to purchase/order a product.

                     Examples:
                     - "I want to buy it."
                     - "Order 2 Samsung Galaxy S24."
                     - "I want to purchase one."

                  6. recommendation:
                     The customer asks for product recommendations OR is browsing by
                     category/price/feature without naming specific products. Use
                     product_comparison when comparing two or more identified products.

                     Examples:
                     - "I want headphones with price below 1000."
                     - "Show me laptops under $1500."
                     - "What smartphones do you have?"
                     - "Recommend me a good phone."

                  7. policy_question:
                     Questions about returns, shipping, warranty, payment, etc.

                  8. general_customer_service:
                     General conversation that does not require product or policy information.

                  9. unknown:
                     The request cannot be classified.

                  Important:
                  - Use the conversation history to resolve references such as
                  "it", "this product", and "that phone".
                  - When the customer asks to compare multiple previously listed products,
                    choose product_comparison, not recommendation or product_question.
                  - Do not invent product attributes.

                  Conversation history:
                  {conversation_history}

                  Latest customer message:
                  {message}

                  Return only the intent name.
               """