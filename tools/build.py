#!/usr/bin/env python3
"""Build data for The Last 100 dashboards.

Usage:
  python3 build.py --checkins checkins.csv --signups signups.csv [--signups more.csv]
                   [--overrides overrides.json] [--now 2026-10-08T23:00]
                   --admin-html admin.html --public-html public.html

Reads the check-in sheet export and sign-up exports, works out every
participant's start date and logged dates, and writes the data into the
<script id="last100-data"> block of each page (admin gets contact details,
public gets names and dates only).
"""
import argparse, csv, json, re, datetime as dt
from collections import defaultdict

ORIGINAL_START = dt.date(2026, 9, 30)
EARLIEST_START = dt.date(2026, 9, 23)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
PILLARS = [("Move", "M"), ("Reset", "R"), ("Nourish", "N"), ("Drop", "D")]


def phone10(raw):
    d = re.sub(r"\D", "", raw or "")
    return d[-10:] if len(d) >= 10 else d


def intl(raw):
    d = re.sub(r"\D", "", raw or "")
    if len(d) == 10:
        return "91" + d
    if len(d) == 11 and d.startswith("0"):
        return "91" + d[1:]
    return d


def tidy(name):
    name = re.sub(r"\s+", " ", (name or "").strip()).strip(" .")
    name = re.sub(r"\(\s*", "(", name)
    name = re.sub(r"\s*\)", ")", name)
    if not name:
        return ""
    def cap(w):
        if w.startswith("("):
            return "(" + cap(w[1:])
        if len(w) <= 3 and w.isupper() and w.isalpha() and w not in ("HR",):
            return w.capitalize() if len(w) > 2 else w
        return w[:1].upper() + w[1:].lower() if (w.isupper() or w.islower()) else w
    return " ".join(cap(w) for w in name.split(" "))


