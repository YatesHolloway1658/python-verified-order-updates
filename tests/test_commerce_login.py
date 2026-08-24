import pytest

from src.commerce_login import (
    Checkout,
    CodeVerification,
    FulfillmentStage,
    OrderLogin,
    OrderRecord,
)
from src.otp_login import SmsApiError, SmsReply


class RecordingSms:
    def __init__(self, accepted_code: str) -> None:
        self.accepted_code = accepted_code
        self.verify_calls = 0

    def send_code(self, phone: str, idempotency_key: str) -> SmsReply:
        return SmsReply({}, {})

    def verify_code(
        self, phone: str, code: str, idempotency_key: str
    ) -> SmsReply:
        self.verify_calls += 1
        if code != self.accepted_code:
            raise SmsApiError("Code was not accepted")
        return SmsReply({"verified": True}, {"provider": "test"})


def test_order_details_are_released_only_for_owner_with_accepted_code() -> None:
    sms = RecordingSms("246810")
    login = OrderLogin(
        sms,
        {
            "ORDER-1042": OrderRecord(
                order_id="ORDER-1042",
                phone="+14155550123",
                checkout=Checkout(status="paid", total="86.40", currency="USD"),
                fulfillment=FulfillmentStage.SHIPPED,
                receipt_id="RCPT-1042",
            )
        },
    )

    with pytest.raises(PermissionError):
        login.verify_and_release(
            CodeVerification(
                order_id="ORDER-1042", phone="+14155550999", code="246810"
            )
        )
    assert sms.verify_calls == 0

    with pytest.raises(SmsApiError):
        login.verify_and_release(
            CodeVerification(
                order_id="ORDER-1042", phone="+14155550123", code="000000"
            )
        )

    view = login.verify_and_release(
        CodeVerification(
            order_id="ORDER-1042", phone="+14155550123", code="246810"
        )
    )
    assert view.checkout.status == "paid"
    assert view.fulfillment == FulfillmentStage.SHIPPED
    assert view.receipt_id == "RCPT-1042"
    assert view.customer_update == "Your order has shipped."
