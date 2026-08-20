#!/usr/bin/env python3
"""Static site generator for "Pražský semafor".

Reads data/projects/*.json, writes dist/ (multi-page site) and
dist/preview.html (single self-contained file for sharing/artifacts,
where cross-page links become in-page anchors).
"""
import html
import json
import re
import shutil
import unicodedata
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
CACHE = ROOT / "data" / "cache"

API = "https://praha.eu/o/prg"
TITLE_TOKENS = re.compile(r"\.|^(MBA|MSc|MA|et)$")
VOTE_ORDER = ["Pro", "Proti", "Zdržel se", "Nehlasoval", "Nepřítomen", "Chyběl", "Omluven"]
VOTE_SEG = {"Pro": "pro", "Proti": "proti", "Zdržel se": "zdrzel",
            "Nehlasoval": "ostatni", "Nepřítomen": "ostatni", "Chyběl": "ostatni",
            "Omluven": "ostatni"}
CLUB_COLORS = {
    "SPOLU pro Prahu": "#2B3E8C", "ODS": "#1A4FA0",
    "TOP 09 a STAN - Spojené síly pro Prahu": "#7B2D8B",
    "Piráti": "#1C1C1C", "PRAHA SOBĚ": "#F2C400", "ANO 2011": "#009FC7",
    "STAN": "#B83A66", "Zastupitelský klub SPD": "#33517E",
    "ODS (Praha 1)": "#1A4FA0", "TOP 09 (Praha 1)": "#7B2D8B",
    "P1 SOBĚ (Praha 1)": "#F2C400", "POP 1 (Praha 1)": "#1C1C1C",
    "LEVICE (Praha 1)": "#B02A2A", "REZIDENTI1 (Praha 1)": "#6B7B4A",
    "3koalice (Praha 1)": "#4C7C6C", "Naše P1 (Praha 1)": "#557088",
    "ČSSD": "#E8542F", "KSČM": "#B02A2A",
    "TOP 09 a nezávislých ": "#7B2D8B",
    "TROJKOALICE Zelení, KDU-ČSL, STAN": "#5B8C3E",
    "ODS (Praha 8)": "#1A4FA0", "ANO 2011 (Praha 8)": "#009FC7",
    "Česká pirátská strana (Praha 8)": "#1C1C1C",
    "8ŽIJE A PRAHA SOBĚ (Praha 8)": "#F2C400",
    "Společně pro Prahu 8 (Praha 8)": "#7B2D8B",
    "SPD a Trikolora pro Osmičku (Praha 8)": "#33517E",
}


DARK_TEXT_CLUBS = {"PRAHA SOBĚ", "P1 SOBĚ (Praha 1)", "8ŽIJE A PRAHA SOBĚ (Praha 8)"}


def club_color(name):
    return CLUB_COLORS.get(name, "var(--ink-3)")


def club_slug(name):
    base = actor_slug(name)
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def club_chip(name, link=False):
    text = "#1C2427" if name in DARK_TEXT_CLUBS else "#fff"
    chip_html = (f'<span class="club-chip" style="background:{club_color(name)};'
                 f'color:{text}">{esc(name)}</span>')
    if link:
        return f'<a class="chip-link" href="klub-{club_slug(name)}.html">{chip_html}</a>'
    return chip_html


def api_cached(name, url):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{name}.json"
    if f.exists():
        return json.loads(f.read_text())
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    f.write_text(json.dumps(data, ensure_ascii=False))
    return data


# Úřední exporty jména komolí: P8 vkládá vícenásobné mezery, P1 jména ořezává
# na pevnou šířku a u vícedílných jmen přehazuje pořadí.
NAME_FIXES = {
    "Adél Kučera": "Adéla Kučerová",
    "Clare Talacková Valerie": "Valerie Clare Talacková",
    "Bara Soukup": "Bára Soukupová",
}


def norm_name(name):
    name = " ".join(name.split())
    return NAME_FIXES.get(name, name)


def name_key(full_name):
    tokens = [t.strip(",") for t in full_name.split()]
    return frozenset(t for t in tokens if t and not TITLE_TOKENS.search(t))


def club_map(period):
    reps = api_cached(f"reps_{period}", f"{API}/representatives/period/{period}")
    return {name_key(r["fullName"]): (r.get("club") or {}).get("name") or "nezařazení"
            for r in reps}


def vote_roll(vote_id, period):
    roll = api_cached(f"roll_{vote_id}", f"{API}/voting/detail/{vote_id}/votes")
    clubs = club_map(period)
    for r in roll:
        r["club"] = clubs.get(name_key(r["memberFullName"]), "nezařazení")
        r["shortName"] = norm_name(" ".join(
            t.strip(",") for t in r["memberFullName"].split()
            if not TITLE_TOKENS.search(t)))
    return roll
# Po registraci domeny prepnout na https://prazskysemafor.cz (domena je volna)
SITE_URL = "https://petrdlouhy.github.io/prazsky-semafor"
SITE_NAME = "Pražský semafor"
TAGLINE = "hlídač pražských projektů a slibů"
FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%231C2427'/>"
           "<circle cx='16' cy='8' r='4' fill='%23E2685A'/>"
           "<circle cx='16' cy='16' r='4' fill='%23D9A94E'/>"
           "<circle cx='16' cy='24' r='4' fill='%234EC0B4'/></svg>")

TIER_LABELS = {"a": "úřední", "b": "média", "c": "tvrzení"}


def esc(s):
    return html.escape(s, quote=False)