def parse_day(s):
    s = (s or "").strip()
    for fmt in ("%d %B %Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def load_signups(paths):
    people = {}
    for p in paths:
        rows = read_csv(p)
        head = rows[0]
        idx = {h: i for i, h in enumerate(head) if h not in ("",)}
        def g(r, k):
            i = idx.get(k)
            return r[i].strip() if i is not None and i < len(r) else ""
        for r in rows[1:]:
            if not any(c.strip() for c in r):
                continue
            ph = phone10(g(r, "Whatsapp"))
            if not ph:
                continue
            day_one = parse_day(g(r, "Day One"))
            submitted = g(r, "Submitted At")[:10]
            cur = people.setdefault(ph, {
                "id": ph, "name": "", "phone": intl(g(r, "Whatsapp")),
                "email": "", "sport": "", "drop": "", "experience": "",
                "instagram": "", "dayOnes": [], "original": False,
                "signedUp": submitted, "source": "signup",
            })
            nm = tidy(g(r, "Name"))
            if len(nm) > len(cur["name"]):
                cur["name"] = nm
            for k, col in (("email", "Email"), ("sport", "Sport"), ("drop", "Giving Up"),
                           ("experience", "Running Experience"), ("instagram", "Instagram")):
                v = g(r, col)
                if v and not cur[k]:
                    cur[k] = v
            if g(r, "Whatsapp").strip().startswith("+") and len(re.sub(r"\D", "", g(r, "Whatsapp"))) > 10:
                cur["phone"] = intl(g(r, "Whatsapp"))
            if day_one:
                cur["dayOnes"].append(day_one)
            else:
                cur["original"] = True
            if submitted and (not cur["signedUp"] or submitted < cur["signedUp"]):
                cur["signedUp"] = submitted
    return people


def load_checkins(path):
    rows = read_csv(path)
    head = rows[0]
    out = []
    for r in rows[1:]:
        if len(r) < 4 or not r[0].strip():
            continue
        ts = dt.datetime.strptime(r[0].strip(), "%m/%d/%Y %H:%M:%S")
        which = (r[3] or "").strip().lower()
        text = r[4] if len(r) > 4 else ""
        pillars = "".join(code for word, code in PILLARS if word.lower() in text.lower())
        out.append({"ts": ts, "name": tidy(r[1]), "phone": r[2], "id": phone10(r[2]),
                    "which": which, "pillars": pillars})
    out.sort(key=lambda x: x["ts"])
    return out


def build(args):
    people = load_signups(args.signups)
    checkins = load_checkins(args.checkins)
    overrides = {}
    if args.overrides:
        try:
            overrides = json.load(open(args.overrides))
        except Exception:
            overrides = {}

    # resolve links (a check-in phone that belongs to another person)
    link = {k: v.get("linkTo") for k, v in overrides.items() if v.get("linkTo")}

    logs = defaultdict(dict)  # id -> {date: pillars}
    checkin_names = defaultdict(set)
    checkin_phone = {}
    for c in checkins:
        pid = link.get(c["id"], c["id"])
        day = c["ts"].date()
        if c["which"].startswith("yester"):
            day -= dt.timedelta(days=1)
        elif c["ts"].hour < 3 and (day - dt.timedelta(days=1)) not in logs[pid]:
            # a "Today" logged just after midnight almost always means the day before
            day -= dt.timedelta(days=1)
        prev = logs[pid].get(day, "")
        logs[pid][day] = "".join(sorted(set(prev + c["pillars"]), key="MRND".index))
        checkin_names[pid].add(c["name"])
        checkin_phone.setdefault(pid, c["phone"])

    # people who check in but never appear in the sign-up export
    for pid in logs:
        if pid not in people:
            nm = max(checkin_names[pid], key=len) if checkin_names[pid] else "Unknown"
            people[pid] = {"id": pid, "name": nm, "phone": intl(checkin_phone.get(pid, "")),
                           "email": "", "sport": "", "drop": "", "experience": "",
                           "instagram": "", "dayOnes": [], "original": False,
                           "signedUp": "", "source": "checkin-only"}

    result = []
    for pid, p in people.items():
        if pid in link:  # merged into another person
            continue
        dates = sorted(logs.get(pid, {}))
        first = dates[0] if dates else None
        if p["original"] or not p["dayOnes"]:
            start = ORIGINAL_START
            if p["source"] == "checkin-only" and first and first > ORIGINAL_START:
                start = first
        else:
            start = min(p["dayOnes"])
        ov = overrides.get(pid, {})
        if ov.get("startDate"):
            start = dt.date.fromisoformat(ov["startDate"])
        extra = [dt.date.fromisoformat(d) for d in ov.get("extraDates", []) if d]
        day_map = dict(logs.get(pid, {}))
        for d in extra:
            day_map.setdefault(d, "MRND")
        end = start + dt.timedelta(days=99)
        in_window = {d: v for d, v in day_map.items() if start <= d <= end}
        early = sorted(d.isoformat() for d in day_map if EARLIEST_START <= d < start)
        result.append({
            "id": pid,
            "name": p["name"] or "Unknown",
            "phone": p["phone"],
            "email": p["email"],
            "sport": p["sport"],
            "drop": p["drop"],
            "experience": p["experience"],
            "instagram": p["instagram"],
            "signedUp": p["signedUp"],
            "source": p["source"],
            "start": start.isoformat(),
            "days": {d.isoformat(): v for d, v in sorted(in_window.items())},
            "early": early,
            "manual": sorted(d.isoformat() for d in extra),
            "aliases": sorted(n for n in checkin_names.get(pid, set()) if n and n != p["name"]),
        })
    result.sort(key=lambda x: x["name"].lower())

    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now(IST).replace(tzinfo=None)
    meta = {"generatedAt": now.strftime("%Y-%m-%dT%H:%M"), "rows": len(checkins)}
    admin = {"meta": meta, "people": result}
    public = {"meta": meta, "people": [
        {"id": f"p{i}", "name": x["name"], "start": x["start"], "days": sorted(x["days"]), "early": x["early"]}
        for i, x in enumerate(result)
    ]}
    return admin, public


def inject(path, data):
    html = open(path, encoding="utf-8").read()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    new, n = re.subn(r'(<script id="last100-data" type="application/json">)(.*?)(</script>)',
                     lambda m: m.group(1) + blob + m.group(3), html, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f"data block not found in {path}")
    open(path, "w", encoding="utf-8").write(new)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkins", required=True)
    ap.add_argument("--signups", action="append", required=True)
    ap.add_argument("--overrides")
    ap.add_argument("--now")
    ap.add_argument("--admin-html")
    ap.add_argument("--public-html")
    ap.add_argument("--dump")
    a = ap.parse_args()
    admin, public = build(a)
    if a.admin_html:
        inject(a.admin_html, admin)
    if a.public_html:
        inject(a.public_html, public)
    if a.dump:
        json.dump(admin, open(a.dump, "w"), indent=1, ensure_ascii=False)
    print(f"people={len(admin['people'])} checkin_rows={admin['meta']['rows']} at={admin['meta']['generatedAt']}")
