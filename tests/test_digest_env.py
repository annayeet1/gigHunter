import os


from gighunter import digest

NAMES = ["SMTP_USER", "SMTP_PASSWORD", "SMTP_TO", "GMAIL_USER", "GMAIL_APP_PASSWORD", "GMAIL_TO"]


class _Env:
    def __init__(self, **vals):
        self.vals = vals

    def __enter__(self):
        self.saved = {n: os.environ.pop(n, None) for n in NAMES}
        os.environ.update(self.vals)

    def __exit__(self, *exc):
        for n in NAMES:
            os.environ.pop(n, None)
            if self.saved[n] is not None:
                os.environ[n] = self.saved[n]


def test_new_names():
    with _Env(SMTP_USER="a@x.com", SMTP_PASSWORD="p", SMTP_TO="b@x.com"):
        assert digest.credentials() == ("a@x.com", "p") and digest.smtp_env("to") == "b@x.com"


def test_legacy_gmail_names_still_work():
    with _Env(GMAIL_USER="old@x.com", GMAIL_APP_PASSWORD="q"):
        assert digest.credentials() == ("old@x.com", "q") and digest.smtp_env("to") is None


def test_new_names_win_over_legacy():
    with _Env(SMTP_USER="new@x.com", SMTP_PASSWORD="n", GMAIL_USER="old@x.com", GMAIL_APP_PASSWORD="o"):
        assert digest.credentials() == ("new@x.com", "n")


def test_missing_credentials_is_a_clear_error():
    with _Env():
        try:
            digest.credentials()
        except SystemExit as e:
            assert "SMTP_USER" in str(e)
        else:
            raise AssertionError("expected SystemExit")
