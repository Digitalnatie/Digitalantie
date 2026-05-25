import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DigitalnatieWooWebhook(http.Controller):
    """Receive WooCommerce webhooks for instant order/product/customer updates."""

    @http.route(
        "/digitalnatie_woo/webhook/<int:instance_id>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def woo_webhook(self, instance_id, **kwargs):
        instance = (
            request.env["digitalnatie.woo.instance"].sudo().browse(instance_id)
        )
        if not instance.exists() or not instance.is_active:
            return request.make_json_response(
                {"status": "ignored"}, status=404
            )
        if not instance.webhook_enabled:
            return request.make_json_response(
                {"status": "webhooks disabled"}, status=403
            )

        raw_body = request.httprequest.get_data() or b""
        headers = request.httprequest.headers
        topic = headers.get("X-WC-Webhook-Topic", "")
        signature = headers.get("X-WC-Webhook-Signature", "")

        # WooCommerce sends a body-less ping when the webhook is first created.
        if not topic or not raw_body.strip():
            return request.make_json_response({"status": "ok", "ping": True})

        if not instance._verify_webhook_signature(raw_body, signature):
            _logger.warning(
                "Digitalnatie Woo: invalid webhook signature for instance %s",
                instance_id,
            )
            return request.make_json_response(
                {"status": "invalid signature"}, status=401
            )

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except Exception:
            payload = {}

        try:
            instance._handle_webhook(topic, payload)
            request.env.cr.commit()
        except Exception as e:
            request.env.cr.rollback()
            _logger.exception("Digitalnatie Woo: webhook handling failed: %s", e)
            instance._woo_log(
                "webhook", "error", "Webhook %s failed" % topic, message=str(e)
            )
            request.env.cr.commit()
            return request.make_json_response({"status": "error"}, status=500)

        return request.make_json_response({"status": "ok"})
