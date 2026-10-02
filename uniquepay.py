"""
uniqueplay.py — UniquePay card-to-card gateway
Docs: https://uniquepay.top/api-docs
Full implementation: create invoice, check invoice, DDBot/Mirza compat.
"""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://uniquepay.top"


class UniquePayError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ---------- error map ----------
ERROR_MESSAGES = {
    403: "توکن ارسال نشده است",
    404: "بیزینس یافت نشد",
    402: "بیزینس غیرفعال یا تایید نشده است",
    101: "hashId ارسال نشده است",
    102: "مبلغ نامعتبر است",
    192: "حداقل مبلغ ۵۰٬۰۰۰ تومان است",
    103: "hashId تکراری است",
    104: "redirectUrl معتبر نیست",
    105: "callbackUrl معتبر نیست",
    106: "کارت یا آدرس بازگشت موجود نیست",
    107: "کارت فعال موجود نیست",
    108: "مبلغ یکتا موجود نیست",
}


class UniquePayClient:
    """
    Full async client for UniquePay API.
    Business Token is loaded at runtime from DB/settings so it can be changed
    without restarting the bot.
    """

    def __init__(self, business_token: str, session: Optional[aiohttp.ClientSession] = None):
        self.token = business_token
        self._session = session
        self._own_session = session is None

    # ---------- session ----------
    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self):
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    # ---------- helpers ----------
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def _post(self, endpoint: str, data: dict) -> dict:
        session = await self._get_session()
        url = f"{BASE_URL}{endpoint}"
        try:
            async with session.post(url, data=data, headers=self._headers(), timeout=aiohttp.ClientTimeout(total=15)) as resp:
                result = await resp.json(content_type=None)
                code = result.get("code", resp.status)
                if not result.get("status", False) and code != 200:
                    msg = result.get("message") or ERROR_MESSAGES.get(code, "خطای ناشناخته")
                    raise UniquePayError(code, msg)
                return result
        except UniquePayError:
            raise
        except asyncio.TimeoutError:
            raise UniquePayError(0, "زمان اتصال به UniquePay تمام شد")
        except Exception as e:
            logger.exception("UniquePayClient._post error: %s", e)
            raise UniquePayError(0, str(e))

    # ==========================================
    # CREATE INVOICE
    # POST /api/create-invoice
    # ==========================================
    async def create_invoice(
        self,
        hash_id: str,
        amount: int,
        redirect_url: Optional[str] = None,
        callback_url: Optional[str] = None,
    ) -> dict:
        """
        Returns:
            refId, paymentLink, telegramPaymentLink, whiteLabel{cardNumber, payableAmount}
        Raises:
            UniquePayError on failure.
        """
        data: dict = {"hashId": hash_id, "amount": str(amount)}
        if redirect_url:
            data["redirectUrl"] = redirect_url
        if callback_url:
            data["callbackUrl"] = callback_url

        result = await self._post("/api/create-invoice", data)
        return {
            "ref_id": result.get("refId"),
            "payment_link": result.get("paymentLink"),
            "telegram_payment_link": result.get("telegramPaymentLink"),
            "white_label": result.get("whiteLabel", {}),
            "hash_id": result.get("hashId"),
        }

    # ==========================================
    # CHECK INVOICE
    # POST /api/check-invoice
    # ==========================================
    async def check_invoice(self, hash_id: str) -> dict:
        """
        Returns invoice dict with isPaid, isVerified, status, ...
        """
        result = await self._post("/api/check-invoice", {"hashId": hash_id})
        invoice = result.get("invoice", {})
        return {
            "is_paid": invoice.get("isPaid", False),
            "is_verified": invoice.get("isVerified", False),
            "status": invoice.get("status", "pending"),
            "amount": invoice.get("amount"),
            "payable_amount": invoice.get("payableAmount"),
            "fee": invoice.get("fee"),
            "fee_payer": invoice.get("feePayer"),
            "card_number": invoice.get("whiteLabel", {}).get("cardNumber"),
            "raw": invoice,
        }

    # ==========================================
    # DDBot / Mirza compat endpoints
    # ==========================================
    async def ddbot_create_invoice(self, hash_id: str, amount: int, order_id: str = "",
                                   callback_url: str = "", redirect_url: str = "") -> dict:
        data = {"hashId": hash_id, "amount": str(amount)}
        if order_id: data["orderId"] = order_id
        if callback_url: data["callbackUrl"] = callback_url
        if redirect_url: data["redirectUrl"] = redirect_url
        result = await self._post("/api/ddbot/create-invoice", data)
        return result

    async def ddbot_check_invoice(self, hash_id: str) -> dict:
        return await self._post("/api/ddbot/check-invoice", {"hashId": hash_id})

    # ==========================================
    # POLL for payment (helper used by handler)
    # ==========================================
    async def wait_for_payment(
        self,
        hash_id: str,
        timeout: int = 900,
        interval: int = 10,
    ) -> Optional[dict]:
        """
        Poll until paid or timeout. Returns check_invoice dict or None.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(interval)
            try:
                info = await self.check_invoice(hash_id)
                if info["is_paid"]:
                    return info
            except UniquePayError as e:
                logger.warning("poll_invoice error: %s", e)
        return None


# ==========================================
# Singleton factory — reads token from settings at call time
# ==========================================
_CLIENTS: dict[str, UniquePayClient] = {}


def get_client(token: str) -> UniquePayClient:
    if token not in _CLIENTS:
        _CLIENTS[token] = UniquePayClient(token)
    return _CLIENTS[token]


def make_hash_id(user_id: int) -> str:
    """Generate a unique hashId for an order."""
    return f"order-{user_id}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
