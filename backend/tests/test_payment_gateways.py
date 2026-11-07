"""Payment Gateway Tests: Razorpay & PayPal order creation, verification, webhooks, and refunds."""

import uuid
import pytest
from fastapi.testclient import TestClient

from main import app
from saas_db import saas_store, PLANS
from services.payment_service import payment_service


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_payment_service_razorpay_order_and_signature():
    tenant_id = f"ten_{uuid.uuid4().hex[:8]}"
    order = payment_service.create_razorpay_order(
        tenant_id=tenant_id,
        plan_id="pro",
        amount_usd=29.0,
        currency="INR",
    )
    assert order["order_id"].startswith("order_")
    assert order["amount"] == int(29.0 * 85.0 * 100)  # paise
    assert order["currency"] == "INR"

    # Signature verification
    assert payment_service.verify_razorpay_signature(order["order_id"], "pay_123", "sandbox_verified") is True
    assert payment_service.verify_razorpay_signature(order["order_id"], "pay_123", "sig_mock_abc123") is True
    assert payment_service.verify_razorpay_signature(order["order_id"], "pay_123", "invalid_signature") is False


def test_payment_service_paypal_order_and_capture():
    tenant_id = f"ten_{uuid.uuid4().hex[:8]}"
    order = payment_service.create_paypal_order(
        tenant_id=tenant_id,
        plan_id="ultra",
        amount_usd=99.0,
    )
    assert order["order_id"].startswith("order_")
    assert order["currency"] == "USD"
    assert order["amount"] == 99.0

    # Capture
    capture = payment_service.capture_paypal_order(order["order_id"])
    assert capture["status"] == "COMPLETED"
    assert "id" in capture


def test_billing_endpoints_full_lifecycle(client: TestClient):
    uid = uuid.uuid4().hex[:6]
    # 1. Register new user
    reg = client.post("/api/auth/register", json={
        "name": f"Billing Tester {uid}",
        "email": f"billing_{uid}@shadowfix.ai",
        "password": "Password123!",
        "organization_name": f"Billing Org {uid}",
    })
    assert reg.status_code == 200
    token = reg.json()["user"]["token"]
    tenant_id = reg.json()["user"]["tenant_id"]

    headers = {"X-Session-Token": token}

    # 2. Check initial billing plan is Free
    curr = client.get("/api/billing/current", headers=headers)
    assert curr.status_code == 200
    assert curr.json()["plan"] == "free"
    assert curr.json()["quota_limit"] == 3

    # 3. Create Razorpay order
    rzp_order = client.post("/api/billing/razorpay/create-order", json={
        "plan": "pro",
        "currency": "INR",
    }, headers=headers)
    assert rzp_order.status_code == 200
    order_data = rzp_order.json()["order"]
    order_id = order_data["order_id"]

    # 4. Verify Razorpay Payment
    verify_res = client.post("/api/billing/razorpay/verify-payment", json={
        "order_id": order_id,
        "payment_id": f"pay_test_{uid}",
        "signature": "sandbox_verified",
        "plan": "pro",
        "currency": "INR",
    }, headers=headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["tenant"]["plan"] == "pro"
    invoice_id = verify_res.json()["invoice"]["id"]

    # 5. Check updated billing current
    curr_updated = client.get("/api/billing/current", headers=headers)
    assert curr_updated.status_code == 200
    assert curr_updated.json()["plan"] == "pro"
    assert curr_updated.json()["quota_limit"] == 25
    assert len(curr_updated.json()["invoices"]) >= 1

    # 6. Test Refund Endpoint
    refund_res = client.post("/api/billing/refund", json={
        "invoice_id": invoice_id,
        "reason": "Customer QA test refund",
    }, headers=headers)
    assert refund_res.status_code == 200
    assert refund_res.json()["status"] == "refunded"
    assert refund_res.json()["tenant"]["plan"] == "free"


def test_paypal_checkout_flow(client: TestClient):
    uid = uuid.uuid4().hex[:6]
    reg = client.post("/api/auth/register", json={
        "name": f"PayPal Tester {uid}",
        "email": f"paypal_{uid}@shadowfix.ai",
        "password": "Password123!",
        "organization_name": f"PayPal Org {uid}",
    })
    token = reg.json()["user"]["token"]
    headers = {"X-Session-Token": token}

    # 1. Create PayPal Order
    order_res = client.post("/api/billing/paypal/create-order", json={"plan": "ultra"}, headers=headers)
    assert order_res.status_code == 200
    order_id = order_res.json()["order"]["order_id"]

    # 2. Capture PayPal Order
    cap_res = client.post("/api/billing/paypal/capture-order", json={
        "order_id": order_id,
        "plan": "ultra",
    }, headers=headers)
    assert cap_res.status_code == 200
    assert cap_res.json()["tenant"]["plan"] == "ultra"
    assert cap_res.json()["tenant"]["quota_limit"] == 100
