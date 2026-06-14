_last = {"in": 0, "out": 0}


def record(in_tokens: int, out_tokens: int):
    _last["in"] = in_tokens
    _last["out"] = out_tokens


def get() -> tuple[int, int]:
    return _last["in"], _last["out"]
