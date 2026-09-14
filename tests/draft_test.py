from app import create_app
from app.agent import agent_graph

app = create_app()

with app.app_context():
    result = agent_graph.invoke(
        {
            "messages": [
                "I want to buy 2 Samsung Galaxy S24"
            ],
            "customer_id": 1,
        }
    )
    print(result)