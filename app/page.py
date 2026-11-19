"""The page's HTML: the top bar, the five views' frames, the phone's tab bar, the tour's layer and the footer, with How
it works written out in full from the scores. site/app.js fills the trace, a session, the policy and the audit log from
site/data.js.

Every visible word comes from WORDS.md. No inline style or script, so the site's security policy can stay strict.
"""
from html import escape as esc

from app import code_view

MARK = ('<svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true"><defs><linearGradient id="brand-ink" x1="0" y1="0" '
        'x2="1" y2="1"><stop offset="0" stop-color="#1f2a3a"/><stop offset="1" stop-color="#0a0e14"/></linearGradient></defs>'
        '<rect width="28" height="28" rx="8" fill="url(#brand-ink)"/><path d="M8 10l4 4-4 4" fill="none" stroke="#22d3ee" '
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M14 18h6" stroke="#fff" stroke-width="2.2" '
        'stroke-linecap="round"/></svg>')
PLAY = ("<svg class='i solid' viewBox='0 0 24 24' aria-hidden='true' focusable='false'><path d='M8 5.2v13.6a1 1 0 0 0 1.5.9l10.6-6.8a1 1 0 0 0 "
        "0-1.7L9.5 4.3A1 1 0 0 0 8 5.2z'/></svg>")
TOUR = ("<svg class='i' viewBox='0 0 24 24' aria-hidden='true' focusable='false'><circle cx='12' cy='12' r='9'/>"
        "<path d='M15.5 8.5l-2 5-5 2 2-5z'/></svg>")
VIEWS = ("trace", "session", "policies", "audit", "how")
REPO = "https://github.com/ryansansbury/agent_console"
HOME = "https://www.ryansansbury.com/"
LIVE = HOME + "agent-console/"
# The share card is the top 838 rows of the 1600 by 1000 card shot, the ratio link previews use, and ?v=1 changes with it.
SHARE = HOME + "images/share/agent-console.png?v=1"



def share_tags(w):
    """The description, the canonical address and the link preview's tags, the same set the other demos carry."""
    title, about, alt = esc(w["page.title"]), esc(w["page.description"]), esc(w["page.share_alt"])
    return (f"<meta name='description' content='{about}'><link rel='canonical' href='{LIVE}'>"
            f"<meta property='og:type' content='website'><meta property='og:url' content='{LIVE}'>"
            "<meta property='og:site_name' content='ryansansbury.com'>"
            f"<meta property='og:title' content='{title}'><meta property='og:description' content='{about}'>"
            f"<meta property='og:image' content='{SHARE}'><meta property='og:image:width' content='1600'>"
            f"<meta property='og:image:height' content='838'><meta property='og:image:alt' content='{alt}'>"
            "<meta name='twitter:card' content='summary_large_image'>"
            f"<meta name='twitter:title' content='{title}'><meta name='twitter:description' content='{about}'>"
            f"<meta name='twitter:image' content='{SHARE}'>")

def money(micro):
    """Dollars for a page: cents from a dime up, tenths of a cent below, and <$0.001 for a cost under that, which
    would otherwise read as free."""
    if 0 < (micro or 0) < 1000:
        return "<$0.001"
    dollars = (micro or 0) / 1e6
    return f"${dollars:.2f}" if dollars >= 0.1 else f"${dollars:.3f}"


def minutes(ms):
    s = round((ms or 0) / 1000)
    return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def table(head, rows, cls="grid"):
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<div class='scroll'><table class='{cls}'><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>"


def paragraphs(w, key):
    return "".join(f"<p>{esc(p)}</p>" for p in w.paragraphs(key))


def bullets(w, key, tag="ul"):
    return f"<{tag}>" + "".join(f"<li>{esc(v)}</li>" for v in w.items(key)) + f"</{tag}>"


def how_map(w):
    rows = []
    for part, rest in w.table("how.map").items():
        who, _, how = rest.partition(" | ")
        rows.append([esc(part), esc(who), esc(how)])
    return table(["", "", ""], rows, "grid map")


def how_experiment(w, data):
    cols = w.table("how.experiment_cols")
    if not data["experiment"]:
        return f"<p class='muted'>{esc(w['how.experiment_none'])}</p>"
    said = w.table("how.said")
    rows = []
    for e in data["experiment"]:
        followed = "; ".join(e["followed"]) if e["followed"] else said["no"]
        caught = said["caught_all"] if e["attempts"] and e["caught"] else said["caught_none"] if not e["attempts"] \
            else said["caught_some"]
        rows.append([esc(e["label"] or e["model"]), esc(followed), esc(said["yes" if e["flagged"] else "no"]),
                     esc(caught)])
    return table([cols["model"], cols["followed"], cols["flagged"], cols["caught"]], rows)


def how_compare(w, data):
    cols, said = w.table("how.compare_cols"), w.table("how.said")
    rows = []
    for mid, r in data["rows"].items():
        name = esc(r["label"]) + (f" <span class='pill route'>{esc(said['route'])}</span>" if mid == data["route"] else "")
        done = w.fill("how.done_of", done=r["done"]) + (" " + w.fill("how.safe_stops", n=r["safe_stops"])
                                                        if r["safe_stops"] else "")
        rows.append([name, esc(done), str(r["unsafe"]), str(r["asked"]), str(r["denied"]), str(r["quarantined"]),
                     esc(money(r["cost_micro"])), minutes(r["ms"])])
    return table([cols[k] for k in ("model", "done", "unsafe", "asked", "denied", "quarantined", "cost", "time")], rows)


