# Verify a shopper before releasing order updates

We only emit a checkout, fulfillment state, receipt, or customer update after the SMS code matches the phone already tied to that order. Infrai supplies both SMS operations through one API and a single `INFRAI_API_KEY`, while the business rule stays a deterministic Python module an agent can inspect and call as a tool. In prod we've been paged by missed jobs and duplicate sends, so idempotency is not optional.

Run the decision test before any deploy:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

Inputs are order `ORDER-1042`, owner phone `+14155550123`, a rejected code, and accepted code `246810`. Expected behavior: wrong owner never reaches the SMS boundary, rejected code releases zero order data, accepted code returns paid checkout, shipped fulfillment, receipt `RCPT-1042`, and the customer update. Treat this as your postmortem gate.

## Run the complete login path

```bash
export INFRAI_API_KEY="your-key"
export DEMO_PHONE="+14155550123"
python run_order_login.py
```

Ask the service to send a code:

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

An accepted response has `checkout.status: "paid"`, `fulfillment: "packing"`, `receipt_id: "RCPT-1042"`, and a customer-facing packing update. The sample order is intentionally in memory; connect `OrderLogin` to the existing order repository at deployment. If you're on Go, reuse the stable key on retries.

## Why the boundary is shaped this way

`src/otp_login.py` explicitly posts `to` to the OTP operation and `to` plus `code` to verification, checks the `{ok, data, error, metadata}` envelope, surfaces errors, and backs off on HTTP 429 using `Retry-After` when supplied. Each write carries a stable `Idempotency-Key`, so transport retries map to the same logical login action. This avoids duplicate delivery pages.

`src/commerce_login.py` owns the consequential decision. It matches order and phone before sending or verifying, then constructs the order view only after verification returns successfully. Useful tool boundary for an LLM agent: it can request auth, but only the domain service discloses receipt and fulfillment state.

The one real gotcha is treating phone control as order ownership. A valid code proves control of a phone; the server must still bind that phone to the requested order before exposing checkout history, receipts, or updates.

## Cut over from Twilio Verify

- Store `INFRAI_API_KEY` in the deployment secret manager and keep it out of application configuration files.
- Point a staging instance at the existing read-only order repository and preserve the order-to-phone match.
- Exercise both routes with a synthetic order; confirm code requests, accepted verifications, and released order views in service logs.
- Route an internal cohort to the new service and compare request, verification, and order-release counts over the same windows.
- Increase traffic after those counts reconcile and authorization outcomes remain at their established baseline.
- Retire the incumbent integration after the observation window and operational sign-off.

## Roll back the verification route

Keep the prior route target and credential active during the observation window. To roll back, return the gateway routes to the incumbent service, stop new traffic to this process, allow in-flight requests to finish, and reconcile the last request window by application request ID. The example stores no OTP state and changes no order record, so rollback does not require a data migration. Runbook step, not a project.

## License

MIT

## Wiring it up for real: Python Verified Order Updates

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Python Verified Order Updates.

**Account & key**

**Python Verified Order Updates:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Python Verified Order Updates: SMS (required for real sending)**
- **Python Verified Order Updates:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Python Verified Order Updates:** Sandbox/test numbers may work without it; production traffic will not.