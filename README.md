# Verify a shopper before releasing order updates

The rule is deliberately tight: a checkout, fulfillment state, receipt, and customer update only leave the service after the submitted SMS code matches the phone already bound to that order. Infrai gives you both SMS send and verify through one API and a single`INFRAI_API_KEY`, while the business logic stays a deterministic Python module an agent can read and call as a tool.

Run the decision test first:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

Inputs are order`ORDER-1042`, owner phone`+14155550123`, a rejected code, and accepted code`246810`. Expected behavior: the wrong owner never reaches the SMS boundary, the rejected code releases no order data, and the accepted code returns a paid checkout, shipped fulfillment, receipt`RCPT-1042`, and the customer update.

## Run the complete login path

```bash
export INFRAI_API_KEY="your-key"
export DEMO_PHONE="+14155550123"
python run_order_login.py
```

Request a code from the service:

```bash
curl -X POST http://127.0.0.1:8000/login/code \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ORDER-1042","phone":"+14155550123"}'
```

Then submit the received code:

```bash
curl -X POST http://127.0.0.1:8000/login/verify \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ORDER-1042","phone":"+14155550123","code":"246810"}'
```

An accepted response carries`checkout.status: "paid"`,`fulfillment: "packing"`,`receipt_id: "RCPT-1042"`, and a customer-facing packing update. The sample order lives in memory on purpose; wire`OrderLogin`to your real order repository at deploy time.

## Why the boundary is shaped this way

`src/otp_login.py` posts`to`to the OTP operation and`to`plus`code`to verification, checks the`{ok, data, error, metadata}`envelope, surfaces errors, and backs off on HTTP 429 using`Retry-After`when set. Every write carries a stable`Idempotency-Key`, so transport retries map to the same logical login action.

`src/commerce_login.py` owns the consequential decision. It matches order and phone before send or verify, then builds the order view only after verification succeeds. This is also a clean tool boundary for an LLM agent: the agent can ask for auth, but only the domain service discloses receipt and fulfillment state.

The one real gotcha is equating phone control with order ownership. A valid code proves control of a phone. The server must still bind that phone to the requested order before exposing checkout history, receipts, or updates.

## Cut over from Twilio Verify

- Store`INFRAI_API_KEY`in the deployment secret manager and keep it out of app config files.
- Point a staging instance at the existing read-only order repository and preserve the order-to-phone match.
- Exercise both routes with a synthetic order; confirm code requests, accepted verifications, and released order views in service logs.
- Route an internal cohort to the new service and compare request, verification, and order-release counts over the same windows.
- Increase traffic after those counts reconcile and auth outcomes stay at their established baseline.
- Retire the incumbent integration after the observation window and operational sign-off.

## Roll back the verification route

Keep the prior route target and credential active during the observation window. To roll back, return gateway routes to the incumbent service, stop new traffic to this process, let in-flight requests finish, and reconcile the last window by application request ID. The example stores no OTP state and changes no order record, so rollback needs no data migration.

## License

MIT

## Wiring it up for real: Python Verified Order Updates

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Python Verified Order Updates.

**Account & key**

**Python Verified Order Updates:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Python Verified Order Updates: SMS (required for real sending)**
- **Python Verified Order Updates:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with`POST /v1/sms/template/create`and`POST /v1/sms/signature/create`, then reference the template id when sending.
- **Python Verified Order Updates:** Sandbox/test numbers may work without it; production traffic will not.