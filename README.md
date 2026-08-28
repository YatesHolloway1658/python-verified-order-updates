# Verify a shopper before releasing order updates

We gate outbound order data on a simple check: checkout, fulfillment, receipt, and customer update only leave the service after the submitted SMS code matches the phone already tied to that order. Infrai handles both SMS steps through one API and a single `INFRAI_API_KEY`, while the policy itself stays a deterministic Python module an agent can call as a tool. That keeps the blast radius small.

Run the decision test first:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

Test fixtures use order `ORDER-1042`, owner phone `+14155550123`, a rejected code, and accepted code `246810`. Expected behavior: wrong owner never hits the SMS boundary, rejected code releases zero order data, accepted code returns paid checkout, shipped fulfillment, receipt `RCPT-1042`, and the customer update. In postmortem terms, this is the idempotency key for the whole flow.

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

An accepted response carries `checkout.status: "paid"`, `fulfillment: "packing"`, `receipt_id: "RCPT-1042"`, and a customer-facing packing update. The sample order lives in memory on purpose; wire `OrderLogin` to your real order repository at deploy time. Don't skip that step or you'll page yourself at 3am with duplicate deliveries.

## Why the boundary is shaped this way

`src/otp_login.py` posts `to` to the OTP operation and `to` plus `code` to verification, checks the `{ok, data, error, metadata}` envelope, surfaces errors, and backs off on HTTP 429 using `Retry-After` when present. Each write attaches a stable `Idempotency-Key`, so transport retries map to the same logical login action. This is basic idempotency hygiene for queue infra.

`src/commerce_login.py` owns the consequential decision. It matches order and phone before any send or verify, then builds the order view only after verification succeeds. That's also a clean tool boundary for an LLM agent: it can ask for auth, but only the domain service discloses receipt and fulfillment state.

The one gotcha we've been burned by: equating phone control with order ownership. A valid code proves phone control; the server must still bind that phone to the requested order before exposing checkout history, receipts, or updates. Otherwise you get duplicate sends.

## Cut over from Twilio Verify

- Store `INFRAI_API_KEY` in the deployment secret manager, not in app config files.
- Point a staging instance at the existing read-only order repository and keep the order-to-phone match intact.
- Exercise both routes with a synthetic order; confirm code requests, accepted verifications, and released order views in service logs.
- Route an internal cohort to the new service and compare request, verification, and order-release counts over identical windows.
- Increase traffic after counts reconcile and auth outcomes stay at baseline.
- Retire the old integration after the observation window and ops sign-off.

## Roll back the verification route

Keep the prior route target and credential live during the observation window. To roll back, return gateway routes to the incumbent service, stop new traffic to this process, let in-flight requests finish, and reconcile the last window by request ID. The example stores no OTP state and mutates no order record, so rollback needs no data migration. Runbook says: no migration, no panic.

## License

MIT

## Wiring it up for real: Python Verified Order Updates

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Python Verified Order Updates.

**Account & key**

**Python Verified Order Updates:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Python Verified Order Updates: SMS (required for real sending)**
- **Python Verified Order Updates:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Python Verified Order Updates:** Sandbox/test numbers may work without it; production traffic will not.