def chip(status):
    return f'<span class="chip chip-{status["kind"]}">{esc(status["label"])}</span>'


def tier_chip(tier):
    return f'<span class="tier tier-{tier}">{TIER_LABELS[tier]}</span>'


def counter_days(since_iso):
    y, m, d = (int(x) for x in since_iso.split("-"))
    days = (date.today() - date(y, m, d)).days
    return f"{days:,}".replace(",", " ")


def page(title, body, nav_active, single_file=False, desc="", path=""):
    prefix = "#" if single_file else ""
    ext = "" if single_file else ".html"
    desc = desc or ("Hlídač pražských projektů: co si město schválilo, co skutečně "
                    "vzniklo a co se cestou změnilo. Spisy se zdroji a jmenovitými "
                    "hlasováními.")
    canonical = f"{SITE_URL}/{path}" if path and not single_file else ""
    head_meta = (
        f'<meta name="description" content="{esc(desc)[:300]}">\n'
        + (f'<link rel="canonical" href="{canonical}">\n' if canonical else "")
        + f'<meta property="og:title" content="{esc(title)} · {SITE_NAME}">\n'
        + f'<meta property="og:description" content="{esc(desc)[:300]}">\n'
        + '<meta property="og:type" content="website">\n'
        + f'<meta property="og:site_name" content="{SITE_NAME}">\n'
        + (f'<meta property="og:url" content="{canonical}">\n' if canonical else "")
        + '<meta property="og:locale" content="cs_CZ">\n'
        + f'<meta property="og:image" content="{SITE_URL}/og.png">\n'
        + '<meta property="og:image:width" content="1200">\n'
        + '<meta property="og:image:height" content="630">\n'
        + '<meta name="theme-color" content="#1C2427">\n'
        + f'<link rel="icon" href="{FAVICON}">')

    def nav_link(slug, label):
        on = ' class="on"' if slug == nav_active else ""
        return f'<a href="{prefix}{slug}{ext}"{on}>{label}</a>'

    nav = (nav_link("index", "Projekty") + nav_link("ramce", "Rámce")
           + nav_link("sliby", "Sliby") + nav_link("akteri", "Aktéři")
           + nav_link("metodika", "Metodika"))
    return f"""<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {SITE_NAME}</title>
{head_meta}
{'<style>' + (ROOT / 'static' / 'style.css').read_text() + '</style>' if single_file
 else '<link rel="stylesheet" href="style.css">'}
</head>
<body>
<div class="betabar">Pracovní verze · údaje před spuštěním projdou položkovým ověřením</div>
<header class="site"><div class="wrap site-inner">
  <a class="brand" href="{prefix}index{ext}">Pražský <em>semafor</em><small>{TAGLINE}</small></a>
  <nav class="top">{nav}</nav>
</div></header>
<main>{body}</main>
<footer class="site"><div class="wrap">
  <span class="mono">Zdroje jsou uvedeny u každé události · stav k {date.today().strftime('%-d. %-m. %Y')}</span>
</div></footer>
</body>
</html>"""


