from __future__ import annotations

import triageflow.core as core

from triageflow.core import emit, register_hook, set_hook_error_handler


def setup_function() -> None:
    core._event_hooks.clear()
    core._hook_error_handler = None


def test_emit_no_hooks() -> None:
    emit("nonexistent.event", foo="bar")


def test_register_and_emit() -> None:
    received = []

    register_hook("test.event", lambda **ctx: received.append(ctx))

    emit("test.event", key="value")

    assert received == [{"key": "value"}]


def test_callback_exception_does_not_propagate() -> None:
    def bad_hook(**ctx) -> None:
        raise RuntimeError("boom")

    register_hook("test.event", bad_hook)

    emit("test.event")


def test_hook_error_handler_called() -> None:
    errors_received = []

    def bad_hook(**ctx) -> None:
        raise ValueError("fail")

    def error_handler(event, errors) -> None:
        errors_received.append((event, len(errors)))

    register_hook("test.event", bad_hook)
    set_hook_error_handler(error_handler)

    emit("test.event")

    assert errors_received == [("test.event", 1)]


def test_error_handler_exception_is_swallowed() -> None:
    def bad_hook(**ctx) -> None:
        raise RuntimeError("hook fail")

    def bad_error_handler(event, errors) -> None:
        raise RuntimeError("handler fail")

    register_hook("test.event", bad_hook)
    set_hook_error_handler(bad_error_handler)

    emit("test.event")


def test_multiple_hooks_all_called() -> None:
    results = []

    def hook_a(**ctx) -> None:
        results.append("a")

    def hook_b(**ctx) -> None:
        raise RuntimeError("b fails")

    def hook_c(**ctx) -> None:
        results.append("c")

    register_hook("test.event", hook_a)
    register_hook("test.event", hook_b)
    register_hook("test.event", hook_c)

    emit("test.event")

    assert results == ["a", "c"]
