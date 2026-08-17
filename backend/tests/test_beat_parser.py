from app.beat_parser import BeatStreamParser, beats_to_prose


def test_parser_handles_arbitrary_chunk_boundaries():
    parser = BeatStreamParser()
    chunks = [
        '<beat type="dia',
        'logue" speaker="苏晴">不要',
        '开灯。</beat>\n<beat type="narration">她走到窗边。</beat>',
    ]
    beats = []
    for chunk in chunks:
        beats.extend(parser.feed(chunk))
    beats.extend(parser.finish())
    assert beats == [
        {"type": "dialogue", "speaker": "苏晴", "text": "不要开灯。"},
        {"type": "narration", "speaker": None, "text": "她走到窗边。"},
    ]


def test_parser_soft_falls_back_when_no_beat_is_present():
    parser = BeatStreamParser()
    parser.feed("雨水越来越大，苏晴走到窗边。\n")
    assert parser.finish() == [{
        "type": "narration", "speaker": None,
        "text": "雨水越来越大，苏晴走到窗边。",
    }]


def test_invalid_lines_after_valid_beats_are_preserved_as_narration():
    parser = BeatStreamParser()
    beats = parser.feed('<beat type="narration">先观察。</beat>\n')
    beats += parser.feed("模型多说了一句。\n")
    beats += parser.finish()
    assert beats == [
        {"type": "narration", "speaker": None, "text": "先观察。"},
        {"type": "narration", "speaker": None, "text": "模型多说了一句。"},
    ]


def test_beats_render_back_to_simulation_narrative():
    assert beats_to_prose([
        {"type": "narration", "speaker": None, "text": "她抬头。"},
        {"type": "dialogue", "speaker": "苏晴", "text": "不要开灯。"},
    ]) == "她抬头。\n\n苏晴：不要开灯。"
