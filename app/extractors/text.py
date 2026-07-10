import re

_ws_run = re.compile(r"[ \t]+")
_nl_run = re.compile(r"\n{3,}")


def normalize(text: str) -> str:
    """Trim, collapse whitespace runs, cap consecutive blank lines."""
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = _ws_run.sub(" ", t)
    t = _nl_run.sub("\n\n", t)
    return t.strip()
