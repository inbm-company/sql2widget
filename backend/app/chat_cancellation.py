"""Cooperative cancellation of synchronous chat work on client disconnect."""

import asyncio
from contextvars import ContextVar
from functools import wraps
from threading import Event

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

_cancel_event = ContextVar("chat_cancel_event", default=None)


class ChatCancelled(BaseException):
    # Model/agent fallbacks catch Exception; cancellation must bypass those retries.
    pass


def check_cancelled():
    event = _cancel_event.get()
    if event is not None and event.is_set():
        raise ChatCancelled()


def cancellation_checkpoint(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        check_cancelled()
        result = function(*args, **kwargs)
        check_cancelled()
        return result
    return wrapped


async def run_chat(request, work):
    event = Event()

    def worker():
        token = _cancel_event.set(event)
        try:
            check_cancelled()
            return work()
        except ChatCancelled:
            raise HTTPException(status_code=499, detail="응답 생성을 중지했습니다.") from None
        finally:
            _cancel_event.reset(token)

    task = asyncio.create_task(run_in_threadpool(worker))
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=0.1)
            if not task.done() and await request.is_disconnected():
                event.set()
        return await task
    finally:
        event.set()
        # If the ASGI request itself is cancelled, consume eventual worker errors.
        if not task.done():
            task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
