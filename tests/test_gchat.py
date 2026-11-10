import pytest

from app.notify import gchat

VALID = "https://chat.googleapis.com/v1/spaces/AAAAbc_12-x/messages?key=abc&token=def"


def test_space_of_accepts_only_google_chat_webhooks():
    assert gchat.space_of(VALID) == "AAAAbc_12-x"
    assert gchat.space_of("  " + VALID + " ") == "AAAAbc_12-x"
    for bad in (None, "", "http://chat.googleapis.com/v1/spaces/A/messages?key=1",
                "https://chat.googleapis.com.evil.com/v1/spaces/A/messages?key=1",
                "https://example.com/v1/spaces/A/messages?key=1", "https://chat.googleapis.com/v1/spaces/A/messages"):
        assert gchat.space_of(bad) is None


def test_send_rejects_invalid_url_without_network():
    with pytest.raises(gchat.SendError):
        gchat.send("https://example.com/hook", "hi")


def test_truncate_keeps_whole_lines():
    text = "\n".join(f"dòng {i} " + "x" * 50 for i in range(200))
    out = gchat.truncate(text)
    assert len(out) <= gchat.MAX_TEXT and out.endswith("xem đủ trên web app)")
    assert gchat.truncate("ngắn") == "ngắn"
