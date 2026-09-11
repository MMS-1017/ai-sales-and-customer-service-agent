from app import create_app
from app.extensions import db
from app.models import Customer, Product, KnowledgeDocument


def seed_database():
    app = create_app()

    with app.app_context():
        # Prevent duplicate seed data
        if Product.query.first():
            print("Database already contains products. Skipping seed.")
            return

        # -------------------------
        # Customers
        # -------------------------
        customer = Customer(
            name="Ahmed Hassan",
            email="ahmed@example.com",
        )

        db.session.add(customer)

        # -------------------------
        # Products
        # -------------------------
        products = [
            Product(
                name="Samsung Galaxy S24",
                description=(
                    "Samsung Galaxy S24 smartphone with a 6.2-inch Dynamic AMOLED "
                    "display, high-performance processor, advanced camera system, "
                    "and long-lasting battery."
                ),
                price=699.99,
                category="Smartphones",
                stock_quantity=15,
            ),
            Product(
                name="iPhone 15",
                description=(
                    "Apple iPhone 15 with a 6.1-inch Super Retina XDR display, "
                    "A16 Bionic chip, advanced dual-camera system, and USB-C."
                ),
                price=799.99,
                category="Smartphones",
                stock_quantity=10,
            ),
            Product(
                name="Google Pixel 8",
                description=(
                    "Google Pixel 8 smartphone featuring Google's Tensor processor, "
                    "excellent computational photography, a 6.2-inch OLED display, "
                    "and a clean Android experience."
                ),
                price=599.99,
                category="Smartphones",
                stock_quantity=8,
            ),
            Product(
                name="MacBook Air M3",
                description=(
                    "Apple MacBook Air powered by the M3 chip, featuring a lightweight "
                    "design, long battery life, high-resolution display, and strong "
                    "performance for productivity and development."
                ),
                price=1099.99,
                category="Laptops",
                stock_quantity=6,
            ),
        ]

        db.session.add_all(products)

        # -------------------------
        # Knowledge Documents
        # -------------------------
        knowledge_documents = [
            KnowledgeDocument(
                title="Return Policy",
                category="policy",
                source="store_policy",
                content=(
                    "Customers can return eligible products within 30 days of purchase. "
                    "Products must be in good condition and include the original "
                    "packaging and accessories. Some products may be subject to "
                    "additional return restrictions."
                ),
            ),
            KnowledgeDocument(
                title="Shipping Policy",
                category="shipping",
                source="store_policy",
                content=(
                    "Standard shipping usually takes 3 to 5 business days. "
                    "Customers receive tracking information after the order is shipped. "
                    "Delivery times may vary depending on the destination."
                ),
            ),
            KnowledgeDocument(
                title="Warranty Policy",
                category="warranty",
                source="store_policy",
                content=(
                    "Eligible electronics come with a one-year limited warranty "
                    "covering manufacturing defects. The warranty does not cover "
                    "accidental damage, misuse, or unauthorized modifications."
                ),
            ),
            KnowledgeDocument(
                title="Payment Methods",
                category="payment",
                source="store_policy",
                content=(
                    "Customers can pay using major credit and debit cards. "
                    "Payment must be successfully authorized before an order "
                    "is confirmed."
                ),
            ),
        ]

        db.session.add_all(knowledge_documents)

        db.session.commit()

        print("Database seeded successfully.")
        print(f"Products added: {len(products)}")
        print(f"Knowledge documents added: {len(knowledge_documents)}")
        print("Customer added: 1")


if __name__ == "__main__":
    seed_database()