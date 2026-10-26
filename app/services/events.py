"""Minimal in-process pub/sub feeding Server-Sent Events. Admins receive every ticket event; an author only
receives events for their own tickets. (Multi-instance deployments: swap for Redis pub/sub, same interface.)"""
import asyncio
import json

from dataclasses import dataclass, field


@dataclass(eq=False)  # eq=False -> hashed by identity, so instances can live in a set
class Subscriber:
    user: dict
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))


_clients: set[Subscriber] = set()


def subscribe(user: dict) -> Subscriber:
    sub = Subscriber(user)
    _clients.add(sub)
    return sub


def unsubscribe(entry) -> None:
    _clients.discard(entry)


def publish(event: dict) -> None:
    payload = f"event: ticket\ndata: {json.dumps(event)}\n\n"
    for sub in list(_clients):
        if sub.user["role"] == "admin" or sub.user["authorId"] == event.get("authorId"):
            try:
                sub.queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # slow consumer: it will refetch on reconnect/visibility anyway


def client_count() -> int:
    return len(_clients)
