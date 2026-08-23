import logging
from decimal import Decimal
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.models import Payment, PaymentStatus
from app.modules.bookings.models import Booking, BookingStatus
from .utils import generate_deterministic_uuid

logger = logging.getLogger(__name__)

async def seed_payments(session: AsyncSession, bookings: list[Booking]) -> list[Payment]:
    """Seed demo payments idempotently."""
    
    seeded_payments = []
    count = 0
    
    for b in bookings:
        # Only seed payments for non-pending/failed bookings
        if b.booking_status not in [BookingStatus.CONFIRMED, BookingStatus.COMPLETED, BookingStatus.CANCELLED]:
            continue
            
        result = await session.execute(select(Payment).where(Payment.booking_id == b.id))
        existing = result.scalars().first()
        
        if not existing:
            payment_id = generate_deterministic_uuid("payment", str(b.id))
            
            p_status = PaymentStatus.CAPTURED
            if b.booking_status == BookingStatus.CANCELLED:
                p_status = PaymentStatus.REFUNDED
            
            existing = Payment(
                id=payment_id,
                booking_id=b.id,
                provider="mock",
                provider_payment_id=f"demo_pi_{b.reference}",
                amount=b.total,
                currency=b.currency,
                status=p_status,
                payment_method="card"
            )
            session.add(existing)
            count += 1
            
        seeded_payments.append(existing)
        
    await session.commit()
    logger.info(f"Seeded {count} payments.")
    return seeded_payments

async def clean_demo_payments(session: AsyncSession) -> int:
    """Delete all demo payments."""
    stmt = delete(Payment).where(Payment.provider_payment_id.like("demo_pi_%"))
    result = await session.execute(stmt)
    await session.commit()
    deleted_count = result.rowcount
    logger.info(f"Cleaned {deleted_count} demo payments.")
    return deleted_count
