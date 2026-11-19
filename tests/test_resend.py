import os

from gighunter import digest

CFG = {"provider": "auto", "to": "me@example.com", "from_name": "gigHunter", "smtp_host": "h", "smtp_port": 465}


class _Resp:
    def __init__(self, code, body=None):
        self.status_code, self._b, self.text = code, body or {}, str(body)

    def json(self):
        return self._b


def _with_env(**env):
    saved = {k: os.environ.pop(k, None) for k in ["RESEND_API_KEY", "EMAIL_TO", "SMTP_USER", "SMTP_PASSWORD"]}
    os.environ.update(env)
    return saved


def _restore(saved):
    for k, v in saved.items():
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v


def test_auto_picks_resend_only_when_key_present():
    s = _with_env(RESEND_API_KEY="re_x")
    try:
        assert digest.provider(CFG) == "resend"
    finally:
        _restore(s)
    s = _with_env()
    try:
        assert digest.provider(CFG) == "smtp"
    finally:
        _restore(s)


def test_resend_request_shape(monkeypatch):
    import requests
    sent = {}
    monkeypatch.setattr(requests, "post", lambda url, **kw: sent.update(url=url, **kw) or _Resp(200, {"id": "1"}))
    s = _with_env(RESEND_API_KEY="re_test")
    try:
        digest.send("Subj", "<b>hi</b>", "hi", CFG)
    finally:
        _restore(s)
    assert sent["url"] == digest.RESEND_URL
    assert sent["headers"]["Authorization"] == "Bearer re_test"
    assert sent["json"]["to"] == ["me@example.com"] and sent["json"]["from"] == "gigHunter <onboarding@resend.dev>"


def test_resend_403_explains_recipient_rule(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "post", lambda url, **kw: _Resp(403, {"message": "You can only send testing emails to your own email address"}))
    s = _with_env(RESEND_API_KEY="re_test")
    try:
        digest.send("S", "h", "t", CFG)
    except SystemExit as e:
        assert "Resend account email" in str(e)
    else:
        raise AssertionError("expected SystemExit")
    finally:
        _restore(s)


def test_resend_needs_a_recipient():
    s = _with_env(RESEND_API_KEY="re_test")
    try:
        digest.send("S", "h", "t", {**CFG, "to": ""})
    except SystemExit as e:
        assert "email.to" in str(e)
    else:
        raise AssertionError("expected SystemExit")
    finally:
        _restore(s)
