"""Customer billing views and authenticated test-provider events."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from .api import principal, owner, TenantContext, require_tenant_context

router = APIRouter(prefix="/api/billing")


class Checkout(TenantContext):
    plan: str = Field(pattern=r"^(trader|pro|professional)$")
    key: str = Field(min_length=8, max_length=160)


@router.get("/plans")
def plans(request: Request):
    return request.app.state.commerce.pricing()


@router.get("/account")
def account(request: Request):
    user = principal(request)
    return request.app.state.commerce.snapshot(user["tenant_id"])


@router.post("/checkout")
def checkout(body: Checkout, request: Request):
    user = owner(request)
    require_tenant_context(request, body.expected_tenant_id)
    request.app.state.identity.rate_limit("checkout:" + user["user_id"], 10, 3600)
    return request.app.state.commerce.checkout(user["tenant_id"], body.plan, body.key)


@router.post("/webhook")
async def webhook(request: Request):
    length = request.headers.get("content-length", "0")
    if not length.isdigit() or int(length) > 65536:
        raise HTTPException(413, "Webhook is too large.")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 65536:
            raise HTTPException(413, "Webhook is too large.")
        chunks.append(chunk)
    return request.app.state.commerce.webhook(b"".join(chunks), request.headers.get("x-razorpay-signature", ""))


@router.get("/receipts/{receipt_id}")
def receipt(receipt_id: str, request: Request):
    user = principal(request)
    with request.app.state.identity.tx() as c:
        row = c.execute("SELECT id,amount,currency,created_at FROM billing_receipts WHERE id=? AND tenant_id=?", (receipt_id, user["tenant_id"])).fetchone()
    if not row:
        raise HTTPException(404, "Receipt not found.")
    return dict(row) | {"kind": "sandbox_payment_receipt", "notice": "Operational test receipt, not a finalized tax invoice."}


@router.get("/checkouts")
def checkouts(request: Request):
    user = owner(request)
    with request.app.state.identity.tx() as c:
        rows = c.execute('SELECT id,plan,amount,provider_order,status,created_at FROM billing_intents WHERE tenant_id=? ORDER BY created_at DESC,id DESC LIMIT 100',(user['tenant_id'],)).fetchall()
    return {'checkouts':[dict(row) for row in rows]}


@router.post("/checkouts/{intent_id}/reconcile")
def reconcile(intent_id: str,body: TenantContext,request: Request):
    user=owner(request)
    require_tenant_context(request,body.expected_tenant_id)
    request.app.state.identity.rate_limit('reconcile:'+user['user_id'],20,3600)
    return request.app.state.commerce.reconcile_checkout(user['tenant_id'],intent_id)
