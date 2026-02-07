"""Markers for event-based parsing."""

from dataclasses import dataclass

from jominipy.parser.event import FinishEvent, StartEvent, TokenEvent
from jominipy.syntax import JominiSyntaxKind
from jominipy.text import TextRange, TextSize


@dataclass(slots=True)
class Marker:
    pos: int
    start: TextSize
    old_start: int
    child_idx: int | None = None

    def complete(self, parser: "Parser", kind: JominiSyntaxKind) -> "CompletedMarker":
        event = parser.events[self.pos]
        if isinstance(event, StartEvent):
            parser.events[self.pos] = StartEvent(kind=kind, forward_parent=event.forward_parent)
        else:
            raise RuntimeError("Marker must point to a StartEvent")

        finish_pos = len(parser.events)
        parser.events.append(FinishEvent())
        return CompletedMarker(
            start_pos=self.pos,
            finish_pos=finish_pos,
            offset=self.start,
            old_start=self.old_start,
        )

    def abandon(self, parser: "Parser") -> None:
        idx = self.pos
        if idx == len(parser.events) - 1:
            event = parser.events[-1]
            if isinstance(event, StartEvent) and event.forward_parent is None:
                parser.events.pop()

        if self.child_idx is not None:
            event = parser.events[self.child_idx]
            if isinstance(event, StartEvent):
                parser.events[self.child_idx] = StartEvent(kind=event.kind, forward_parent=None)


@dataclass(frozen=True, slots=True)
class CompletedMarker:
    start_pos: int
    finish_pos: int
    offset: TextSize
    old_start: int

    def change_kind(self, parser: "Parser", new_kind: JominiSyntaxKind) -> None:
        event = parser.events[self.start_pos]
        if isinstance(event, StartEvent):
            parser.events[self.start_pos] = StartEvent(kind=new_kind, forward_parent=event.forward_parent)
        else:
            raise RuntimeError("CompletedMarker points to non-start event")

    def range(self, parser: "Parser") -> TextRange:
        end = self.offset
        for event in reversed(parser.events[self.old_start : self.finish_pos]):
            if isinstance(event, TokenEvent):
                end = event.end
                break
        return TextRange.new(self.offset, end)

    def text(self, parser: "Parser") -> str:
        rng = self.range(parser)
        return parser.source.text[rng.start.value : rng.end.value]

    def precede(self, parser: "Parser") -> Marker:
        new_pos = parser.start()
        idx = self.start_pos
        event = parser.events[idx]
        if isinstance(event, StartEvent):
            distance = new_pos.pos - self.start_pos
            if distance <= 0:
                raise RuntimeError("Invalid precede distance")
            parser.events[idx] = StartEvent(kind=event.kind, forward_parent=distance)
        else:
            raise RuntimeError("CompletedMarker points to non-start event")

        new_pos.child_idx = self.start_pos
        new_pos.start = self.offset
        new_pos.old_start = min(new_pos.old_start, self.old_start)
        return new_pos

    def undo_completion(self, parser: "Parser") -> Marker:
        event = parser.events[self.start_pos]
        if not isinstance(event, StartEvent):
            raise RuntimeError("CompletedMarker points to non-start event")
        if self.finish_pos != len(parser.events) - 1:
            raise RuntimeError("Can only undo the most recent completion")

        parser.events.pop()
        return Marker(
            pos=self.start_pos,
            start=self.offset,
            old_start=self.old_start,
        )


from jominipy.parser.parser import Parser
