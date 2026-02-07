"""Parser events."""

from dataclasses import dataclass
from typing import Protocol

from jominipy.diagnostics import Diagnostic
from jominipy.syntax import JominiSyntaxKind
from jominipy.text import TextSize


@dataclass(frozen=True, slots=True)
class StartEvent:
    kind: JominiSyntaxKind
    forward_parent: int | None = None

    @staticmethod
    def tombstone() -> "StartEvent":
        return StartEvent(kind=JominiSyntaxKind.TOMBSTONE, forward_parent=None)


@dataclass(frozen=True, slots=True)
class FinishEvent:
    pass


@dataclass(frozen=True, slots=True)
class TokenEvent:
    kind: JominiSyntaxKind
    end: TextSize


Event = StartEvent | FinishEvent | TokenEvent


class TreeSink(Protocol):
    def token(self, kind: JominiSyntaxKind, end: TextSize) -> None: ...

    def start_node(self, kind: JominiSyntaxKind) -> None: ...

    def finish_node(self) -> None: ...

    def errors(self, errors: list[Diagnostic]) -> None: ...


def process_events(
    sink: TreeSink,
    events: list[Event],
    errors: list[Diagnostic],
) -> None:
    sink.errors(errors)
    forward_parents: list[JominiSyntaxKind] = []

    idx = 0
    while idx < len(events):
        event = events[idx]
        if isinstance(event, StartEvent):
            if event.kind == JominiSyntaxKind.TOMBSTONE:
                idx += 1
                continue

            forward_parents.append(event.kind)
            parent_idx = idx
            parent_offset = event.forward_parent

            while parent_offset is not None:
                parent_idx += parent_offset
                if parent_idx >= len(events):
                    raise RuntimeError("Invalid forward_parent offset in parser events")

                parent_event = events[parent_idx]
                if not isinstance(parent_event, StartEvent):
                    raise RuntimeError("forward_parent must point to StartEvent")

                events[parent_idx] = StartEvent.tombstone()
                if parent_event.kind != JominiSyntaxKind.TOMBSTONE:
                    forward_parents.append(parent_event.kind)

                parent_offset = parent_event.forward_parent

            while forward_parents:
                sink.start_node(forward_parents.pop())
        elif isinstance(event, FinishEvent):
            sink.finish_node()
        else:
            sink.token(event.kind, event.end)

        idx += 1
