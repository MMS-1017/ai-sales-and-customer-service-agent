from __future__ import annotations

import logging
import threading
from typing import Any

from flask import Blueprint, Request, current_app, jsonify, request

from app.channels.base import ChannelAuthError, ChannelValidationError
from app.channels.registry import ChannelNotRegisteredError, ChannelRegistry, get_channel_registry
from app.extensions import db
from app.schemas import UnifiedAgentResponse, UnifiedIncomingMessage
from app.services.channel_service import ChannelService, WebhookDeduplicator
from app.services.identity_service import CustomerNotFoundError

logger = logging.getLogger(__name__)

omnichannel_bp = Blueprint("omnichannel", __name__)
_channel_deduplicators: dict[str, WebhookDeduplicator] = {}


def _get_deduplicator(channel_name: str) -> WebhookDeduplicator:
    if channel_name not in _channel_deduplicators:
        _channel_deduplicators[channel_name] = WebhookDeduplicator()
    return _channel_deduplicators[channel_name]


def _run_async_message(app, channel_name: str, incoming: UnifiedIncomingMessage, deduplicator: WebhookDeduplicator) -> None:
    """Process an asynchronous webhook message inside an isolated Flask application context."""
    with app.app_context():
        try:
            ChannelService.process_message(incoming)
        except Exception:
            if incoming.external_message_id:
                deduplicator.remove(incoming.external_message_id)
            db.session.rollback()
            logger.exception("Async omnichannel processing failed for channel=%s", channel_name)


def handle_channel_request(
    channel_name: str,
    req: Request,
    *,
    deduplicator: WebhookDeduplicator | None = None,
    registry: ChannelRegistry | None = None,
) -> tuple[Any, int]:
    """Unified HTTP dispatcher delegating request lifecycle to the registered ChannelAdapter."""
    resolved_registry = registry or get_channel_registry()
    try:
        adapter = resolved_registry.get(channel_name)
    except ChannelNotRegisteredError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    active_dedup = deduplicator or _get_deduplicator(adapter.channel_name)

    try:
        adapter.verify_webhook(req)
    except ChannelAuthError as auth_err:
        return jsonify({"success": False, "error": auth_err.message}), auth_err.status_code

    try:
        incoming_messages, ignore_reason = adapter.parse_incoming(req)
    except ChannelValidationError as val_err:
        return jsonify({"success": False, "error": val_err.message}), val_err.status_code
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 400

    if ignore_reason:
        body, status = adapter.format_http_response([], ignored_reason=ignore_reason)
        return (jsonify(body) if isinstance(body, dict) else body), status

    async_mode = bool(
        current_app.config.get("WEBHOOK_ASYNC_PROCESSING", False)
        and adapter.delivers_asynchronously
    )

    results: list[UnifiedAgentResponse] = []
    single_message_mode = len(incoming_messages) == 1

    for incoming in incoming_messages:
        if incoming.external_message_id and active_dedup.is_duplicate(incoming.external_message_id):
            logger.info(
                "Ignoring duplicate inbound message channel=%s external_id=%s",
                adapter.channel_name,
                incoming.external_message_id,
            )
            if single_message_mode:
                body, status = adapter.format_http_response([], ignored_reason="duplicate_message")
                return (jsonify(body) if isinstance(body, dict) else body), status
            continue

        if async_mode:
            app_obj = current_app._get_current_object()
            worker = threading.Thread(
                target=_run_async_message,
                args=(app_obj, adapter.channel_name, incoming, active_dedup),
                daemon=True,
            )
            worker.start()
            continue

        try:
            agent_response = ChannelService.process_message(
                incoming,
                adapter=adapter,
                registry=resolved_registry,
            )
            if not agent_response.success and agent_response.error == "empty_message":
                if single_message_mode:
                    body, status = adapter.format_http_response([], ignored_reason="empty_message")
                    return (jsonify(body) if isinstance(body, dict) else body), status
                continue
            results.append(agent_response)
        except CustomerNotFoundError as not_found_err:
            if incoming.external_message_id:
                active_dedup.remove(incoming.external_message_id)
            return jsonify({"success": False, "error": str(not_found_err)}), 404
        except ValueError as val_err:
            if incoming.external_message_id:
                active_dedup.remove(incoming.external_message_id)
            return jsonify({"success": False, "error": str(val_err)}), 400
        except Exception as exc:
            if incoming.external_message_id:
                active_dedup.remove(incoming.external_message_id)
            db.session.rollback()
            logger.exception("Omnichannel processing failed for channel=%s", adapter.channel_name)
            if adapter.delivers_asynchronously:
                if not single_message_mode:
                    # Acknowledge other items in batch webhooks after recording error
                    continue
                return jsonify({"success": False, "error": "Message processing failed"}), 500
            return jsonify({"success": False, "error": str(exc)}), 500

    body, status = adapter.format_http_response(results)
    return (jsonify(body) if isinstance(body, dict) else body), status


@omnichannel_bp.post("/webhooks/channel/<channel_name>")
def generic_channel_webhook(channel_name: str):
    """Dynamic route enabling newly registered channels without adding controller boilerplate."""
    return handle_channel_request(channel_name, request)
