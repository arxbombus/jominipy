from dataclasses import dataclass
from typing import Final, Literal


@dataclass(frozen=True, slots=True, order=True)
class TextSize:
    """Opaque measure of text length / index into text."""

    value: int

    def __post_init__(self):
        if self.value < 0:
            raise ValueError("TextSize cannot be negative")

    @staticmethod
    def of(text: str) -> "TextSize":
        """Create a TextSize from a string's length."""
        return TextSize(len(text))

    @staticmethod
    def from_int(value: int) -> "TextSize":
        """Create a TextSize from an integer."""
        return TextSize(value)

    def to_int(self) -> int:
        """Convert the TextSize to an integer."""
        return self.value

    def __add__(self, other: "TextSize") -> "TextSize":
        return TextSize(self.value + other.value)

    def __sub__(self, other: "TextSize") -> "TextSize":
        result = self.value - other.value
        if result < 0:
            raise ValueError("Resulting TextSize cannot be negative")
        return TextSize(result)

    def __repr__(self) -> str:
        return f"TextSize({self.value})"


ZERO: Final[TextSize] = TextSize(0)
"""Constant representing a TextSize of zero."""


@dataclass(frozen=True, slots=True, order=True)
class TextRange:
    """
    Half-open range [start, end) in text, represented by TextSize offsets.

    Invariant:
    - 0 <= start <= end

    Storing as ints for now for simplicity.
    """

    _start: int
    _end: int

    def __post_init__(self):
        if self._start < 0 or self._end < 0:
            raise ValueError("TextRange positions cannot be negative")
        if self._start > self._end:
            raise ValueError("TextRange invariant violated: start > end")

    @staticmethod
    def new(start: TextSize, end: TextSize) -> "TextRange":
        """Create a TextRange from start and end TextSizes."""
        return TextRange(start.value, end.value)

    @staticmethod
    def at(offset: TextSize, length: TextSize) -> "TextRange":
        # offset...offset+length
        """Create a TextRange at offset with given length."""
        return TextRange(offset.value, offset.value + length.value)

    @staticmethod
    def empty(offset: TextSize) -> "TextRange":
        """Create an empty TextRange at the given offset."""
        return TextRange(offset.value, offset.value)

    @staticmethod
    def up_to(end: TextSize) -> "TextRange":
        """Create a TextRange from 0 up to the given end offset."""
        return TextRange(0, end.value)

    @staticmethod
    def _from_offsets(start: int, end: int) -> "TextRange":
        """Create a TextRange from integer offsets (internal use - prefer using TextSize in most APIs)."""
        return TextRange(start, end)

    @property
    def start(self) -> TextSize:
        """Get the start offset as a TextSize."""
        return TextSize(self._start)

    @property
    def end(self) -> TextSize:
        """Get the end offset as a TextSize."""
        return TextSize(self._end)

    def len(self) -> TextSize:
        """Get the length of the range as a TextSize."""
        return TextSize(self._end - self._start)

    def is_empty(self) -> bool:
        """Check if the range is empty."""
        return self._start == self._end

    def as_tuple(self) -> tuple[int, int]:
        """Get the range as a tuple of (start, end) integers."""
        return (self._start, self._end)

    def contains(self, offset: TextSize) -> bool:
        """Check if the range contains the given offset."""
        return self._start <= offset.value < self._end

    def contains_inclusive(self, offset: TextSize) -> bool:
        """Check if the range contains the given offset, inclusive of end."""
        return self._start <= offset.value <= self._end

    def contains_range(self, other: "TextRange") -> bool:
        """Check if the range fully contains another range."""
        return self._start <= other._start and other._end <= self._end

    def intersect(self, other: "TextRange") -> "TextRange | None":
        """Get the intersection of this range with another range, or None if they don't overlap."""
        start = max(self._start, other._start)
        end = min(self._end, other._end)
        if end < start:
            return None
        return TextRange._from_offsets(start, end)

    def cover(self, other: "TextRange") -> "TextRange":
        """Get the minimal range that covers both this range and another range."""
        start = min(self._start, other._start)
        end = max(self._end, other._end)
        return TextRange._from_offsets(start, end)

    def cover_offset(self, offset: TextSize) -> "TextRange":
        """Get the minimal range that covers this range and the given offset."""
        return self.cover(TextRange._from_offsets(offset.value, offset.value))

    def ordering(self, other: "TextRange") -> Literal[-1, 0, 1]:
        """Compare this range to another range for ordering.

        Returns:
        - -1 if this range is before the other range
        - 0 if the ranges overlap
        - 1 if this range is after the other range
        """
        if self._end <= other._start:
            return -1
        elif other._end <= self._start:
            return 1
        else:
            return 0

    def shift(self, delta: TextSize) -> "TextRange":
        """Shift the range by the given delta."""
        d = delta.value
        return TextRange._from_offsets(self._start + d, self._end + d)

    def unshift(self, delta: TextSize) -> "TextRange":
        """Unshift the range by the given delta."""
        d = delta.value
        result_start = self._start - d
        result_end = self._end - d
        if result_start < 0 or result_end < 0:
            raise ValueError("Resulting TextRange positions cannot be negative")
        return TextRange._from_offsets(result_start, result_end)

    def __repr__(self) -> str:
        return f"TextRange({self._start}, {self._end})"


def slice_text_range(source: str, range: TextRange) -> str:
    """Get the substring of the source text covered by the given TextRange.

    Coord system matches python string indices so we can just do this.
    """
    return source[range.start.value : range.end.value]
