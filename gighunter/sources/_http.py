import requests

HEADERS = {"User-Agent": "gigHunter/0.1 (personal job digest)"}


def get_json(url: str, **params):
    r = requests.get(url, headers=HEADERS, params=params or None, timeout=30)
    r.raise_for_status()
    return r.json()


def get_text(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text
