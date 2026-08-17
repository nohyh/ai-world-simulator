from app.db import Database
from app.routes import WorldCreate, _auto_title


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
