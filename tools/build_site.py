"""Add or refresh the encrypted progress board inside the findyourultra.in index.html.

python3 tools/build_site.py index.html <admin page with data block> tools/progress_snippet.html index.html
Safe to run repeatedly: it replaces the previous board each time.
"""
import sys, re, json, os, base64, hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

src, admin, snip, out = sys.argv[1:5]
SALT, ITER = "the-last-100/v1", 150000
b64 = lambda b: base64.b64encode(b).decode()

a = open(admin, encoding="utf-8").read()
data = json.loads(re.search(r'<script id="last100-data" type="application/json">(.*?)</script>', a, re.S).group(1).replace("<\\/", "</"))
gen = data["meta"]["generatedAt"]
people, ids, recs = [], [], []
st = {"people": 0, "days": 0, "moveMin": 0, "resetMin": 0, "meals": 0, "drop": 0, "smoke": 0, "sugar": 0, "alcohol": 0}
for p in data["people"]:
    pid = re.sub(r"\D", "", p["id"])[-10:]
    if len(pid) != 10:
        continue
    manual = set(p.get("manual") or [])
    recs.append({"name": p["name"], "start": p["start"],
                 "days": sorted(d for d in p["days"] if d not in manual),
                 "manual": sorted(manual)})
    ids.append(pid)
    st["people"] += 1
    drop = (p.get("drop") or "").lower()
    for d, v in p["days"].items():
        v = v or ""
        st["days"] += 1
        st["moveMin"] += 20 * ("M" in v)
        st["resetMin"] += 5 * ("R" in v)
        st["meals"] += ("N" in v)
        if "D" in v:
            st["drop"] += 1
            st["smoke"] += bool(re.search(r"smok|cigar|cigg|tobacco", drop))
            st["sugar"] += bool(re.search(r"sugar|sweet|mithai|dessert", drop))
            st["alcohol"] += bool(re.search(r"alcohol|drink|booze|beer", drop))

keys = {}
for rec, pid in zip(recs, ids):
    bits = hashlib.pbkdf2_hmac("sha256", pid.encode(), SALT.encode(), ITER, 48)
    iv = os.urandom(12)
    keys[bits[:16].hex()] = [b64(iv), b64(AESGCM(bits[16:48]).encrypt(iv, json.dumps(rec, ensure_ascii=False, separators=(",", ":")).encode(), None))]

h, m = map(int, gen[11:16].split(":"))
asOfTime = f"{(h % 12) or 12}:{m:02d} {'am' if h < 12 else 'pm'}"
D = {"salt": SALT, "iter": ITER, "asOf": gen[:10], "asOfTime": asOfTime, "keys": keys, "stats": st,
     "formKey": "870cb139-8593-4bd4-934e-5b8db3bce18c"}
snippet = open(snip, encoding="utf-8").read().replace("__L100X_DATA__", json.dumps(D, separators=(",", ":")))

s = open(src, encoding="utf-8").read()
A = '<script type="__bundler/template">'
a0 = s.index(A) + len(A); a1 = s.index("</script>", a0)
t = json.loads(s[a0:a1])

# idempotent: drop any earlier injection, then add the current one
t = re.sub(r"<!--L100X-START-->.*?<!--L100X-END-->\n?", "", t, flags=re.S)
NAV = ('\n        <a href="#progress" style="color:#121212" style-hover="color:#4E6C1D">My progress</a>'
       '\n        <a href="#invite" style="color:#121212" style-hover="color:#4E6C1D">Invite</a>')
nav_anchor = '>Check in</a>'
if NAV not in t:
    assert t.count(nav_anchor) == 1, "Check in nav link not found"
    t = t.replace(nav_anchor, nav_anchor + NAV, 1)
assert t.rstrip().endswith("</body></html>")
i = t.rindex("</body>")
t = t[:i] + "<!--L100X-START-->" + snippet + "<!--L100X-END-->\n" + t[i:]

enc = "\n" + json.dumps(t).replace("</", "<\\u002F") + "\n  "
s = s[:a0] + enc + s[a1:]
open(out, "w", encoding="utf-8").write(s)
print(f"people={len(recs)} keys={len(keys)} asOf={gen} size={len(s)} stats={st}")
