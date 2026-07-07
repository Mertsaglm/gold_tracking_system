"""GitHub Actions secrets'larını API + pynacl ile ekler (gh kurulu değil).

Token scratchpad'ten okunur; secret değerleri .env'den. Değerler ASLA yazdırılmaz.
Kullanım: python scripts/set_secrets.py <token_dosyasi>
"""
import base64
import json
import sys
import urllib.request

from nacl import encoding, public

REPO = "Mertsaglm/gold_tracking_system"
SECRETS = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "EVDS_API_KEY"]


def _api(path, token, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}/{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "altin-secrets")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, (json.loads(r.read()) if r.length != 0 and method == "GET" else None)


def _encrypt(pubkey_b64, secret_value):
    pk = public.PublicKey(pubkey_b64.encode(), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(secret_value.encode())
    return base64.b64encode(sealed).decode()


def main():
    token = open(sys.argv[1], encoding="utf-8").read().strip()
    # .env oku
    env = {}
    for line in open(".env", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

    _, key = _api("actions/secrets/public-key", token)
    key_id, pubkey = key["key_id"], key["key"]

    for name in SECRETS:
        val = env.get(name)
        if not val:
            print(f"  ATLANDI {name}: .env'de yok")
            continue
        enc = _encrypt(pubkey, val)
        status, _ = _api(f"actions/secrets/{name}", token, method="PUT",
                         data={"encrypted_value": enc, "key_id": key_id})
        print(f"  {name}: PUT HTTP {status}")

    # listele (sadece isimler)
    _, lst = _api("actions/secrets", token)
    print("Repodaki secret isimleri:", [s["name"] for s in lst.get("secrets", [])])


if __name__ == "__main__":
    main()
