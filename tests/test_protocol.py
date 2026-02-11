from xchat.protocol import decode_message, encode_message


def test_encode_decode_roundtrip() -> None:
    raw = encode_message("msg", "alice.onion", "hello")
    decoded = decode_message(raw.decode("utf-8").strip())
    assert decoded is not None
    assert decoded.kind == "msg"
    assert decoded.sender == "alice.onion"
    assert decoded.text == "hello"


def test_decode_rejects_invalid_payload() -> None:
    assert decode_message("{}") is None
    assert decode_message("not-json") is None
