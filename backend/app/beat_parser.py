"""Streaming parser for the narrator's semantic beat protocol."""

from __future__ import annotations

import html
import re


_FENCE_RE = re.compile(r"^\s*```(?:xml|html)?\s*$", re.IGNORECASE)
_BEAT_RE = re.compile(
    r"<beat\b(?P<attrs>[^>]*)>(?P<text>.*?)</beat\s*>",
    re.IGNORECASE | re.DOTALL,
)
_ATTR_RE = re.compile(
    r"(?P<key>[\w:-]+)\s*=\s*(?:\"(?P<double>[^\"]*)\"|"
    r"'(?P<single>[^']*)'|(?P<bare>[^\s>]+))"
)
_BEAT_MARKUP_RE = re.compile(r"</?beat\b[^>]*>", re.IGNORECASE)


def _narration(text: str, speaker: str | None = None) -> dict:
    return {"type": "narration", "speaker": speaker or None, "text": text.strip()}


def _attributes(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in _ATTR_RE.finditer(raw):
        value = match.group("double")
        if value is None:
            value = match.group("single")
        if value is None:
            value = match.group("bare")
        attrs[match.group("key").lower()] = html.unescape(value or "")
    return attrs


def _parse_line(line: str) -> list[dict]:
    candidate = line.strip()
    if not candidate or _FENCE_RE.match(candidate):
        return []
    beats = []
    for match in _BEAT_RE.finditer(candidate):
        attrs = _attributes(match.group("attrs"))
        beat_type = attrs.get("type", "").strip().lower()
        text = html.unescape(match.group("text")).strip()
        if beat_type not in {"narration", "dialogue"} or not text:
            continue
        speaker = attrs.get("speaker", "").strip() or None
        if beat_type == "dialogue" and not speaker:
            continue
        beats.append({"type": beat_type, "speaker": speaker, "text": text})
    return beats


class BeatStreamParser:
    """Parse complete beat lines from arbitrarily chunked model output."""

    def __init__(self) -> None:
        self._buffer = ""
        self._pending_raw = ""
        self._seen_valid_beat = False

    def feed(self, chunk: str) -> list[dict]:
        """Consume arbitrary text and return beats completed by this chunk."""
        if not chunk:
            return []
        self._buffer += chunk
        out: list[dict] = []
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            out.extend(self._consume_line(line + "\n"))
        return out

    def finish(self) -> list[dict]:
        """Flush the last partial line and soft-fallback malformed output."""
        out: list[dict] = []
        if self._buffer:
            out.extend(self._consume_line(self._buffer))
            self._buffer = ""
        if self._pending_raw.strip():
            out.append(_narration(self._pending_raw))
            self._pending_raw = ""
        return out

    def _consume_line(self, raw_line: str) -> list[dict]:
        parsed = _parse_line(raw_line)
        if parsed:
            out: list[dict] = []
            if self._pending_raw.strip():
                out.append(_narration(self._pending_raw))
                self._pending_raw = ""
            out.extend(parsed)
            self._seen_valid_beat = True
            return out

        candidate = raw_line.strip()
        if not candidate or _FENCE_RE.match(candidate):
            return []

        # A malformed beat after a valid one is provider noise, not story text.
        # Before the first valid beat, strip the markup so the plain fallback is
        # still useful when a model emits a nearly-correct tag.
        if _BEAT_MARKUP_RE.search(candidate) or re.search(r"<\s*/?beat\b", candidate, re.IGNORECASE):
            if self._seen_valid_beat:
                return []
            cleaned = _BEAT_MARKUP_RE.sub(" ", raw_line).strip()
            if cleaned:
                self._pending_raw += cleaned + "\n"
            return []

        if self._seen_valid_beat:
            return [_narration(raw_line)]
        self._pending_raw += raw_line
        return []


def beat_to_prose(beat: dict) -> str:
    """Render a beat back into the plain narrative consumed by simulation."""
    text = (beat.get("text") or "").strip()
    if beat.get("speaker"):
        return f"{beat['speaker']}：{text}"
    return text


def beats_to_prose(beats: list[dict]) -> str:
    return "\n\n".join(filter(None, (beat_to_prose(beat) for beat in beats))).strip()