def how_budget(w, data):
    b = data["budget_test"]
    if not b:
        return f"<p class='muted'>{esc(w['how.budget_none'])}</p>"
    said = w.table("how.said")
    line = w.fill("how.budget_line", model=b["label"] or b["model"], job=b["job"], limit=money(b["limit_micro"]),
                  spent=money(b["spent_micro"]), warned=said["warned" if b["warned"] else "never_warned"],
                  stopped=said["stopped" if b["stopped"] else "never_stopped"])
    # The sentence already says the bar when it held (warned first, stopped, under the limit), so only a miss adds one.
    return f"<p>{esc(line)}{'' if b['ok'] else ' ' + esc(said['not_ok'])}</p>"


def how_runs(w, data):
    cols = w.table("how.runs_cols")
    rows = [[esc(r["date"]), esc(r["model"]), esc(r["run"]), f"<code>{esc(r['job'])}</code>", esc(r["state"] or ""),
             str(r["calls"]), esc(money(r["cost_micro"]))] for r in data["runs"]]
    return table([cols[k] for k in ("date", "model", "run", "job", "state", "calls", "cost")], rows)


def how_code(w):
    feats = "".join(f"<button type='button' class='cfeat' data-file='{esc(f)}'><b>{esc(f.split('/')[-1])}</b>"
                    f"<span>{esc(f)}</span></button>" for f in code_view.FEATURED)
    return (f"<h2 id='code'>{esc(w['how.code_head'])}</h2><p>{esc(w['how.code_lead'])}</p>"
            f"<div class='feats'>{feats}</div><div class='codebox'><nav id='code-tree' aria-label='files'></nav>"
            f"<div class='code-main'><p id='code-path' class='mono'></p><pre id='code-body' tabindex='0'></pre></div></div>")


def how(w, data):
    return (f"<article class='how'><h1>{esc(w['how.title'])}</h1>{paragraphs(w, 'how.lead')}"
            f"<h2>{esc(w['how.map_head'])}</h2>{how_map(w)}"
            f"<h2>{esc(w['how.threat_head'])}</h2>{paragraphs(w, 'how.threat')}"
            f"<h2>{esc(w['how.layers_head'])}</h2>{bullets(w, 'how.layers', 'ol')}"
            f"<h2>{esc(w['how.experiment_head'])}</h2>{paragraphs(w, 'how.experiment_lead')}{how_experiment(w, data)}"
            f"<h2>{esc(w['how.compare_head'])}</h2>{paragraphs(w, 'how.compare_lead')}{how_compare(w, data)}"
            f"<h2>{esc(w['how.budget_head'])}</h2>{how_budget(w, data)}"
            f"<h2>{esc(w['how.runs_head'])}</h2>{how_runs(w, data)}"
            f"<h2>{esc(w['how.client_head'])}</h2>{bullets(w, 'how.client', 'ol')}"
            f"<h2>{esc(w['how.limits_head'])}</h2>{bullets(w, 'how.limits')}"
            f"{how_code(w)}</article>")


def render(w, data):
    nav = w.table("page.nav")
    tabs = "".join(f"<button type='button' class='tab{' on' if v == 'trace' else ''}' data-view='{v}' "
                   f"aria-pressed='{'true' if v == 'trace' else 'false'}'>{esc(nav[v])}</button>" for v in VIEWS)
    screens = w.table("ui.screen")
    phone_tabs = "".join(f"<button type='button' data-view='{v}'>{esc(screens[v])}</button>" for v in screens)
    sections = "".join(f"<section id='v-{v}' class='view' aria-label='{esc(nav[v])}'{'' if v == 'trace' else ' hidden'}>"
                       f"{how(w, data) if v == 'how' else ''}</section>" for v in VIEWS)
    preview = f"<p id='preview-bar' class='preview'>{esc(w['page.preview'])}</p>" if data.get("preview") else ""
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta name='robots' content='index, follow'><meta name='referrer' content='no-referrer'>"
        f"<title>{esc(w['page.title'])}</title>{share_tags(w)}"
        "<link rel='icon' href='data:,'><link rel='stylesheet' href='app.css'></head>"
        "<body class='view-trace'>"
        f"<a class='skip' href='#main'>{esc(w['page.skip'])}</a>"
        f"<header class='top'><a class='brand' href='#trace' data-home='trace' title='{esc(w['page.home'])}'>{MARK}"
        f"<b>{esc(w['page.title'])}</b></a>"
        f"<nav class='tabs' aria-label='views'>{tabs}</nav>"
        f"<div class='grow'></div><label class='picker'><span>{esc(w['page.model'])}</span>"
        "<select id='model'></select></label>"
        f"<button type='button' id='replay' class='btn'>{PLAY}{esc(w['page.replay'])}</button>"
        f"<button type='button' id='tour-start' class='btn ghost'>{TOUR}{esc(w['page.tour'])}</button></header>{preview}"
        f"<main id='main'>{sections}</main>"
        f"<nav class='screens' aria-label='screens'>{phone_tabs}</nav>"
        f"<footer class='foot'><p>{esc(w['page.footer'])}</p>"
        f"<p><a href='{REPO}'>{esc(w['page.code_link'])}</a> · <a href='{HOME}'>{esc(w['page.home_link'])}</a></p></footer>"
        "<svg id='tour' hidden aria-hidden='true'></svg>"
        "<div id='tour-box' role='dialog' aria-live='polite' hidden></div><div id='pop' hidden></div>"
        "<script src='data.js'></script><script src='policy.js'></script><script src='audit.js'></script>"
        "<script src='app.js'></script></body></html>\n"
    )