def actor_slug(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def render_event(ev, single_file=False):
    srcs = " · ".join(
        f'<a href="{html.escape(s["url"])}">{esc(s["label"])}</a>' for s in ev["sources"]
    )
    actors = ""
    if ev.get("actors"):
        prefix = "#akter-" if single_file else "osoba-"
        suffix = "" if single_file else ".html"
        links = ", ".join(
            f'<a href="{prefix}{actor_slug(a["name"])}{suffix}">{esc(a["name"])}</a>'
            f' ({esc(a["role"])})'
            for a in ev["actors"]
        )
        actors = f'<p class="src">aktéři: {links}</p>'
    return f"""<li>
  <div class="when">{esc(ev["date"])}</div>
  <div class="what">
    <h4>{esc(ev["title"])} {tier_chip(ev["tier"])}{f' <span class="chip chip-muted">{esc(ev["thread"])}</span>' if ev.get("thread") else ""}</h4>
    <p>{esc(ev["text"])}</p>
    {render_vote(ev, single_file)}
    {render_promise_line(ev)}
    <p class="src">{srcs}</p>
    {actors}
  </div>
</li>"""


PROMISE_CHIP = {"nesplněno": "miss", "běží": "wait", "splněno": "ok",
                "v opozici": "muted", "kampaň 2026": "wait", "neuskutečněno": "miss",
                "nesplněno, příprava běží": "wait", "částečně": "muted"}


def render_promise_line(ev):
    pr = ev.get("promise")
    if not pr:
        return ""
    due = f' · termín: {esc(pr["due"])}' if pr.get("due") else ""
    kind = PROMISE_CHIP.get(pr["status"], "muted")
    return (f'<p class="src">závazek{due} · '
            f'<span class="chip chip-{kind}">{esc(pr["status"])}</span></p>')


def seg_counts(roll):
    counts = {"pro": 0, "proti": 0, "zdrzel": 0, "ostatni": 0}
    for r in roll:
        counts[VOTE_SEG.get(r["voteText"], "ostatni")] += 1
    return counts


def render_bar(counts, height=26, label=""):
    total = sum(counts.values()) or 1
    seg = "".join(
        f'<div class="seg seg-{key}" style="width:{100 * counts[key] / total:.1f}%" '
        f'title="{name}: {counts[key]}"></div>'
        for key, name in
        [("pro", "Pro"), ("proti", "Proti"), ("zdrzel", "Zdržel se"),
         ("ostatni", "Nehlasoval / nepřítomen")] if counts[key]
    )
    aria = (f'{label}: {counts["pro"]} pro, {counts["proti"]} proti, '
            f'{counts["zdrzel"]} se zdrželo, {counts["ostatni"]} ostatní')
    return (f'<div class="votebar" style="height:{height}px" role="img" '
            f'aria-label="{esc(aria)}">{seg}</div>')


def person_link(short_name, single_file):
    if single_file:
        return esc(short_name)
    return f'<a href="osoba-{actor_slug(short_name)}.html">{esc(short_name)}</a>'


def render_roll_details(roll, single_file=False):
    by_club = {}
    for r in roll:
        by_club.setdefault(r["club"], []).append(r)
    blocks = []
    for club, members in sorted(by_club.items(), key=lambda kv: -len(kv[1])):
        counts = seg_counts(members)
        groups = []
        for vt in VOTE_ORDER:
            names = sorted(m["shortName"] for m in members if m["voteText"] == vt)
            if names:
                links = ", ".join(person_link(n, single_file) for n in names)
                groups.append(
                    f'<p class="roll-group"><span class="swatch seg-{VOTE_SEG[vt]}"></span>'
                    f'<b>{vt.lower()} ({len(names)}):</b> {links}</p>')
        blocks.append(f"""<div class="club-block" style="border-left-color:{club_color(club)}">
  <h5>{club_chip(club, link=not single_file)}
  <span class="mono club-n">{len(members)}</span></h5>
  {render_bar(counts, height=12)}
  {"".join(groups)}
</div>""")
    return f"""<details class="roll">
  <summary>Jak hlasovaly kluby a jednotlivci</summary>
  <div class="clubs">{"".join(blocks)}</div>
</details>"""


def render_vote(ev, single_file=False):
    v = ev.get("vote")
    if not v:
        return ""
    roll = ev.get("_roll")
    counts = seg_counts(roll) if roll else {
        "pro": v["pro"], "proti": v["proti"],
        "zdrzel": v["zdrzel"], "ostatni": v["ostatni"]}
    key_items = "".join(
        f'<li><span class="swatch seg-{key}"></span><b>{counts[key]}</b> {label}</li>'
        for key, label in
        [("pro", "pro"), ("proti", "proti"), ("zdrzel", "zdrželo se"),
         ("ostatni", "nehlasovalo / chybělo")]
    )
    details = render_roll_details(roll, single_file) if roll else ""
    caveat = ""
    if v.get("kind") == "zarazeni":
        caveat = ('<p class="src">poznámka: hlasování o zařazení bodu na program '
                  'vypovídá o ochotě jednat, ne nutně o postoji k projektu</p>')
    return f"""<div class="votewrap">
  <p class="src" style="margin-bottom:.35rem">{esc(v["label"])} · výsledek: {esc(v["vysledek"])}</p>
  {render_bar(counts, label=v["label"])}
  <ul class="votekey">{key_items}</ul>
  {caveat}
  {details}
</div>"""


def render_promises_body(projects, single_file=False):
    prefix = "#" if single_file else ""
    ext = "" if single_file else ".html"
    rows = []
    for p in projects:
        for ev in p["events"]:
            pr = ev.get("promise")
            if not pr:
                continue
            who = pr.get("by") or ", ".join(a["name"] for a in ev.get("actors", []))
            kind = PROMISE_CHIP.get(pr["status"], "muted")
            year = int(next(iter(re.findall(r"\d{4}", pr["promised"])), 9999))
            text = f'{esc(pr["text"])}<br>' if pr.get("text") else ""
            rows.append((year, f"""<tr>
  <td>{esc(pr["promised"])}</td>
  <td><b>{esc(who)}</b><br>
      {text}<span class="src">kontext: <a href="{prefix}{p["slug"]}{ext}">{esc(p["title"])}</a>: {esc(ev["title"])}</span></td>
  <td>{esc(pr.get("due") or "bez termínu")}</td>
  <td><span class="chip chip-{kind}">{esc(pr["status"])}</span></td>
</tr>"""))
    rows = [h for _, h in sorted(rows, key=lambda r: r[0])]

    doc_promises = json.loads((ROOT / "data" / "promises.json").read_text())
    prefix2 = "#" if single_file else ""
    ext2 = "" if single_file else ".html"
    slug_to_title = {p["slug"]: p["title"] for p in projects}
    doc_rows = []
    for pr in doc_promises:
        kind = PROMISE_CHIP.get(pr["status"], "muted")
        proj = ""
        if pr.get("project") and pr["project"] in slug_to_title:
            proj = (f'<br><a href="{prefix2}{pr["project"]}{ext2}">'
                    f'{esc(slug_to_title[pr["project"]])}</a>')
        doc_rows.append(f"""<tr>
  <td>{esc(pr["year"])}<br><span class="src mono">{esc(pr["type"])}</span></td>
  <td><b>{esc(pr["who"])}</b><br>„{esc(pr["quote"])}“
      <br><a class="src" href="{html.escape(pr["source"]["url"])}">{esc(pr["source"]["label"])}</a>{proj}</td>
  <td><span class="chip chip-{kind}">{esc(pr["status"])}</span>{f'<br><span class="src">{esc(pr["note"])}</span>' if pr.get("note") else ""}{f'<br><span class="src posun">reálný posun: {esc(pr["posun"])}</span>' if pr.get("posun") else ""}</td>
</tr>""")
    doc_section = f"""<h2 class="sec">Programy a koaliční dokumenty</h2>
  <p class="sec-lead" style="margin-bottom:1rem">Doslovné sliby z volebních
  programů a koaličních dokumentů. Sliby stran, které skončily v opozici,
  neznámkujeme jako nesplněné: označujeme je „v opozici“; plnit je nebylo
  v jejich moci.</p>
  <table class="votes promises">
    <thead><tr><th>Kdy</th><th>Kdo a co slíbil</th><th>Stav</th></tr></thead>
    <tbody>{"".join(doc_rows)}</tbody>
  </table>"""

    anchor = ' id="sliby"' if single_file else ""
    return f"""<div class="wrap"{anchor}>
  <p class="crumb">Závazky</p>
  <h1 class="page">Sliby a jejich osud</h1>
  <p class="page-lead">Veřejné závazky z událostí spisů: kdo je dal, dokdy měly
  být splněny a jak dopadly. Řadíme chronologicky; každý závazek vede na
  kontext ve svém spisu.</p>
  <table class="votes promises">
    <thead><tr><th>Kdy</th><th>Kdo a co</th><th>Termín</th><th>Stav</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  {doc_section}
</div>"""


def render_actors_body(projects, single_file=False, persons_index=None):
    by_actor = {}
    for p in projects:
        for ev in p["events"]:
            for a in ev.get("actors", []):
                entry = by_actor.setdefault(a["name"], {"roles": set(), "events": []})
                entry["roles"].add(a["role"])
                entry["events"].append((p, ev))

    prefix = "#" if single_file else ""
    ext = "" if single_file else ".html"
    rows = []
    for name in sorted(by_actor, key=lambda n: n.split()[-1]):
        entry = by_actor[name]
        events = "".join(
            f'<tr><td>{esc(ev["date"])}</td>'
            f'<td><a href="{prefix}{p["slug"]}{ext}">{esc(p["title"])}</a>: '
            f'{esc(ev["title"])}</td></tr>'
            for p, ev in sorted(entry["events"],
                                key=lambda x: event_sort_key(x[1]["date"]))
        )
        role_parts = []
        for r in entry["roles"]:
            for part in r.split("; "):
                if part not in role_parts:
                    role_parts.append(part)
        roles = " · ".join(role_parts)
        name_html = (esc(name) if single_file
                     else f'<a href="osoba-{actor_slug(name)}.html">{esc(name)}</a>')
        rows.append(f"""<div class="part" id="akter-{actor_slug(name)}">
  <h3>{name_html}</h3>
  <p class="src" style="margin-bottom:.6rem">{esc(roles)}</p>
  <table class="votes"><tbody>{events}</tbody></table>
</div>""")
    anchor = ' id="akteri"' if single_file else ""
    index = ""
    if persons_index and not single_file:
        links = " · ".join(
            f'<a href="osoba-{slug}.html">{esc(p["name"])}</a>'
            for slug, p in sorted(persons_index.items(),
                                  key=lambda kv: kv[1]["name"].split()[-1]))
        index = (f'<h2 class="sec">Rejstřík všech osob ve sledovaných '
                 f'hlasováních ({len(persons_index)})</h2>'
                 f'<p style="font-size:.9rem; color:var(--ink-2)">{links}</p>')
    return f"""<div class="wrap"{anchor}>
  <p class="crumb">Aktéři</p>
  <h1 class="page">Kdo ve spisech vystupuje</h1>
  <p class="page-lead">Nahoře osoby doložené v událostech spisů; níže úplný
  rejstřík všech, kdo se objevují ve sledovaných jmenovitých hlasováních.
  Jména i kluby jsou proklikávací.</p>
  {"".join(rows)}
  {index}
</div>"""


ELECTIONS = [(2010, 10, 16), (2014, 10, 11), (2018, 10, 6), (2022, 9, 24)]

PERIOD_LABELS = {-36525: "2022–2026", -33394: "2018–2022", -29783: "2014–2018"}
MC_BODIES = {"p1": "Zastupitelstvo MČ Praha 1", "p8": "Zastupitelstvo MČ Praha 8"}


def mc_mandate(roll_file):
    prefix, y, m, d = roll_file.split("-")[0], *[int(x) for x in roll_file.split("-")[1:4]]
    start = max(ey for ey, em, ed in ELECTIONS if (ey, em, ed) <= (y, m, d))
    return (MC_BODIES[prefix], f"{start}–{start + 4}")


def event_sort_key(d):
    m = re.search(r"(\d{4})", d)
    year = int(m.group(1)) if m else 0
    m2 = re.match(r"(\d{1,2})\. (\d{1,2})\. \d{4}", d)
    if m2:
        return (year, int(m2.group(2)), int(m2.group(1)))
    months = {"leden": 1, "únor": 2, "březen": 3, "duben": 4, "květen": 5,
              "červen": 6, "červenec": 7, "srpen": 8, "září": 9, "říjen": 10,
              "listopad": 11, "prosinec": 12, "podzim": 10, "jaro": 4, "léto": 7}
    for name, num in months.items():
        if name in d.lower():
            return (year, num, 15)
    return (year, 6, 15)


def render_events_with_elections(events, single_file=False):
    out = []
    prev_key = None
    for ev in events:
        key = event_sort_key(ev["date"])
        if prev_key:
            for ey, em, ed in ELECTIONS:
                if prev_key <= (ey, em, ed) < key:
                    out.append(
                        f'<li class="election-sep"><div class="when"></div>'
                        f'<div class="what"><span class="mono">'
                        f'komunální volby {ey}</span></div></li>')
        out.append(render_event(ev, single_file))
        prev_key = key
    return "".join(out)


PHASES = ["záměr", "studie", "soutěž", "dokumentace", "povolení", "tendr", "stavba", "provoz"]


def render_karta(p):
    k = p.get("karta")
    if not k:
        return ""
    rows = ""
    fazebar = ""
    if k.get("typ") == "stavba" and k.get("faze") in PHASES:
        cur = PHASES.index(k["faze"])
        pills = "".join(
            f'<span class="faze {"done" if i < cur else "cur" if i == cur else "todo"}">{ph}</span>'
            for i, ph in enumerate(PHASES))
        pozn = f' <span class="src">({esc(k["fazepozn"])})</span>' if k.get("fazepozn") else ""
        fazebar = f'<div class="fazebar">{pills}{pozn}</div>'
    fields = [("investor", "investor"), ("gestor", "gestor"), ("stav", "stav"),
              ("horizont", "horizont"), ("cena", "cena")]
    cells = "".join(
        f'<div><dt>{label}</dt><dd>{esc(k[key])}</dd></div>'
        for key, label in fields if k.get(key))
    return f'<div class="karta">{fazebar}<dl class="karta-grid">{cells}</dl></div>'


def render_links(p):
    if not p.get("links"):
        return ""
    items = "".join(
        f'<li><a href="{html.escape(l["url"])}">{esc(l["label"])}</a></li>'
        for l in p["links"])
    return (f'<h2 class="sec">Kde se dozvíte víc</h2>'
            f'<ul class="morelinks">{items}</ul>')


def render_project_body(p, single_file=False):
    parts = "".join(
        f'<div class="part"><h3>{esc(x["name"])} {chip(x["status"])}</h3>'
        f'<p>{esc(x["text"])}</p></div>'
        for x in p["parts"]
    )
    counter = ""
    if "counter" in p:
        counter = (
            f'<div class="counterline"><b>{counter_days(p["counter"]["since"])}</b> '
            f'{esc(p["counter"]["label"])}</div>'
        )
    events = render_events_with_elections(p["events"], single_file)
    anchor = f' id="{p["slug"]}"' if single_file else ""
    return f"""<div class="wrap"{anchor}>
  <p class="crumb">Projekt · {esc(p["category"])}{f' · páteřní trasa {esc(p["trasa"])}' if p.get("trasa") else ""} · {esc(p["area"])}</p>
  <h1 class="page">{esc(p["title"])} {chip(p["status"])}</h1>
  <p class="page-lead">{esc(p["summary"])}</p>
  {render_karta(p)}
  {counter}
  <div class="parts">{parts}</div>
  <h2 class="sec">Události spisu</h2>
  <ol class="ev">{events}</ol>
  {render_links(p)}
</div>"""


def render_index_body(projects, single_file=False):
    prefix = "#" if single_file else ""
    ext = "" if single_file else ".html"
    cards = "".join(
        f"""<a class="card" href="{prefix}{p["slug"]}{ext}">
  <h3>{esc(p["title"])}{f' <span class="mono trasa-tag">{esc(p["trasa"])}</span>' if p.get("trasa") else ""}</h3>
  <p class="status">{chip(p["status"])}</p>
  <p>{esc(p["summary"].split(". ")[0])}.</p>
</a>"""
        for p in projects
    )
    anchor = ' id="index"' if single_file else ""
    return f"""<div class="wrap"{anchor}>
  <p class="crumb">Přehled</p>
  <h1 class="page">Projekty</h1>
  <p class="page-lead">Dokumentujeme pražské projekty aktivní mobility, veřejné
  dopravy a veřejného prostoru: co si město schválilo, co skutečně vzniklo a co
  se cestou změnilo. Každý spis obsahuje časovou osu událostí s odkazy na
  zdroje a stupněm doloženosti.</p>
  <div class="cards">{cards}</div>
</div>"""


def render_ramce_body(projects, single_file=False):
    ramce = json.loads((ROOT / "data" / "ramce.json").read_text())
    prefix = "#" if single_file else ""
    ext = "" if single_file else ".html"
    slug_to_title = {p["slug"]: p["title"] for p in projects}
    blocks = []
    for r in ramce:
        docs = " · ".join(
            f'<a href="{html.escape(d["url"])}">{esc(d["label"])}</a>'
            for d in r["dokumenty"])
        projs = " · ".join(
            f'<a href="{prefix}{s}{ext}">{esc(slug_to_title[s])}</a>'
            for s in r["projekty"] if s in slug_to_title)
        blocks.append(f"""<div class="part ramec">
  <h3>{esc(r["nazev"])}</h3>
  <p class="src" style="margin-bottom:.6rem">{esc(r["schvaleno"])}</p>
  <p><b>Slibuje:</b> {esc(r["slibuje"])}</p>
  <p><b>Stav plnění:</b> {esc(r["stav"])}</p>
  <p class="src">dokumenty: {docs}<br>sledované projekty: {projs}</p>
</div>""")
    anchor = ' id="ramce"' if single_file else ""
    return f"""<div class="wrap"{anchor}>
  <p class="crumb">Rámce</p>
  <h1 class="page">Závazky, kterými se město měří</h1>
  <p class="page-lead">Strategie a koncepce, které si Praha sama schválila.
  Z nich plyne výběr sledovaných projektů i měřítko: neměříme město naší
  představou, ale jeho vlastními dokumenty.</p>
  <div class="ramce-list">{"".join(blocks)}</div>
</div>"""


def render_methodology_body(single_file=False):
    anchor = ' id="metodika"' if single_file else ""
    return f"""<div class="wrap meth"{anchor}>
  <p class="crumb">Metodika</p>
  <h1 class="page">Jak web funguje a co nedělá</h1>
  <p class="page-lead">Neutralita webu je metodologická, ne tematická: záběr
  přiznáváme, uvnitř něj měříme každého stejně.</p>
  <h2>Záběr a výběr projektů</h2>
  <p>Sledujeme aktivní mobilitu, veřejnou dopravu a veřejný prostor. Do spisů
  zařazujeme projekty, ke kterým se Praha zavázala schváleným dokumentem
  (koncepce, strategie, programové prohlášení, usnesení). Dokumentujeme rozdíl
  mezi schváleným záměrem a realitou, v obou směrech: spisem je dotažený projekt
  stejně jako rozpadlý. Každý spis musí vypovídat o tom, jak město drží slovo
  a hospodaří, srozumitelně i pro čtenáře, kterého dané téma jinak nezajímá;
  web není katalogem oborových přání. Dálniční okruhy a radiály nesledujeme;
  mají vlastní početné hlídače, tento web se věnuje závazkům, které soustavně
  nehlídá nikdo.</p>
  <h2>Tři stupně doloženosti</h2>
  <div class="tiers">
    <div class="tier-row"><span class="tier tier-a">úřední</span>
      <p>Usnesení, zápisy, jmenovitá hlasování, úřední dokumenty a weby
      institucí. Přebíráme jako fakt, vždy s odkazem.</p></div>
    <div class="tier-row"><span class="tier tier-b">média</span>
      <p>Reportáže a přímé citace v médiích. Uvádíme s odkazem na zdroj a
      jménem média.</p></div>
    <div class="tier-row"><span class="tier tier-c">tvrzení</span>
      <p>Informace třetích stran. Publikujeme výhradně jako označené tvrzení
      s uvedením původce, jen pokud je veřejně dohledatelné; dotčený vždy
      dostane prostor k vyjádření předem.</p></div>
  </div>
  <h2>Hlasování a jejich výklad</h2>
  <p>Postoj k projektu nikdy nevyvozujeme z jediného procedurálního hlasování:
  hlasování o zařazení bodu na program vypovídá o ochotě jednat, ne o názoru na
  věc, a bývá nástrojem taktiky. U aktérů rozlišujeme autora tisku od
  navrhovatele jeho zařazení; co z dat neplyne, výslovně říkáme.</p>
  <h2>Sliby a férovost</h2>
  <p>Sliby evidujeme podle typu zdroje: volební program, koaliční smlouva,
  programové prohlášení, veřejný výrok, předvolební odpověď. Velké stavby se táhnou přes několik volebních období a zásluhy se dělí; proto
  vedle známky uvádíme i <b>reálný posun</b>: o kolik fází (záměr, studie,
  soutěž, dokumentace, povolení, tendr, stavba, provoz) se věc pohnula za
  vlády slibujícího. Známka poměřuje slib s jeho horizontem, posun měří
  skutečnou práci; nečinnost tak nezakryje ani vzletný slib, ani výmluva na
  délku stavby. Sliby stran, které skončily v opozici, neznámkujeme (plnit je
  nebylo v jejich moci) a u slibů úsilí („budeme usilovat, podpoříme“)
  hodnotíme doložené úsilí, ne výsledek. Koaliční smlouvy citujeme jako podepsané politické závazky, nikoli
  úřední akty.</p>
  <h2>Zdroje dat</h2>
  <ul>
    <li>Jmenovitá hlasování zastupitelstva hl. m. Prahy: veřejné rozhraní
    praha.eu, kompletní včetně neschválených návrhů.</li>
    <li>Usnesení a zápisy Rady hl. m. Prahy a městských částí: úřední desky.</li>
    <li>Vše ostatní: odkazovaný veřejný zdroj s uvedeným stupněm doloženosti.</li>
  </ul>
  <h2>Co web nedělá</h2>
  <ul>
    <li>Nevyzývá k podpisům ani nedoporučuje, koho volit.</li>
    <li>Nehodnotí politiky adjektivy; řadí fakta a nechává čtenáře soudit.</li>
    <li>Nepřijímá peníze od politických stran; provoz nestojí nic a nikdo ho
    neplatí.</li>
  </ul>
  <h2>Kdo za tím stojí</h2>
  <p>Web připravuje a data ověřuje <b>Petr Dlouhý</b>, softwarový inženýr a
  Pražan. Projekt je občanský, bez rozpočtu a bez vazby na politické strany.
  Zdrojová data a historie každé změny jsou veřejné v
  <a href="https://github.com/PetrDlouhy/prazsky-semafor">repozitáři webu</a>;
  opravy a doplnění se zdrojem vítáme. Kontaktní adresa bude uvedena zde.</p>
</div>"""


def prefetch_rolls(projects):
    for p in projects:
        for ev in p["events"]:
            v = ev.get("vote")
            if not v:
                continue
            if v.get("rollFile"):
                ev["_roll"] = json.loads((ROOT / "data" / "rolls" / v["rollFile"]).read_text())
                mandate = mc_mandate(v["rollFile"])
                for r in ev["_roll"]:
                    r["shortName"] = norm_name(r["shortName"])
                    r["_mandat"] = mandate
            elif v.get("id") is not None and v.get("period") is not None:
                try:
                    ev["_roll"] = vote_roll(v["id"], v["period"])
                    for r in ev["_roll"]:
                        r["_mandat"] = ("Zastupitelstvo hl. m. Prahy", PERIOD_LABELS[v["period"]])
                except Exception as exc:  # noqa: broad-except - offline build falls back to stored counts
                    print(f"  ! roll {v['id']}: {exc}")


def collect_persons(projects):
    overrides = json.loads((ROOT / "data" / "persons.json").read_text())
    persons = {}
    def entry(short_name):
        slug = actor_slug(short_name)
        return persons.setdefault(slug, {
            "name": short_name, "clubs": set(), "votes": [], "events": [],
            "mandaty": set()})
    for p in projects:
        for ev in p["events"]:
            for r in ev.get("_roll", []):
                e = entry(r["shortName"])
                e["clubs"].add(r["club"])
                e["votes"].append((p, ev, r["voteText"]))
                if r.get("_mandat"):
                    e["mandaty"].add(tuple(r["_mandat"]))
            for a in ev.get("actors", []):
                e = entry(a["name"])
                e["events"].append((p, ev, a["role"]))
    # Mandáty ZHMP i bez zaznamenaného hlasování: úřední seznamy členů period
    for period, label in PERIOD_LABELS.items():
        reps_file = CACHE / f"reps_{period}.json"
        if not reps_file.exists():
            continue
        for r in json.loads(reps_file.read_text()):
            short = norm_name(" ".join(
                t.strip(",") for t in r["fullName"].split()
                if not TITLE_TOKENS.search(t)))
            slug = actor_slug(short)
            if slug in persons:
                persons[slug]["mandaty"].add(("Zastupitelstvo hl. m. Prahy", label))
    for slug, override in overrides.items():
        if slug in persons:
            persons[slug]["name"] = override.get("name", persons[slug]["name"])
            persons[slug]["note"] = override.get("note")
    return persons


def collect_clubs(projects):
    clubs = {}
    for p in projects:
        for ev in p["events"]:
            roll = ev.get("_roll")
            if not roll:
                continue
            by_club = {}
            for r in roll:
                by_club.setdefault(r["club"], []).append(r)
            for club, members in by_club.items():
                entry = clubs.setdefault(club, {"members": {}, "votes": []})
                for m in members:
                    entry["members"][actor_slug(m["shortName"])] = m["shortName"]
                entry["votes"].append((p, ev, seg_counts(members)))
    return clubs


def render_club_body(club, entry):
    votes = "".join(
        f"""<div class="club-vote">
  <p class="src" style="margin-bottom:.3rem"><a href="{p["slug"]}.html">{esc(p["title"])}</a>:
  {esc(ev["vote"]["label"])} · výsledek: {esc(ev["vote"]["vysledek"])}</p>
  {render_bar(counts, height=14)}
  <p class="src">{counts["pro"]} pro · {counts["proti"]} proti · {counts["zdrzel"]} zdrželo se · {counts["ostatni"]} nehlasovalo/chybělo</p>
</div>"""
        for p, ev, counts in sorted(entry["votes"],
                                    key=lambda x: event_sort_key(x[1]["date"])))
    members = ", ".join(
        f'<a href="osoba-{slug}.html">{esc(name)}</a>'
        for slug, name in sorted(entry["members"].items(), key=lambda kv: kv[1].split()[-1]))
    return f"""<div class="wrap">
  <p class="crumb">Klub</p>
  <h1 class="page">{club_chip(club)}</h1>
  <p class="page-lead">Členové a členky zaznamenaní ve sledovaných hlasováních:
  {members}.</p>
  <h2 class="sec">Hlasování klubu ve sledovaných projektech</h2>
  {votes}
  <p class="src" style="margin-top:2rem">Stránka zachycuje pouze hlasování ze
  spisů tohoto webu; není to úplný přehled působení klubu.</p>
</div>"""


def render_person_body(person):
    by_body = {}
    for body, label in sorted(person.get("mandaty", set())):
        by_body.setdefault(body, []).append(label)
    body_order = sorted(by_body, key=lambda b: (b != "Zastupitelstvo hl. m. Prahy", b))
    mandaty = ""
    if by_body:
        parts_m = " · ".join(
            f'{body} (období {", ".join(sorted(by_body[body]))})' for body in body_order)
        mandaty = (f'<p style="margin:-1.2rem 0 1.5rem; font-size:.9rem; '
                   f'color:var(--ink-2)">{esc(parts_m)}</p>')
    clubs = " ".join(
        club_chip(c, link=True)
        for c in sorted(person["clubs"])) or "bez záznamu ve sledovaných jmenovitých hlasováních"
    ev_rows = "".join(
        f'<tr><td>{esc(ev["date"])}</td>'
        f'<td><a href="{p["slug"]}.html">{esc(p["title"])}</a>: {esc(ev["title"])}'
        f'<br><span class="src mono">{esc(role)}</span></td><td></td></tr>'
        for p, ev, role in sorted(person["events"],
                                  key=lambda x: event_sort_key(x[1]["date"])))
    vote_rows = "".join(
        f'<tr><td>{esc(ev["date"])}</td>'
        f'<td><a href="{p["slug"]}.html">{esc(p["title"])}</a>: {esc(ev["vote"]["label"])}</td>'
        f'<td><span class="v-chip v-{VOTE_SEG.get(vt, "zdrzel")}">{esc(vt.lower())}</span></td></tr>'
        for p, ev, vt in sorted(person["votes"],
                                key=lambda x: event_sort_key(x[1]["date"])))
    counts = {}
    for _, _, vt in person["votes"]:
        counts[vt] = counts.get(vt, 0) + 1
    bilance = ""
    if person["votes"]:
        parts_txt = " · ".join(f"{v}× {k.lower()}" for k, v in
                               sorted(counts.items(), key=lambda kv: -kv[1]))
        bilance = (f'<p class="src" style="margin:-.8rem 0 1.5rem">bilance ve '
                   f'sledovaných hlasováních: {esc(parts_txt)}</p>')
    sections = ""
    if ev_rows:
        sections += f'<h2 class="sec">Události ve spisech</h2><table class="votes">{ev_rows}</table>'
    if vote_rows:
        sections += f'<h2 class="sec">Hlasování ve sledovaných projektech</h2><table class="votes">{vote_rows}</table>'
    return f"""<div class="wrap">
  <p class="crumb">Osoba</p>
  <h1 class="page">{esc(person["name"])}</h1>
  <p class="page-lead">{clubs}</p>
  {mandaty}
  {f'<p style="margin-top:-1.2rem; font-size:.9rem; color:var(--ink-2)">{esc(person["note"])}</p>' if person.get("note") else ""}
  {bilance}
  {sections}
  <p class="src" style="margin-top:2rem">Stránka zachycuje pouze hlasování a
  události ze spisů tohoto webu; není to úplný přehled působení. Zdroje
  jmenovitých hlasování: praha.eu a úřední exporty městských částí.</p>
</div>"""


def build():
    projects = []
    for f in sorted((ROOT / "data" / "projects").glob("*.json")):
        projects.append(json.loads(f.read_text()))
    prefetch_rolls(projects)
    persons = collect_persons(projects)
    clubs = collect_clubs(projects)

    DIST.mkdir(exist_ok=True)
    for stale in DIST.glob("*.html"):
        stale.unlink()
    shutil.copy(ROOT / "static" / "style.css", DIST / "style.css")
    shutil.copy(ROOT / "static" / "og.png", DIST / "og.png")

    written = []
    def emit(fname, html_out):
        (DIST / fname).write_text(html_out)
        written.append(fname)
    emit("index.html", page("Projekty", render_index_body(projects), "index",
        desc="Spisy pražských projektů aktivní mobility, veřejné dopravy a veřejného prostoru.",
        path="index.html"))
    emit("metodika.html", page("Metodika", render_methodology_body(), "metodika",
        desc="Jak web funguje: tři stupně doloženosti, výběr projektů, co web nedělá.",
        path="metodika.html"))
    emit("akteri.html", page("Aktéři", render_actors_body(projects, persons_index=persons), "akteri",
        desc="Politici a političky doložení v událostech a jmenovitých hlasováních sledovaných projektů.",
        path="akteri.html"))
    emit("ramce.html", page("Rámce", render_ramce_body(projects), "ramce",
        desc="Strategie a koncepce, kterými se Praha zavázala a kterými ji web měří.",
        path="ramce.html"))
    emit("sliby.html", page("Sliby", render_promises_body(projects), "sliby",
        desc="Veřejné závazky politiků k pražským projektům: kdo co slíbil, dokdy a jak to dopadlo.",
        path="sliby.html"))
    for slug, person in persons.items():
        emit(f"osoba-{slug}.html",
            page(person["name"], render_person_body(person), "akteri",
                 desc=f"Jak hlasuje {person['name']} ve sledovaných pražských projektech; události a závazky se zdroji.",
                 path=f"osoba-{slug}.html"))
    for club, entry in clubs.items():
        emit(f"klub-{club_slug(club)}.html",
            page(club, render_club_body(club, entry), "akteri",
                 desc=f"Jak hlasuje klub {club} ve sledovaných pražských projektech.",
                 path=f"klub-{club_slug(club)}.html"))
    for p in projects:
        emit(f'{p["slug"]}.html',
            page(p["title"], render_project_body(p), "index",
                 desc=p["summary"][:280], path=f'{p["slug"]}.html'))

    preview_body = (
        render_index_body(projects, single_file=True)
        + "".join(render_project_body(p, single_file=True) for p in projects)
        + render_ramce_body(projects, single_file=True)
        + render_promises_body(projects, single_file=True)
        + render_actors_body(projects, single_file=True)
        + render_methodology_body(single_file=True)
    )
    (DIST / "preview.html").write_text(
        page("Náhled", preview_body, "index", single_file=True))
    not_found_body = """<div class="wrap">
  <p class="crumb">Chyba 404</p>
  <h1 class="page">Tahle stránka vypadla cestou</h1>
  <p class="page-lead">Adresa neexistuje nebo se změnila.</p>
  <p><a href="index.html">Přejít na projekty</a></p>
</div>"""
    (DIST / "404.html").write_text(page("Stránka nenalezena", not_found_body, ""))

    urls = "".join(f"<url><loc>{SITE_URL}/{f}</loc></url>" for f in sorted(written))
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    now = date.today().strftime("%a, %d %b %Y 06:00:00 +0200")
    items = "".join(
        f"<item><title>{esc(p['title'])}</title>"
        f"<link>{SITE_URL}/{p['slug']}.html</link>"
        f"<guid>{SITE_URL}/{p['slug']}.html</guid>"
        f"<description>{esc(p['summary'][:400])}</description>"
        f"<pubDate>{now}</pubDate></item>"
        for p in projects)
    (DIST / "feed.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f'<title>{SITE_NAME}</title><link>{SITE_URL}</link>'
        f'<description>{TAGLINE.capitalize()}</description>'
        f'<language>cs</language><lastBuildDate>{now}</lastBuildDate>'
        f'{items}</channel></rss>')
    print(f"built {len(projects)} project(s), {len(persons)} person page(s), sitemap {len(written)} url(s) -> {DIST}")


if __name__ == "__main__":
    build()
