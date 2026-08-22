import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.deps import SessionDep, get_current_user
from app.modules.payments.schemas import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentRead,
    PaymentVerifyRequest,
    RefundCreateRequest,
    RefundRead,
)
from app.modules.payments.service import PaymentService
from app.modules.users.models import User

router = APIRouter(tags=["Payments"])


@router.post(
    "/create",
    response_model=PaymentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a payment order/intent for a booking",
)
async def create_payment(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
    request_in: PaymentCreateRequest,
):
    return await PaymentService.create_payment(
        session=session,
        booking_id=request_in.booking_id,
        user_id=current_user.id,
        idempotency_key=request_in.idempotency_key,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentRead,
    summary="Get payment details",
)
async def get_payment(
    payment_id: uuid.UUID,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await PaymentService.get_payment(
        session=session,
        payment_id=payment_id,
        user_id=current_user.id,
    )


@router.post(
    "/{payment_id}/verify",
    response_model=PaymentRead,
    summary="Verify payment signature after checkout",
)
async def verify_payment(
    payment_id: uuid.UUID,
    verify_in: PaymentVerifyRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await PaymentService.verify_payment(
        session=session,
        payment_id=payment_id,
        provider_payment_id=verify_in.provider_payment_id,
        provider_order_id=verify_in.provider_order_id,
        provider_signature=verify_in.provider_signature,
        user_id=current_user.id,
    )


@router.post(
    "/{payment_id}/refund",
    response_model=RefundRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a refund for a payment",
)
async def create_refund(
    payment_id: uuid.UUID,
    refund_in: RefundCreateRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    # Verify user owns the payment/booking
    await PaymentService.get_payment(
        session=session,
        payment_id=payment_id,
        user_id=current_user.id,
    )
    return await PaymentService.create_refund(
        session=session,
        payment_id=payment_id,
        amount=refund_in.amount,
        reason=refund_in.reason,
        idempotency_key=refund_in.idempotency_key,
    )


@router.post(
    "/webhooks/razorpay",
    status_code=status.HTTP_200_OK,
    summary="Razorpay webhook listener",
)
async def razorpay_webhook(
    request: Request,
    session: SessionDep,
    x_razorpay_signature: Annotated[str | None, Header()] = None,
):
    body = await request.body()
    signature = x_razorpay_signature or ""
    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body"
        )

    await PaymentService.process_webhook(
        session=session,
        provider="razorpay",
        payload=payload,
        signature=signature,
        body=body,
    )
    return {"status": "ok"}


@router.post(
    "/webhooks/stripe",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook listener",
)
async def stripe_webhook(
    request: Request,
    session: SessionDep,
    stripe_signature: Annotated[str | None, Header()] = None,
):
    body = await request.body()
    signature = stripe_signature or ""
    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body"
        )

    await PaymentService.process_webhook(
        session=session,
        provider="stripe",
        payload=payload,
        signature=signature,
        body=body,
    )
    return {"status": "ok"}
