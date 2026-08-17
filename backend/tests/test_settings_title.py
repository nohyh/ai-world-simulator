from app.db import Database
from datetime import datetime

from app.routes import WorldCreate, _auto_title, _infer_player_fields, _normalize_start_time


def test_settings_roundtrip(tmp_path):
    db = Database(tmp_path / "s.db")
    assert db.get_settings() == {}
    db.set_settings({"provider": "mock", "api_key": "", "model": "m"})
    assert db.get_settings()["provider"] == "mock"
    db.set_settings({"provider": "deepseek", "api_key": "sk-x", "model": "deepseek-chat"})
    assert db.get_settings()["api_key"] == "sk-x"


def test_auto_title():
    def wc(title="", setting=""):
        return WorldCreate(title=title, world_setting=setting)

    assert _auto_title(wc(title=" 我的末日世界 ", setting="随便")) == "我的末日世界"
    assert _auto_title(wc(setting="2041年，大崩坏后的第十年。\n文明退回据点时代")) == "2041年，大崩坏后的第十年"
    assert _auto_title(wc(setting="短")) == "短"
    assert _auto_title(wc(setting="很短的一句话")) == "很短的一句话"
    # 空行跳过，取第一行有效内容
    assert _auto_title(wc(setting="\n\n   \n第二行世界")) == "第二行世界"
    # 全空回退
    assert _auto_title(wc(setting="。。。")) in ("新世界", "。")


def test_player_description_infers_name_and_identity():
    assert _infer_player_fields("林默，23岁，避难所侦察员，擅长追踪。") == (
        "林默", "避难所侦察员")


def test_empty_start_time_is_materialized_once():
    value = _normalize_start_time("")
    parsed = datetime.fromisoformat(value)
    assert parsed.second == 0 and parsed.microsecond == 0
    assert _normalize_start_time("2041年7月16日 08:00") == "2041年7月16日 08:00"
