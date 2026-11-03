"""Separate platform-credit and real-payment ledgers. Never touches virtual funds."""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import re
import time
import uuid
import requests
from .identity import IdentityError

PLANS = {
    "free": {"name": "Free", "features": ["Synthetic research", "Paper practice", "Journal"]},
    "trader": {"name": "Trader", "features": ["Saved workspaces", "Extended research quotas"]},
    "pro": {"name": "Pro", "features": ["Strategy versions", "Historical research quotas", "AI quotas"]},
    "professional": {"name": "Professional", "features": ["Higher quotas", "Exports", "Priority operational support"]},
}


class SandboxPayments:
    """Razorpay test-mode transport. No live keys or automatic production activation."""
    def __init__(self):
        self.key = os.environ.get("ALGOOPTIONX_PAYMENT_KEY_ID", "")
        self.secret = os.environ.get("ALGOOPTIONX_PAYMENT_KEY_SECRET", "")
        self.webhook_secret = os.environ.get("ALGOOPTIONX_PAYMENT_WEBHOOK_SECRET", "")
        self.enabled = os.environ.get("ALGOOPTIONX_BILLING_ENABLED") == "1"

    @property
    def configured(self):
        return self.enabled and self.key.startswith("rzp_test_") and bool(self.secret) and bool(self.webhook_secret)

    def call(self, method: str, path: str, body=None):
        if not self.configured:
            raise IdentityError("Sandbox payments are not configured. No payment was initiated.", 503)
        try:
            response = requests.request(method, "https://api.razorpay.com/v1/" + path, json=body,
                                        auth=(self.key, self.secret), timeout=10, allow_redirects=False)
            if response.status_code < 200 or response.status_code >= 300:
                raise IdentityError("The payment provider could not complete this request.", 502)
            return response.json()
        except (requests.RequestException, ValueError):
            raise IdentityError("The payment provider is unavailable. Retry after checking payment status.", 503) from None


