"""Streaming parser for the narrator's semantic beat protocol."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET


_FENCE_RE = re.compile(r"^\s*```(?:xml|html)?\s*$", re.IGNORECASE)


def _narration(text: str) -> dict:
    return {"type": "narration", "speaker": None, "text": text.strip()}


def _parse_line(line: str) -> dict | None:
    candidate = line.strip()
    if not candidate or _FENCE_RE.match(candidate):
        return None
    try:
        element = ET.fromstring(candidate)
    except ET.ParseError:
        return None
    if element.tag != "beat":
        return None
    beat_type = (element.attrib.get("type") or "").strip().lower()
    text = html.unescape("".join(element.itertext())).strip()
    if beat_type not in {"narration", "dialogue"} or not text:
        return None
    speaker = (element.attrib.get("speaker") or "").strip() or None
    if beat_type == "dialogue" and not speaker:
        return None
    if beat_type == "narration":
        speaker = None
    return {"type": beat_type, "speaker": speaker, "text": text}


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
        if parsed is not None:
            out: list[dict] = []
            if self._pending_raw.strip():
                out.append(_narration(self._pending_raw))
                self._pending_raw = ""
            out.append(parsed)
            self._seen_valid_beat = True
            return out
        if raw_line.strip() and not _FENCE_RE.match(raw_line.strip()):
            if self._seen_valid_beat:
                return [_narration(raw_line)]
            self._pending_raw += raw_line
        return []


def beat_to_prose(beat: dict) -> str:
    """Render a beat back into the plain narrative consumed by simulation."""
    text = (beat.get("text") or "").strip()
    if beat.get("type") == "dialogue" and beat.get("speaker"):
        return f"{beat['speaker']}：{text}"
    return text


def beats_to_prose(beats: list[dict]) -> str:
    return "\n\n".join(filter(None, (beat_to_prose(beat) for beat in beats))).strip()
