from __future__ import annotations

import threading

from app.channels.base import ChannelAdapter
from app.channels.messenger_adapter import MessengerAdapter
from app.channels.web_chat_adapter import WebChatAdapter
from app.channels.whatsapp_adapter import WhatsAppAdapter
from app.schemas import normalize_channel_name


class ChannelNotRegisteredError(KeyError):
    """Raised when an operation targets a channel with no registered adapter."""


class ChannelRegistry:
    """Thread-safe registry and dispatcher mapping channel slugs to ChannelAdapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}
        self._lock = threading.Lock()

    def register(self, adapter: ChannelAdapter) -> None:
        key = normalize_channel_name(adapter.channel_name)
        with self._lock:
            self._adapters[key] = adapter

    def get(self, channel_name: str) -> ChannelAdapter:
        key = normalize_channel_name(channel_name)
        with self._lock:
            adapter = self._adapters.get(key)
        if not adapter:
            raise ChannelNotRegisteredError(f"No ChannelAdapter registered for channel '{key}'.")
        return adapter

    def has(self, channel_name: str) -> bool:
        try:
            key = normalize_channel_name(channel_name)
        except ValueError:
            return False
        with self._lock:
            return key in self._adapters

    def list_channels(self) -> list[str]:
        with self._lock:
            return sorted(self._adapters.keys())


_default_registry: ChannelRegistry | None = None
_registry_lock = threading.Lock()


def get_channel_registry() -> ChannelRegistry:
    """Return the process-wide ChannelRegistry pre-populated with built-in adapters."""
    global _default_registry
    with _registry_lock:
        if _default_registry is None:
            registry = ChannelRegistry()
            registry.register(WhatsAppAdapter())
            registry.register(MessengerAdapter())
            registry.register(WebChatAdapter())
            _default_registry = registry
        return _default_registry
