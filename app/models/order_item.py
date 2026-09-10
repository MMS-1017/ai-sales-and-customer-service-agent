from app.extensions import db


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False,
        index=True,
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False,
        index=True,
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
    )

    unit_price = db.Column(
        db.Numeric(10, 2),
        nullable=False,
    )

    order = db.relationship(
        "Order",
        back_populates="items",
    )

    product = db.relationship(
        "Product",
        back_populates="order_items",
    )

    def __repr__(self):
        return f"<OrderItem order={self.order_id} product={self.product_id}>"