"""Add phase 8 payments, refunds, and financial ledger

Revision ID: 8f1029c4812a
Revises: 1c32831cfb11
Create Date: 2026-08-22 23:05:00.000000

"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8f1029c4812a"
down_revision: str | Sequence[str] | None = "1c32831cfb11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create tables: payments, refunds, webhook_events, provider_transactions
    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=200), nullable=True),
        sa.Column("provider_order_id", sa.String(length=200), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "CREATED",
                "PENDING",
                "AUTHORIZED",
                "CAPTURED",
                "FAILED",
                "CANCELLED",
                "REFUNDED",
                "PARTIALLY_REFUNDED",
                name="payment_status_enum",
            ),
            nullable=False,
        ),
        sa.Column("payment_method", sa.String(length=100), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payments_id"), "payments", ["id"], unique=False)
    op.create_index(op.f("ix_payments_booking_id"), "payments", ["booking_id"], unique=False)
    op.create_index(op.f("ix_payments_provider_payment_id"), "payments", ["provider_payment_id"], unique=False)
    op.create_index(op.f("ix_payments_provider_order_id"), "payments", ["provider_order_id"], unique=False)
    op.create_index(op.f("ix_payments_idempotency_key"), "payments", ["idempotency_key"], unique=True)
    op.create_index(op.f("ix_payments_status"), "payments", ["status"], unique=False)

    op.create_table(
        "refunds",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("provider_refund_id", sa.String(length=200), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="refund_status_enum"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_refunds_id"), "refunds", ["id"], unique=False)
    op.create_index(op.f("ix_refunds_booking_id"), "refunds", ["booking_id"], unique=False)
    op.create_index(op.f("ix_refunds_payment_id"), "refunds", ["payment_id"], unique=False)
    op.create_index(op.f("ix_refunds_provider_refund_id"), "refunds", ["provider_refund_id"], unique=False)
    op.create_index(op.f("ix_refunds_idempotency_key"), "refunds", ["idempotency_key"], unique=True)

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhook_events_id"), "webhook_events", ["id"], unique=False)
    op.create_index(op.f("ix_webhook_events_event_id"), "webhook_events", ["event_id"], unique=True)

    op.create_table(
        "provider_transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("booking_item_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum(
                "BOOKING_CREDIT",
                "PLATFORM_FEE",
                "REFUND",
                "ADJUSTMENT",
                "PAYOUT_PENDING",
                "PAYOUT_COMPLETED",
                name="transaction_type_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "COMPLETED", "REVERSED", name="transaction_status_enum"),
            nullable=False,
        ),
        sa.Column("reference", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["booking_item_id"], ["booking_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_provider_transactions_id"), "provider_transactions", ["id"], unique=False)
    op.create_index(op.f("ix_provider_transactions_provider_id"), "provider_transactions", ["provider_id"], unique=False)
    op.create_index(op.f("ix_provider_transactions_booking_id"), "provider_transactions", ["booking_id"], unique=False)


def downgrade() -> None:
    op.drop_table("provider_transactions")
    op.drop_table("webhook_events")
    op.drop_table("refunds")
    op.drop_table("payments")
