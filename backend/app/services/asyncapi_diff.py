# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What changed between two AsyncAPI documents (2.x and 3.x), for someone who
takes part in the messaging the document describes.

An operation is (direction, channel): "PUBLISH" / "SUBSCRIBE" in 2.x, "SEND" /
"RECEIVE" in 3.x, written from the point of view of the application the
document describes. A client SENDS messages where the application receives
them (2.x publish, 3.x receive) and RECEIVES them where it sends (2.x
subscribe, 3.x send) - so the payload of the first is judged like an OpenAPI
request body and the payload of the second like a response: a required property
added to something a client sends is breaking, a property removed from
something it receives is. The payloads are compared by the same code as
OpenAPI schemas (app/services/spec_diff.py), `$ref`s included.

The changes reuse the OpenAPI kinds - an operation removed, a property of the
payload changed - with the direction as `method`, the channel as `path` and the
message name as `media_type` (scope "message"), so the frontend words them with
the same texts. Compared: operations, the messages of each, their payloads.
Not compared: headers, bindings, channel parameters, servers, security."""

from dataclasses import dataclass, field
from typing import Any

from app.services.spec_diff import Change, SpecDiff, _Comparison, _deref


@dataclass
class _Operation:
    sending: bool
    deprecated: bool = False
    messages: dict[str, Any] = field(default_factory=dict)  # name -> payload schema (unresolved)


def _message_name(message: Any, ref: str | None, fallback: str) -> str:
    if isinstance(message, dict):
        for key in ("name", "messageId"):
            if isinstance(message.get(key), str) and message[key]:
                return message[key]
    return ref.rsplit("/", 1)[-1] if ref else fallback


def _messages_of_v2(doc: dict, node: Any) -> dict[str, Any]:
    """A 2.x operation's `message`: one message, or {"oneOf": [...]}."""
    message, ref = _deref(doc, node)
    if not isinstance(message, dict):
        return {}
    if isinstance(message.get("oneOf"), list):
        found: dict[str, Any] = {}
        for index, option in enumerate(message["oneOf"]):
            resolved, option_ref = _deref(doc, option)
            if isinstance(resolved, dict):
                found[_message_name(resolved, option_ref, f"message{index + 1}")] = resolved.get("payload")
        return found
    return {_message_name(message, ref, "message"): message.get("payload")}


def _operations_v2(doc: dict) -> dict[tuple[str, str], _Operation]:
    found: dict[tuple[str, str], _Operation] = {}
    channels = doc.get("channels")
    if not isinstance(channels, dict):
        return found
    for channel_name, raw in channels.items():
        channel, _ = _deref(doc, raw)
        if not isinstance(channel, dict):
            continue
        for action in ("publish", "subscribe"):
            operation = channel.get(action)
            if isinstance(operation, dict):
                found[(action.upper(), str(channel_name))] = _Operation(
                    sending=action == "publish",  # the application consumes what clients publish
                    deprecated=operation.get("deprecated") is True,
                    messages=_messages_of_v2(doc, operation.get("message")),
                )
    return found


def _operations_v3(doc: dict) -> dict[tuple[str, str], _Operation]:
    found: dict[tuple[str, str], _Operation] = {}
    operations = doc.get("operations")
    if not isinstance(operations, dict):
        return found
    for raw in operations.values():
        operation, _ = _deref(doc, raw)
        if not isinstance(operation, dict) or operation.get("action") not in ("send", "receive"):
            continue
        channel, channel_ref = _deref(doc, operation.get("channel"))
        if not isinstance(channel, dict):
            continue
        address = channel.get("address") if isinstance(channel.get("address"), str) else None
        address = address or (channel_ref.rsplit("/", 1)[-1] if channel_ref else "")
        action = operation["action"]
        key = (action.upper(), address)
        entry = found.setdefault(key, _Operation(sending=action == "receive"))  # the application receives what clients send
        entry.deprecated = entry.deprecated or operation.get("deprecated") is True
        listed = operation.get("messages")
        if isinstance(listed, list):
            for index, option in enumerate(listed):
                message, ref = _deref(doc, option)
                if isinstance(message, dict):
                    entry.messages[_message_name(message, ref, f"message{index + 1}")] = message.get("payload")
        elif isinstance(channel.get("messages"), dict):
            for name, option in channel["messages"].items():
                message, _ = _deref(doc, option)
                if isinstance(message, dict):
                    entry.messages[str(name)] = message.get("payload")
    return found


def operations(doc: dict) -> dict[tuple[str, str], _Operation]:
    """{(DIRECTION, channel): operation} of a 2.x or 3.x document."""
    return _operations_v3(doc) if str(doc.get("asyncapi", "")).startswith("3") else _operations_v2(doc)


class _AsyncComparison(_Comparison):
    def run(self) -> SpecDiff:
        old_ops, new_ops = operations(self.old), operations(self.new)
        for key in sorted(old_ops.keys() | new_ops.keys()):
            direction, channel = key
            if key not in new_ops:
                self.add(Change("operation_removed", "breaking", direction, channel))
            elif key not in old_ops:
                self.add(Change("operation_added", "info", direction, channel))
            else:
                self._messages(direction, channel, old_ops[key], new_ops[key])
        self.changes.sort(key=Change.sort_key)
        return SpecDiff(self.changes, self.truncated)

    def _messages(self, direction: str, channel: str, old: _Operation, new: _Operation) -> None:
        sending = new.sending
        if new.deprecated and not old.deprecated:
            self.add(Change("operation_deprecated", "warning", direction, channel))
        elif old.deprecated and not new.deprecated:
            self.add(Change("operation_undeprecated", "info", direction, channel))
        for name in sorted(old.messages.keys() | new.messages.keys()):
            where = dict(method=direction, path=channel, scope="message", media_type=name)
            if name not in new.messages:
                self.add(Change("message_removed", "breaking", **where))
            elif name not in old.messages:
                # A message a client may now send is harmless; one it may now receive is something it may not handle.
                self.add(Change("message_added", "info" if sending else "warning", **where))
            else:
                self._schema(old.messages[name], new.messages[name], where, sending=sending, location="")


def diff_asyncapi(old: dict, new: dict) -> SpecDiff:
    """The changes from AsyncAPI document `old` to `new`, most severe first.
    Never raises on an odd document: a part that is not shaped as expected is
    skipped."""
    return _AsyncComparison(old, new).run()
