"""Idempotent Omnichannel schema creation and legacy identity backfill helper."""

from app import create_app
from app.extensions import db
from app.models import Customer, CustomerChannelIdentity, ensure_schema_columns


def run_omnichannel_migration():
    """Create new omnichannel tables and backfill legacy synthetic channel customers."""
    app = create_app()
    with app.app_context():
        db.create_all()
        ensure_schema_columns()
        backfilled = 0

        for customer in Customer.query.all():
            raw_email = (customer.email or "").strip()
            email = raw_email.lower()
            if email.startswith("whatsapp_") and email.endswith("@whatsapp.local"):
                raw_phone = raw_email[len("whatsapp_"):-len("@whatsapp.local")]
                external_user_id = f"{raw_phone}@c.us" if "@" not in raw_phone else raw_phone
                exists = CustomerChannelIdentity.query.filter_by(
                    channel="whatsapp",
                    channel_account_id="",
                    external_user_id=external_user_id,
                ).first()
                if not exists:
                    db.session.add(
                        CustomerChannelIdentity(
                            customer_id=customer.id,
                            channel="whatsapp",
                            channel_account_id="",
                            external_user_id=external_user_id,
                            display_name=customer.name,
                            is_verified=True,
                        )
                    )
                    backfilled += 1

            elif email.startswith("facebook_") and email.endswith("@facebook.local"):
                psid = raw_email[len("facebook_"):-len("@facebook.local")]
                exists = CustomerChannelIdentity.query.filter_by(
                    channel="facebook",
                    channel_account_id="",
                    external_user_id=psid,
                ).first()
                if not exists:
                    db.session.add(
                        CustomerChannelIdentity(
                            customer_id=customer.id,
                            channel="facebook",
                            channel_account_id="",
                            external_user_id=psid,
                            display_name=customer.name,
                            is_verified=True,
                        )
                    )
                    backfilled += 1

        db.session.commit()
        print(f"Omnichannel migration complete. Backfilled identities: {backfilled}")


if __name__ == "__main__":
    run_omnichannel_migration()