class Commerce:
    def __init__(self, identity, provider=None, catalog=None):
        self.identity = identity
        self.provider = provider or SandboxPayments()
        try:
            self.catalog = catalog if catalog is not None else json.loads(os.environ.get("ALGOOPTIONX_BILLING_CATALOG", "{}"))
        except ValueError:
            self.catalog = {}
        if not isinstance(self.catalog, dict):
            self.catalog = {}
        with identity.tx() as c:
            for statement in (
                "CREATE TABLE IF NOT EXISTS billing_subscriptions(tenant_id TEXT PRIMARY KEY REFERENCES tenants(id),plan TEXT NOT NULL,status TEXT NOT NULL,period_end INTEGER,provider_subscription TEXT,updated_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS credit_accounts(tenant_id TEXT PRIMARY KEY REFERENCES tenants(id),balance INTEGER NOT NULL DEFAULT 0)",
                "CREATE TABLE IF NOT EXISTS credit_transactions(id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL REFERENCES tenants(id),reference TEXT UNIQUE NOT NULL,kind TEXT NOT NULL,created_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS credit_postings(transaction_id TEXT NOT NULL REFERENCES credit_transactions(id),account TEXT NOT NULL,units INTEGER NOT NULL,PRIMARY KEY(transaction_id,account))",
                "CREATE TABLE IF NOT EXISTS billing_intents(id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL REFERENCES tenants(id),request_key TEXT NOT NULL,plan TEXT NOT NULL,amount INTEGER NOT NULL,credits INTEGER NOT NULL,provider_order TEXT UNIQUE,status TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(tenant_id,request_key))",
                "CREATE TABLE IF NOT EXISTS payment_transactions(id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL REFERENCES tenants(id),intent_id TEXT NOT NULL REFERENCES billing_intents(id),provider_payment TEXT UNIQUE NOT NULL,amount INTEGER NOT NULL,refunded INTEGER NOT NULL DEFAULT 0,credits_reversed INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS billing_periods(id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL REFERENCES tenants(id),payment_id TEXT UNIQUE NOT NULL REFERENCES payment_transactions(id),plan TEXT NOT NULL,starts_at INTEGER NOT NULL,ends_at INTEGER NOT NULL,status TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS payment_refunds(id TEXT PRIMARY KEY,provider_payment TEXT NOT NULL REFERENCES payment_transactions(provider_payment),amount INTEGER NOT NULL,created_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS payment_postings(reference TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL,currency TEXT NOT NULL CHECK(currency='INR'),PRIMARY KEY(reference,account))",
                "CREATE TABLE IF NOT EXISTS billing_webhooks(id TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,event TEXT NOT NULL,status TEXT NOT NULL,created_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS billing_receipts(id TEXT PRIMARY KEY,payment_id TEXT UNIQUE NOT NULL REFERENCES payment_transactions(id),tenant_id TEXT NOT NULL REFERENCES tenants(id),amount INTEGER NOT NULL,currency TEXT NOT NULL,created_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS usage_reservations(id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL REFERENCES tenants(id),request_key TEXT NOT NULL,feature TEXT NOT NULL,reserved INTEGER NOT NULL,used INTEGER,status TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(tenant_id,request_key))",
            ):
                c.execute(statement)

    def ensure(self, c, tenant_id):
        c.execute("INSERT OR IGNORE INTO credit_accounts VALUES(?,0)", (tenant_id,))
        c.execute("INSERT OR IGNORE INTO billing_subscriptions VALUES(?,'free','active',NULL,NULL,?)", (tenant_id, int(time.time())))

    def pricing(self):
        plans = []
        for key, plan in PLANS.items():
            price = self.catalog.get(key, {})
            if not isinstance(price, dict):
                price = {}
            amount = price.get("amount_paise")
            credits = price.get("credits")
            approved = type(amount) is int and amount > 0 and type(credits) is int and credits >= 0
            plans.append({"id": key, **plan, "amount_paise": amount if approved else None,
                          "credits": credits if approved else None, "checkout_available": approved and self.provider.configured})
        return {"plans": plans, "currency": "INR", "mode": "sandbox", "payments_configured": self.provider.configured,
                "notice": "Prices require explicit approval and configured sandbox credentials. No live payments or automatic renewals are enabled."}

    def snapshot(self, tenant_id):
        with self.identity.tx() as c:
            self.ensure(c, tenant_id)
            self.refresh_subscription(c, tenant_id)
            subscription = dict(c.execute("SELECT plan,status,period_end,updated_at FROM billing_subscriptions WHERE tenant_id=?", (tenant_id,)).fetchone())
            if subscription["period_end"] and subscription["period_end"] <= int(time.time()):
                subscription["status"] = "expired"
            credits = c.execute("SELECT balance FROM credit_accounts WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
            receipts = [dict(row) for row in c.execute("SELECT id,amount,currency,created_at FROM billing_receipts WHERE tenant_id=? ORDER BY created_at DESC LIMIT 100", (tenant_id,))]
            entries = [dict(row) for row in c.execute("SELECT t.kind,t.created_at,p.units FROM credit_transactions t JOIN credit_postings p ON p.transaction_id=t.id WHERE t.tenant_id=? AND p.account=? ORDER BY t.created_at DESC LIMIT 100", (tenant_id, tenant_id))]
        return {"subscription": subscription, "credits": credits, "receipts": receipts, "credit_history": entries,
                "mode": "sandbox", "notice": "Usage credits are separate from virtual trading capital and real payment receipts."}

    def credit(self, c, tenant_id, reference, kind, units):
        if type(units) is not int:
            raise IdentityError("Credit units must be integers.")
        self.ensure(c, tenant_id)
        previous = c.execute("SELECT t.id,t.tenant_id,t.kind,p.units FROM credit_transactions t JOIN credit_postings p ON p.transaction_id=t.id AND p.account=t.tenant_id WHERE t.reference=?", (reference,)).fetchone()
        if previous:
            if previous["tenant_id"] != tenant_id or previous["kind"] != kind or previous["units"] != units:
                raise IdentityError("Credit reference conflicts with recorded history.", 409)
            return previous["id"]
        transaction_id = uuid.uuid4().hex
        c.execute("INSERT INTO credit_transactions VALUES(?,?,?,?,?)", (transaction_id, tenant_id, reference, kind, int(time.time())))
        c.executemany("INSERT INTO credit_postings VALUES(?,?,?)", [(transaction_id, tenant_id, units), (transaction_id, "platform", -units)])
        c.execute("UPDATE credit_accounts SET balance=balance+? WHERE tenant_id=?", (units, tenant_id))
        return transaction_id

    def checkout(self, tenant_id, plan, request_key):
        if plan not in PLANS or plan == "free":
            raise IdentityError("Select a configured paid plan.", 422)
        price = self.catalog.get(plan, {})
        if not isinstance(price, dict):
            price = {}
        amount, credits = price.get("amount_paise"), price.get("credits")
        if type(amount) is not int or not 0 < amount <= 100_000_000 or type(credits) is not int or not 0 <= credits <= 1_000_000_000:
            raise IdentityError("Pricing has not been approved/configured for this plan.", 503)
        if not self.provider.configured:
            raise IdentityError("Sandbox payments are not configured. No payment was initiated.", 503)
        with self.identity.tx() as c:
            self.ensure(c, tenant_id)
            existing = c.execute("SELECT * FROM billing_intents WHERE tenant_id=? AND request_key=?", (tenant_id, request_key)).fetchone()
            if existing:
                if existing["plan"] != plan:
                    raise IdentityError("This checkout key was already used for another plan.", 409)
                if existing["provider_order"]:
                    return {"intent_id": existing["id"], "provider_order": existing["provider_order"], "amount_paise": existing["amount"], "currency": "INR", "key_id": self.provider.key, "mode": "sandbox"}
                raise IdentityError("Checkout status is uncertain. Reconcile this attempt before retrying.", 409)
            pending = c.execute("SELECT id FROM billing_intents WHERE tenant_id=? AND status IN ('creating','pending')", (tenant_id,)).fetchone()
            if pending:
                raise IdentityError("Finish or reconcile the existing checkout before creating another.", 409)
            other_plan = c.execute("SELECT id FROM billing_periods WHERE tenant_id=? AND status='active' AND ends_at>? AND plan!=?", (tenant_id, int(time.time()), plan)).fetchone()
            if other_plan:
                raise IdentityError("A plan change needs an approved proration policy. The existing paid term is preserved.", 409)
            intent_id = uuid.uuid4().hex
            c.execute("INSERT INTO billing_intents VALUES(?,?,?,?,?,?,NULL,'creating',?)", (intent_id, tenant_id, request_key, plan, amount, credits, int(time.time())))
        # Persist intent before outbound side effects. Unknown outcomes are never blindly retried.
        result = self.provider.call("POST", "orders", {"amount": amount, "currency": "INR", "receipt": intent_id})
        if not isinstance(result, dict):
            raise IdentityError("Payment-provider response is invalid.",502)
        order_id = result.get("id")
        if not isinstance(order_id, str) or not re.fullmatch(r"order_[A-Za-z0-9]+", order_id) or type(result.get("amount")) is not int or result.get("amount") != amount or result.get("currency") != "INR":
            raise IdentityError("Payment-provider response did not match the checkout.", 502)
        with self.identity.tx() as c:
            c.execute("UPDATE billing_intents SET provider_order=?,status='pending' WHERE id=? AND status='creating'", (order_id, intent_id))
        return {"intent_id": intent_id, "provider_order": order_id, "amount_paise": amount, "currency": "INR", "key_id": self.provider.key, "mode": "sandbox"}

    def reconcile_checkout(self, tenant_id, intent_id):
        """Read provider status; grant economics only for a verified capture."""
        if not self.provider.configured:
            raise IdentityError("Sandbox payments are not configured.",503)
        with self.identity.tx() as c:
            intent = c.execute('SELECT * FROM billing_intents WHERE id=? AND tenant_id=?',(intent_id,tenant_id)).fetchone()
            if not intent:
                raise IdentityError("Checkout not found.",404)
            if not intent['provider_order']:
                raise IdentityError("Order creation has an uncertain outcome. Reconcile its receipt in the provider dashboard; a duplicate order was not created.",409)
            order_id = intent['provider_order']
        order = self.provider.call('GET','orders/'+order_id)
        payments = self.provider.call('GET','orders/'+order_id+'/payments')
        if not isinstance(order,dict) or order.get('id')!=order_id or type(order.get('amount')) is not int or order['amount']!=intent['amount'] or order.get('currency')!='INR' or not isinstance(payments,dict) or not isinstance(payments.get('items'),list):
            raise IdentityError("Provider status does not match the recorded checkout.",502)
        captured = [item for item in payments['items'] if isinstance(item,dict) and item.get('status')=='captured']
        if len(captured)>1:
            raise IdentityError("Multiple captured payments require operator reconciliation.",409)
        with self.identity.tx() as c:
            if captured:
                if captured[0].get('order_id')!=order_id:
                    raise IdentityError("Provider payment belongs to a different order.",502)
                self._capture(c,captured[0])
            status = c.execute('SELECT status FROM billing_intents WHERE id=? AND tenant_id=?',(intent_id,tenant_id)).fetchone()[0]
        return {'intent_id':intent_id,'status':status,'notice':'Only server-verified captures grant credits. Refunds are reconciled through signed provider webhooks.'}

    def _capture(self, c, payment):
        payment_id, order_id = payment.get("id"), payment.get("order_id")
        if not isinstance(payment_id, str) or not re.fullmatch(r"pay_[A-Za-z0-9]+", payment_id):
            raise IdentityError("Invalid provider payment identity.")
        intent = c.execute("SELECT * FROM billing_intents WHERE provider_order=?", (order_id,)).fetchone()
        if not intent:
            raise IdentityError("Payment awaits order reconciliation.", 409)
        if payment.get("status") != "captured" or type(payment.get("amount")) is not int or payment["amount"] != intent["amount"] or payment.get("currency") != "INR":
            raise IdentityError("Payment details do not match the approved checkout.", 409)
        existing = c.execute("SELECT * FROM payment_transactions WHERE provider_payment=?", (payment_id,)).fetchone()
        if existing:
            if existing["intent_id"] != intent["id"] or existing["amount"] != intent["amount"]:
                raise IdentityError("Payment identity conflicts with recorded history.", 409)
            return
        if intent["status"] == "paid":
            raise IdentityError("This checkout already has a captured payment. Reconcile the additional payment.", 409)
        now, transaction_id = int(time.time()), uuid.uuid4().hex
        c.execute("INSERT INTO payment_transactions VALUES(?,?,?,?,?,0,0,?)", (transaction_id, intent["tenant_id"], intent["id"], payment_id, intent["amount"], now))
        c.executemany("INSERT INTO payment_postings VALUES(?,?,?,'INR')", [(payment_id, "provider_receivable", intent["amount"]), (payment_id, "deferred_platform_revenue", -intent["amount"])])
        self.credit(c, intent["tenant_id"], "purchase:" + payment_id, "PURCHASE", intent["credits"])
        c.execute("UPDATE billing_intents SET status='paid' WHERE id=?", (intent["id"],))
        latest = c.execute("SELECT plan,MAX(ends_at) ends_at FROM billing_periods WHERE tenant_id=? AND status='active' AND ends_at>? GROUP BY plan", (intent["tenant_id"], now)).fetchall()
        if latest and any(row["plan"] != intent["plan"] for row in latest):
            raise IdentityError("Conflicting plan purchase requires payment reconciliation.", 409)
        start = max([now] + [row["ends_at"] for row in latest])
        c.execute("INSERT INTO billing_periods VALUES(?,?,?,?,?,?,'active')", (uuid.uuid4().hex, intent["tenant_id"], transaction_id, intent["plan"], start, start + 30 * 86400))
        self.refresh_subscription(c, intent["tenant_id"])
        c.execute("INSERT INTO billing_receipts VALUES(?,?,?,?,'INR',?)", (uuid.uuid4().hex, transaction_id, intent["tenant_id"], intent["amount"], now))

    def webhook(self, raw: bytes, signature: str):
        if not self.provider.configured or len(raw) > 65536 or not re.fullmatch(r"[a-f0-9]{64}", signature):
            raise IdentityError("Webhook authentication failed.", 401)
        expected = hmac.new(self.provider.webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise IdentityError("Webhook authentication failed.", 401)
        try:
            payload = json.loads(raw)
            kind = payload["event"]
            event_id = payload.get("id") or hashlib.sha256(raw).hexdigest()
            if not isinstance(event_id, str) or len(event_id) > 160 or not isinstance(kind, str):
                raise ValueError()
            payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        except (ValueError, KeyError, TypeError, AttributeError):
            raise IdentityError("Malformed payment webhook.", 422) from None
        payload_hash = hashlib.sha256(raw).hexdigest()
        with self.identity.tx() as c:
            previous = c.execute("SELECT payload_hash FROM billing_webhooks WHERE id=?", (event_id,)).fetchone()
            if previous:
                if previous[0] != payload_hash:
                    raise IdentityError("Webhook identity was reused with different content.", 409)
                return {"ok": True, "duplicate": True}
            if kind in {"payment.captured","payment.failed"} and not isinstance(payment,dict):
                raise IdentityError("Malformed payment entity.",422)
            if kind == "payment.captured":
                self._capture(c, payment)
            elif kind == "refund.processed":
                refund = payload.get("payload", {}).get("refund", {}).get("entity", {})
                self._refund(c, refund)
            elif kind == "payment.failed":
                c.execute("UPDATE billing_intents SET status='failed' WHERE provider_order=? AND status='pending'", (payment.get("order_id"),))
            c.execute("INSERT INTO billing_webhooks VALUES(?,?,?,'processed',?)", (event_id, payload_hash, kind, int(time.time())))
        return {"ok": True}

    def _refund(self, c, refund):
        if not isinstance(refund,dict):raise IdentityError("Malformed refund entity.",422)
        refund_id, payment_id, amount = refund.get("id"), refund.get("payment_id"), refund.get("amount")
        if not isinstance(refund_id, str) or not re.fullmatch(r"rfnd_[A-Za-z0-9]+", refund_id) or not isinstance(payment_id,str) or not re.fullmatch(r"pay_[A-Za-z0-9]+",payment_id) or type(amount) is not int or amount <= 0:
            raise IdentityError("Invalid refund details.", 422)
        previous = c.execute("SELECT provider_payment,amount FROM payment_refunds WHERE id=?", (refund_id,)).fetchone()
        if previous:
            if previous["provider_payment"] != payment_id or previous["amount"] != amount:
                raise IdentityError("Refund identity conflicts with recorded economics.", 409)
            return
        if c.execute("SELECT 1 FROM payment_postings WHERE reference=?", (refund_id,)).fetchone():
            raise IdentityError("Historical refund requires reconciliation before replay.", 409)
        payment = c.execute("SELECT p.*,i.credits FROM payment_transactions p JOIN billing_intents i ON i.id=p.intent_id WHERE p.provider_payment=?", (payment_id,)).fetchone()
        if not payment:
            raise IdentityError("Refund awaits captured-payment reconciliation.", 409)
        c.execute("INSERT INTO payment_refunds VALUES(?,?,?,?)", (refund_id, payment_id, amount, int(time.time())))
        total = payment["refunded"] + amount
        if total > payment["amount"]:
            raise IdentityError("Refund exceeds the captured payment.", 409)
        reversed_credits = payment["credits"] * total // payment["amount"]
        self.credit(c, payment["tenant_id"], "refund:" + refund_id, "REFUND", -(reversed_credits - payment["credits_reversed"]))
        c.execute("UPDATE payment_transactions SET refunded=?,credits_reversed=? WHERE id=?", (total, reversed_credits, payment["id"]))
        c.executemany("INSERT INTO payment_postings VALUES(?,?,?,'INR')", [(refund_id, "provider_receivable", -amount), (refund_id, "deferred_platform_revenue", amount)])
        if total == payment["amount"]:
            c.execute("UPDATE billing_periods SET status='refunded' WHERE payment_id=?", (payment["id"],))
        self.refresh_subscription(c, payment["tenant_id"])

    def refresh_subscription(self, c, tenant_id):
        now = int(time.time())
        active = c.execute("SELECT plan,ends_at FROM billing_periods WHERE tenant_id=? AND status='active' AND starts_at<=? AND ends_at>? ORDER BY starts_at DESC LIMIT 1", (tenant_id, now, now)).fetchone()
        future = c.execute("SELECT starts_at FROM billing_periods WHERE tenant_id=? AND status='active' AND starts_at>? ORDER BY starts_at LIMIT 1", (tenant_id, now)).fetchone()
        balance = c.execute("SELECT balance FROM credit_accounts WHERE tenant_id=?", (tenant_id,)).fetchone()
        status = "past_due" if balance and balance[0] < 0 else "active" if active else "scheduled" if future else "active"
        c.execute("UPDATE billing_subscriptions SET plan=?,status=?,period_end=?,updated_at=? WHERE tenant_id=?", (active["plan"] if active else "free", status, active["ends_at"] if active else None, now, tenant_id))

    def reserve_in_transaction(self, c, tenant_id, request_key, feature, units):
        if feature not in {"ai", "historical_backtest"} or type(units) is not int or not 0 < units <= 100000:
            raise IdentityError("Invalid usage reservation.", 422)
        self.ensure(c, tenant_id)
        previous = c.execute("SELECT * FROM usage_reservations WHERE tenant_id=? AND request_key=?", (tenant_id, request_key)).fetchone()
        if previous:
            if previous["feature"] != feature or previous["reserved"] != units:
                raise IdentityError("Usage key was reused with a different request.", 409)
            return dict(previous)
        if c.execute("SELECT balance FROM credit_accounts WHERE tenant_id=?", (tenant_id,)).fetchone()[0] < units:
            raise IdentityError("Not enough platform usage credits. Risk-reducing trading controls remain available.", 402)
        reservation_id = uuid.uuid4().hex
        self.credit(c, tenant_id, "reserve:" + reservation_id, "RESERVE", -units)
        c.execute("INSERT INTO usage_reservations VALUES(?,?,?,?,?,NULL,'reserved',?)", (reservation_id, tenant_id, request_key, feature, units, int(time.time())))
        return dict(c.execute("SELECT * FROM usage_reservations WHERE id=?", (reservation_id,)).fetchone())

    def reserve(self, tenant_id, request_key, feature, units):
        with self.identity.tx() as c:
            return self.reserve_in_transaction(c, tenant_id, request_key, feature, units)

    def settle(self, tenant_id, reservation_id, used):
        with self.identity.tx() as c:
            row = c.execute("SELECT * FROM usage_reservations WHERE id=? AND tenant_id=?", (reservation_id, tenant_id)).fetchone()
            if not row:
                raise IdentityError("Usage reservation not found.", 404)
            if type(used) is not int or not 0 <= used <= row["reserved"]:
                raise IdentityError("Invalid settled usage.", 422)
            if row["status"] == "settled":
                if row["used"] != used:
                    raise IdentityError("This usage was already settled differently.", 409)
                return
            self.credit(c, tenant_id, "release:" + reservation_id, "RELEASE", row["reserved"] - used)
            c.execute("UPDATE usage_reservations SET used=?,status='settled' WHERE id=?", (used, reservation_id))
