#!/usr/bin/env python3
# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Polaris render v2: one visual model per screen, real states, tighter type."""
import html, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "polaris_redesign_v2.html")
V1 = "https://claude.ai/artifact/GGVPi95TqBSdWEodpGUEb4"

# Global chip space: v1 took 2001-2030. v2 allocates from 2101. Sections 91+.
_chip = [2100]
def next_chip():
    _chip[0] += 1
    return _chip[0]

IC = {
 "close": '<path d="M6 6l12 12M18 6L6 18"/>',
 "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
 "lock": '<rect x="5" y="10.5" width="14" height="9.5" rx="2.2"/><path d="M8.5 10.5V8a3.5 3.5 0 017 0v2.5"/>',
 "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8v.01"/>',
 "camera": '<path d="M4 8.5h3l1.5-2.5h7L17 8.5h3V19H4z"/><circle cx="12" cy="13.2" r="3.2"/>',
 "pdf": '<path d="M7 3.5h7l4 4V20a.5.5 0 01-.5.5h-10.5a.5.5 0 01-.5-.5V4a.5.5 0 01.5-.5z"/><path d="M14 3.5V8h4M9 13h6M9 16.5h4"/>',
 "wallet": '<path d="M4 7.5A2.5 2.5 0 016.5 5H18v3M4 7.5V17a2 2 0 002 2h13.5v-9.5H6.5A2.5 2.5 0 014 7.5z"/><circle cx="16" cy="14.2" r="1"/>',
 "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
 "x": '<circle cx="12" cy="12" r="8.5"/><path d="M9 9l6 6M15 9l-6 6"/>',
 "shield": '<path d="M12 3.5l7 2.6v5.4c0 4.2-2.9 7.2-7 9-4.1-1.8-7-4.8-7-9V6.1z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
 "coin": '<circle cx="12" cy="12" r="8.5"/><path d="M14.5 9.2c-.5-.7-1.4-1.1-2.5-1.1-1.5 0-2.5.8-2.5 1.9 0 2.6 5.1 1.2 5.1 3.9 0 1.1-1.1 1.9-2.6 1.9-1.2 0-2.2-.5-2.7-1.3M12 6.5v1.6M12 15.9v1.6"/>',
 "cal": '<rect x="4" y="5.5" width="16" height="14.5" rx="2.2"/><path d="M4 10h16M8 3.5v4M16 3.5v4"/>',
 "bell": '<path d="M6.5 16.5V11a5.5 5.5 0 0111 0v5.5l1.5 1.5h-14z"/><path d="M10 19.5a2 2 0 004 0"/>',
 "chev": '<path d="M9.5 6.5l5.5 5.5-5.5 5.5"/>',
 "edit": '<path d="M4 20h4l10.5-10.5a1.5 1.5 0 000-2.1L16.6 5.5a1.5 1.5 0 00-2.1 0L4 16z"/>',
 "del": '<path d="M9 6h11.5v12H9l-5-6z"/><path d="M12 9.5l5 5M17 9.5l-5 5"/>',
 "doc": '<path d="M7 3.5h7l4 4V20a.5.5 0 01-.5.5h-10.5a.5.5 0 01-.5-.5V4a.5.5 0 01.5-.5z"/><path d="M14 3.5V8h4"/>',
 "phone": '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 17.5h2"/>',
}
def icon(name, size=20, stroke=1.8, color="currentColor"):
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{IC[name]}</svg>')

# LoanCalculator, SDK config: init 15% (cap 1150), service R86, 0.1%/day, VAT 15% on fees
def calc(cap, days):
    init = min(cap * .15, 1150.0); svc = 86.0; intr = cap * .001 * days; vat = (init + svc) * .15
    return dict(cap=cap, init=init, svc=svc, intr=intr, vat=vat, total=cap + init + svc + intr + vat)
L = calc(3000, 30)                      # 3,706.40 due 22 Nov 2026
ALT = calc(1000, 14)                    # 1,285.40
def money(x): return "R" + format(x, ",.2f")
TOTAL, COST = money(L["total"]), money(L["total"] - 3000)

def status_bar():
    return ('<div class="sb"><span>9:41</span><span class="sbr">'
            '<svg width="16" height="11" viewBox="0 0 16 11"><path fill="currentColor" d="M1 8h2v2H1zM5 6h2v4H5zM9 3.5h2V10H9zM13 1h2v9h-2z"/></svg>'
            '<svg width="22" height="11" viewBox="0 0 22 11"><rect x=".5" y=".5" width="19" height="10" rx="2.5" fill="none" stroke="currentColor"/><rect x="2" y="2" width="14" height="7" rx="1.2" fill="currentColor"/><path d="M20.5 3.5v4" stroke="currentColor"/></svg></span></div>')

def appbar(title, step, done=False):
    segs = "".join(f'<i class="seg{" on" if (done or n <= step) else ""}"></i>' for n in range(1, 7))
    right = "" if done else f'<span class="stepn">STEP {step} OF 6</span>'
    return (f'<div class="appbar">{status_bar()}<div class="abrow"><span class="abx">{icon("close", 18)}</span>'
            f'<span class="abt">{html.escape(title)}</span>{right}</div><div class="segs">{segs}</div></div>')

class Frame:
    def __init__(self, sec, letter, mode, body, title="Loan application", step=1, cta=None, cta2=None, done=False,
                 noappbar=False, fine=None, keypad=False, accessory=None):
        self.__dict__.update(locals()); del self.__dict__["self"]

def render_frame(f, chips):
    head = "" if f.noappbar else appbar(f.title, f.step, f.done)
    tail = ""
    if f.keypad:
        acc = f'<div class="acc"><div class="btn">{html.escape(f.accessory)}</div></div>' if f.accessory else ""
        keys = "".join(f'<span class="{"dim" if k in (".", "⌫") else ""}">{k}</span>' for k in ["1","2","3","4","5","6","7","8","9",".","0","⌫"])
        tail = acc + f'<div class="kbd">{keys}</div>'
    elif f.cta:
        c = f'<div class="btn{" off" if f.cta[1] else ""}">{html.escape(f.cta[0])}</div>'
        c2 = f'<div class="btn ghost">{html.escape(f.cta2)}</div>' if f.cta2 else ""
        fine = f'<div class="fine">{icon("lock", 12, 2)}{html.escape(f.fine)}</div>' if f.fine else ""
        tail = f'<div class="ctaw">{c}{c2}{fine}</div>'
    ch = "".join(f'<i class="chip" style="left:{x}px;top:{y}px">{n}</i>' for n, x, y in chips)
    return (f'<figure class="fr"><div class="phone m-{f.mode}">{head}<div class="pbody">{f.body}</div>{tail}{ch}</div>'
            f'<figcaption><span class="flabel">{f.sec}{f.letter}</span><b>{"Dark" if f.mode=="dark" else "Light"}</b>'
            f'{" · typing" if f.keypad else ""}</figcaption></figure>')

# ---- building blocks ---------------------------------------------------------
def h1(t, c=False): return f'<h3 class="h1{" c" if c else ""}">{html.escape(t)}</h3>'
def sub(t, c=False): return f'<p class="sub{" c" if c else ""}">{html.escape(t)}</p>'
def eyebrow(t): return f'<div class="eyebrow">{html.escape(t)}</div>'

def month_bar(income, exp, debt, loan, limit=None):
    """Segments as % of income; the loan overflows past the income mark when it does not fit."""
    left = income - exp - debt - loan
    pct = lambda v: 100 * v / income
    if left >= 0:
        segs = (f'<i class="seg-exp" style="width:{pct(exp)}%"></i><i class="seg-debt" style="width:{pct(debt)}%"></i>'
                f'<i class="seg-loan" style="width:{pct(loan)}%"></i><i class="seg-left" style="width:{pct(left)}%"></i>')
        lg = [("seg-exp","Living",exp),("seg-debt","Debts",debt),("seg-loan","This loan",loan),("seg-left","Left over",left)]
    else:
        fits = income - exp - debt
        over = loan - fits
        scale = 100 * income / (income + over)
        segs = (f'<i class="seg-exp" style="width:{pct(exp)*scale/100}%"></i><i class="seg-debt" style="width:{pct(debt)*scale/100}%"></i>'
                f'<i class="seg-loan" style="width:{pct(fits)*scale/100}%"></i><i class="seg-over" style="width:{100-scale}%"></i>'
                f'<span class="lim" style="left:{scale}%"></span>')
        lg = [("seg-exp","Living",exp),("seg-debt","Debts",debt),("seg-loan","This loan",loan),("seg-over","Short by",over)]
    legend = "".join(f'<div><i class="{c}"></i>{html.escape(n)}<b>{money(v)}</b></div>' for c, n, v in lg)
    return f'<div class="month"><div class="k">Your month · income {money(income)}</div><div class="bar">{segs}</div><div class="legend">{legend}</div></div>'

def fld(label, val, prefix="R", focus=False, hint=None):
    h = f'<div class="hint">{html.escape(hint)}</div>' if hint else ""
    p = f'<span class="pfx">{prefix}</span>' if prefix else ""
    return f'<div class="fld{" focus" if focus else ""}"><label>{html.escape(label)}</label><div class="v">{p}{html.escape(val)}</div>{h}</div>'

# ---- screens -----------------------------------------------------------------
def s_aff(typing=False):
    # typing: the view has scrolled so the live field sits above the keyboard; title is off-screen
    body = (("" if typing else h1("Does this loan fit your month?")
        + sub(f"{money(3000)} over 30 days means repaying {TOTAL} on 22 Nov. Tell us what comes in and goes out, and we show you whether it fits."))
        + f'<div class="card">{month_bar(20000, 5000, 1500, L["total"])}'
          f'<div class="verdict ok">{icon("check", 15, 2.6)}Fits, with {money(20000-5000-1500-L["total"])} to spare</div></div>'
        + '<div class="fields">'
        + fld("Income after tax", "20,000.00")
        + fld("Living costs", "5,000.00")
        + fld("Other debt repayments", "1,500" if typing else "1,500.00", focus=typing, hint="Accounts, cards, other loans" if typing else None)
        + '</div>'
        + ("" if typing else f'<div class="nca">{icon("shield", 14, 1.9)}<span>The National Credit Act requires every lender to check affordability before offering credit. We do it first, before you give us anything else.</span></div>'))
    return body

def s_nofit():
    return (h1("It doesn't fit this month")
        + sub("Going by your figures this loan would leave you short, so we won't offer it. A smaller one would.")
        + f'<div class="card">{month_bar(9000, 5500, 2200, L["total"])}'
          f'<div class="verdict warn">{icon("info", 15, 2.4)}Short by {money(L["total"]-1300)}</div></div>'
        + eyebrow("What would fit")
        + f'<div class="srow fit"><div><b>{money(1000)} over 14 days</b><small>Repay {money(ALT["total"])} on 6 Nov 2026</small></div>{icon("chev", 18, 2)}</div>')

def s_details():
    return (h1("Check these are you")
        + sub("Your name comes from your account. We need two more things.")
        + f'<div class="who"><span class="av">LD</span><div><b>Lerato Dlamini</b><small>Polaris account</small></div><span class="tag">{icon("shield", 14, 2.2)}Verified</span></div>'
        + '<div class="fields">'
        + f'<div class="fld big2"><label>South African ID number</label><div class="v">820315 5084 083</div><div class="ok">{icon("check", 14, 2.6)}Born 15 March 1982, female</div></div>'
        + f'<div class="fld big2"><label>Mobile number</label><div class="v">082 555 0123</div><div class="hint">We send your decision here by text</div></div>'
        + '</div>')

def s_docs():
    def tile(kind, title, small, state):
        if state == "added":
            th = '<div class="th"><div class="idc"></div></div>' if kind == "front" else '<div class="th"><div class="idb"></div></div>'
            return f'<div class="tile">{th}<span class="badge">{icon("check", 13, 3)}</span><b>{title}</b><small>{small}</small></div>'
        ico = "pdf" if kind == "pdf" else "camera"
        return f'<div class="tile todo"><div class="add"><i>{icon(ico, 20, 1.8)}</i></div><b>{title}</b><small>{small}</small></div>'
    return (h1("Add four documents")
        + sub("Photos are fine. Good light, all four corners in the frame.")
        + '<div class="cnt"><b>2 of 4</b><span>added · 2.3 MB</span></div>'
        + '<div class="tiles">'
        + tile("front", "ID, front", "Added · 1.2 MB", "added") + tile("back", "ID, back", "Added · 1.1 MB", "added")
        + tile("pdf", "Bank statement", "PDF · last 3 months", "todo") + tile("selfie", "Selfie with ID", "Face and ID together", "todo")
        + '</div>')

def s_agree():
    rows = [("Loan amount", money(L["cap"])), ("Initiation fee", money(L["init"])), ("Service fee", money(L["svc"])),
            ("Interest · 30 days", money(L["intr"])), ("VAT on fees", money(L["vat"]))]
    r = "".join(f'<div class="lr"><span>{a}</span><b>{b}</b></div>' for a, b in rows)
    return (h1("Your agreement")
        + f'<div><div class="k">You repay</div><div class="big">{TOTAL}</div><div class="due">{icon("cal", 16, 1.9)}<span>on <b>Sunday 22 November 2026</b>, in one payment</span></div></div>'
        + f'<div class="card rc">{r}<div class="hr"></div><div class="lr tot"><span>Total to repay</span><b>{TOTAL}</b></div>'
          f'<div class="cost"><span>This loan costs you</span><b>{COST}</b></div></div>'
        + f'<div class="linkrow"><span>Read the full agreement</span>{icon("chev", 18, 2)}</div>')

def s_consent():
    tl = [("Today", "You submit", "We check everything and decide in minutes.", ""),
          ("On approval", f"{money(3000)} to your wallet", f"The {money(L['init'])} initiation fee is debited at the same time.", ""),
          ("22 Nov 2026", f"{TOTAL} collected", "By DebiCheck, from the account you choose at your bank.", "")]
    t = "".join(f'<div><i class="{"on" if i == 0 else ""}"></i><div><span class="when">{w}</span><b>{b}</b><small>{s}</small></div></div>' for i, (w, b, s, _) in enumerate(tl))
    return (h1("What happens next")
        + f'<div class="tl">{t}</div>'
        + f'<div class="consent"><span class="cb on">{icon("check", 14, 3.2)}</span><div><b>I authorise the DebiCheck mandate</b><small>Your bank will ask you to approve it on your phone before anything is collected.</small></div></div>')

def s_ok():
    return (f'<div class="hero"><div class="ring ok">{icon("coin", 36, 1.8)}</div><div class="tagc ok">Approved</div>'
            f'{h1("R3,000.00 is in your wallet", True)}{sub("Paid out just now. Nothing else to do today.", True)}</div>'
        + f'<div class="card"><div class="delta"><div><div class="k">Wallet before</div><div class="n">{money(1250)}</div></div><span class="arr">{icon("chev", 18, 2)}</span><div><div class="k">Wallet now</div><div class="n up">{money(4250)}</div></div></div></div>'
        + f'<div class="rowi"><span class="dic">{icon("cal", 19, 1.8)}</span><div><b>Repay {TOTAL} on 22 Nov 2026</b><small>Collected by DebiCheck · in 30 days</small></div></div>'
        + f'<div class="rowi"><span class="dic">{icon("bell", 19, 1.8)}</span><div><b>Remind me a day before</b><small>One notification, 21 Nov</small></div>{icon("chev", 18, 2)}</div>')

def s_wait():
    tl = [("Done", "Application received", "Just now", "done"), ("Now", "Checking your documents", "Usually a few minutes", "on"),
          ("Next", "Decision by text", "to 082 555 0123", "")]
    t = "".join(f'<div><i class="{c}">{icon("check", 11, 3.5) if c == "done" else ""}</i><div><span class="when">{w}</span><b>{b}</b><small>{s}</small></div></div>' for w, b, s, c in tl)
    return (f'<div class="hero"><div class="ring warn">{icon("clock", 36, 1.8)}</div><div class="tagc warn">In review</div>'
            f'{h1("We are checking your application", True)}{sub("You can close this. We will text you the moment there is a decision.", True)}</div>'
        + f'<div class="card"><div class="tl">{t}</div></div>')

def s_no():
    return (f'<div class="hero"><div class="ring bad">{icon("x", 36, 1.8)}</div><div class="tagc bad">Not approved</div>'
            f'{h1("Not this time", True)}{sub("We could not approve R3,000.00 over 30 days. Nothing was charged and nothing is owed.", True)}</div>'
        + eyebrow("What would likely work")
        + f'<div class="srow fit"><div><b>{money(1000)} over 14 days</b><small>Repay {money(ALT["total"])} · costs {money(ALT["total"]-1000)}</small></div>{icon("chev", 18, 2)}</div>'
        + sub("A smaller amount over fewer days costs less and is easier to approve."))

def s_apply():
    return ('<div class="hostbar"><b>Wallet</b><span>Balance R1,250.00</span></div>'
        + '<div class="card apply"><div class="k">Borrow</div>'
          f'<div class="amt"><div class="big">{money(3000)}</div><span class="ed">{icon("edit", 15, 1.9)}</span></div>'
          '<div class="slider"><i style="width:59%"></i><u style="left:59%"></u></div><div class="sl"><span>R100</span><span>R5,000</span></div>'
          '<div class="segc"><span>7 days</span><span>14 days</span><span class="on">30 days</span></div>'
          f'<div class="repay"><span>Repay on 22 Nov</span><b>{TOTAL}</b></div>'
          f'<div class="fine l" style="margin-top:4px">Costs {COST} · no other charges</div>'
          '<div class="btn">Apply</div></div>'
        + f'<div class="fine" style="margin-top:2px">{icon("lock", 12, 2)}Six short steps, about three minutes</div>'
        + '<div class="hk">Recent</div><div class="tx">'
          f'<div><span class="dic">{icon("wallet", 17, 1.8)}</span><div><b>Top-up from FNB</b><small>Yesterday</small></div><span class="amt in">+R500.00</span></div>'
          f'<div><span class="dic">{icon("phone", 17, 1.8)}</span><div><b>Airtime</b><small>Mon 20 Oct</small></div><span class="amt">R55.00</span></div>'
          f'<div><span class="dic">{icon("coin", 17, 1.8)}</span><div><b>Loan repaid</b><small>Fri 17 Oct · on time</small></div><span class="amt">R1,285.40</span></div>'
          '</div>')

# ---- page assembly -----------------------------------------------------------
SECTIONS = []
def with_chips(frames, points):
    nums = [next_chip() for _ in points]
    out = []
    for f in frames:
        pts = [(n, x, y) for i, ((x, y), n) in enumerate(zip(points, nums)) if (f.mode == "light") == (i % 2 == 0)]
        out.append(render_frame(f, pts))
    return nums, "".join(out)

def section(sid, num, title, state, intro, frames_html, callouts, nums):
    notes = "".join(f'<li><i class="chip s">{n}</i><span>{t}</span></li>' for n, t in zip(nums, callouts))
    SECTIONS.append((sid, num, title))
    return (f'<section class="pair" id="{sid}"><div class="shead"><h2 id="sec-{num}">{num} · {html.escape(title)}<em>{state}</em></h2>'
            f'<p class="lede">{intro}</p></div><div class="row">{frames_html}</div><ol class="notes">{notes}</ol></section>')

def pair(sec, body, **kw):
    return [Frame(sec, "a", "dark", body(), **kw), Frame(sec, "b", "light", body(), **kw)]

def build():
    P = []
    # 92 affordability
    fr = pair(92, s_aff, step=1, cta=("Check affordability", False), fine="Used only to check what fits")
    nums, fh = with_chips(fr, [(381, 150), (381, 262), (381, 335), (381, 530)])
    n = next_chip(); nums.append(n)
    fh += render_frame(Frame(92, "c", "dark", s_aff(True), step=1, keypad=True, accessory="Check affordability"), [(n, 381, 520)])
    P.append(section("s92", 92, "Affordability", "V2",
        "One model instead of a form: your month as a bar, with this loan drawn into it. The verdict is visible before the button is pressed, and it changes as you type.",
        fh, ["One sentence states what the loan means in money and on which date.",
             "The month bar. Income is the full width; living costs, other debts and this loan are laid into it; what is left is green. Figures update live.",
             "The verdict in words, with the number to spare. Green only when it fits.",
             "Three inputs, no boxes: label left, figure right, rand sign quiet. Tabular numerals so the column lines up.",
             "Frame c shows the real typing state: the field is live, the keyboard is the system number pad, and the action sits in the accessory bar above it."], nums))

    # 93 does not fit
    fr = pair(93, s_nofit, step=1, cta=("Try R1,000 over 14 days", False), cta2="Change my figures")
    nums, fh = with_chips(fr, [(381, 150), (381, 320), (381, 418), (381, 560)])
    P.append(section("s93", 93, "Doesn't fit", "V2",
        "The decline keeps the same picture. The loan block overflows the income line, hatched, so the problem is obvious without a word, and the one alternative that fits is offered as the primary action.",
        fh, ["Plain title. No apology, no blame.",
             "The same month bar, with the loan hatched past the income mark and the shortfall named.",
             "One alternative computed by the SDK's own calculator, not a vague 'try less'. Shown with the date it would be due; the row and the button do the same thing.",
             "The primary action takes the alternative. The ghost button goes back to the figures."], nums))

    # 94 details
    fr = pair(94, s_details, step=2, cta=("Confirm and continue", False))
    nums, fh = with_chips(fr, [(381, 150), (381, 330), (381, 405), (381, 490)])
    P.append(section("s94", 94, "Your details", "V2",
        "Identity first, then the two things we still need. The ID number is read as you type and echoed back as a date of birth, which is the fastest check that it is right.",
        fh, ["Title in the second person; the name is a verified fact, not a form field.",
             "ID number spaced 6·4·3 the way it is printed on the card.",
             "The echo: born 15 March 1982, female, decoded from the number itself. A wrong digit shows a wrong birthday at once.",
             "Mobile number with the reason we ask, in one line."], nums))

    # 95 documents
    fr = pair(95, s_docs, step=3, cta=("Continue", True), fine="2 still to add")
    nums, fh = with_chips(fr, [(381, 150), (381, 260), (381, 330), (381, 495)])
    P.append(section("s95", 95, "Documents", "V2",
        "Four tiles, not four list rows. Added documents show their thumbnail; missing ones are dashed with the one tap that fills them. The whole state is readable from across the room.",
        fh, ["Count and total size in one line.",
             "Added tiles carry a thumbnail of the capture and a green badge.",
             "Missing tiles are dashed outlines with the capture type as the icon: camera for photos, document for the PDF.",
             "Continue stays disabled with the number still to add, as the code does today."], nums))

    # 96 agreement
    fr = pair(96, s_agree, step=4, cta=("I agree to these terms", False))
    nums, fh = with_chips(fr, [(381, 150), (381, 250), (381, 480), (381, 585)])
    P.append(section("s96", 96, "Agreement", "V2",
        "A statement, not a tinted box. The one number first, the date written out, then the fees as a receipt. The total cost of credit is stated plainly in ember, because an honest number is the brand.",
        fh, ["What you repay, large, with the day written in full and 'in one payment'.",
             "Receipt rows in the fleet money format, right-aligned on tabular figures.",
             "'This loan costs you R706.40': the fees and interest summed, so the price of the loan is one number.",
             "The full agreement opens from a row; the screen does not try to be the contract."], nums))

    # 97 consent
    fr = pair(97, s_consent, step=5, cta=("Submit application", False), fine="You can cancel any time before payout")
    nums, fh = with_chips(fr, [(381, 150), (381, 270), (381, 395), (381, 560)])
    P.append(section("s97", 97, "Consent", "V2",
        "Consent means knowing what will happen. The step is a three-point timeline: today, on approval, on the due date. The DebiCheck mandate is one clear checkbox under it.",
        fh, ["Title says what the screen is for.",
             "Timeline: today you submit; on approval the money arrives and the initiation fee is debited; on 22 Nov the repayment is collected.",
             "The fee is said where it happens, not as a red warning.",
             "The mandate checkbox, with what your bank will do."], nums))

    # 98-100 outcomes
    for sid, num, body, cta, cta2, name, intro, notes, pts in (
        ("s98", 98, s_ok, ("Done", False), None, "Approved",
         "A money moment. The wallet before and after, the repayment as a calendar row, and a one-tap reminder.",
         ["Wallet before and after. The delta is the point of the screen.", "The repayment as a dated row with how it is collected.", "A reminder the day before, one tap. The only thing left to do."],
         [(381, 265), (381, 400), (381, 470)]),
        ("s99", 99, s_wait, ("Close", False), None, "In review",
         "Pending shows where the application is, in the same timeline language as consent, so the user knows which step is happening and what wakes them.",
         ["Warm status colour, not an error.", "Timeline with the current step pulsing and the decision channel named."],
         [(381, 265), (381, 440)]),
        ("s100", 100, s_no, ("Try R1,000 over 14 days", False), "Done", "Declined",
         "Calm, specific, and useful. Nothing was charged, nothing is owed, and the one alternative that would likely work is the primary action.",
         ["Title and the facts: what was asked, what was charged (nothing).", "The alternative, with its due amount and cost, as a tappable row.", "Primary action takes the alternative; Done is secondary."],
         [(381, 265), (381, 430), (381, 740)]),
    ):
        fr = pair(num, body, step=6, done=True, cta=cta, cta2=cta2)
        nums, fh = with_chips(fr, pts)
        P.append(section(sid, num, "Outcome · " + name, "V2", intro, fh, notes, nums))

    # 101 apply card
    fr = pair(101, s_apply, noappbar=True)
    nums, fh = with_chips(fr, [(381, 150), (381, 262), (381, 320), (381, 370)])
    P.append(section("s101", 101, "Apply card, embedded", "V2",
        "PolarisApplyCard sits on the host's wallet page. Amount as the headline, term as a segmented control, repay and cost in one line, one button.",
        fh, ["Amount is the headline, editable by tap or slider.",
             "Term as a three-way segmented control instead of a second slider.",
             "Repay date and figure on one line; the cost of the loan under it.",
             "One primary action; the card says how long the application takes."], nums))
    return "\n".join(P)

def principles():
    items = [("One picture per screen", "Each step has a single visual model: the month bar, the tiles, the receipt, the timeline. Nothing is a bare form."),
             ("Ember means go", "The brand colour appears once per screen, on the action or the one fact that matters. Status colours are quiet and never red for information."),
             ("Money is tabular", "Every figure comes from the SDK's calculator through the fleet formatter: R3,706.40, right-aligned on tabular numerals. Dates are written out."),
             ("Say what happens next", "Every screen ends with what the user will see next and when. No step leaves them guessing.")]
    g = "".join(f'<div><b>{t}</b><p>{p}</p></div>' for t, p in items)
    SECTIONS.insert(0, ("prin", 91, "Principles"))
    return f'<section class="pair" id="prin"><div class="shead"><h2 id="sec-91">91 · Four principles<em>V2</em></h2><p class="lede">What changed between v1 and v2 is not the palette. It is that every screen now has a reason to look the way it does.</p></div><div class="prin">{g}</div></section>'

def build_notes():
    sw = [("Surface","#0b1f1a"),("Card","#10302a"),("Hairline","#255548"),("Secondary ink","#9db8ae"),("Ember, one primary for both modes","#f0643c"),("Approve","#3ddc97")]
    chips = "".join(f'<div class="sw"><i style="background:{c}"></i><b>{n}</b><code>{c}</code></div>' for n, c in sw)
    rows = [("App bar, progress", "CommonAppBar card with the six segments inside it; AppStyle.primary for the filled segments."),
            ("Inputs", "OutlinedBorderTextField, with the label moved left and a rand prefix; number keyboard; format-as-you-type through AppHelpers.numberFormat."),
            ("Buttons", "CustomButton (primary) and the ghost variant; pinned in a bottom bar inside the safe area."),
            ("Cards, rows, tiles", "AppStyle.cardFor / strokeFor / cardAltFor; radius 18; no raw hex anywhere in polaris_sdk."),
            ("Type", "AppStyle.interSemi / interNormal at .sp sizes; tabular figures via FontFeature.tabularFigures()."),
            ("Money and dates", "AppHelpers.numberFormat; intl DateFormat('EEEE d MMMM yyyy')."),
            ("Strings", "TrKeys for every string; copy above is the English."),
            ("Palette", "Polaris home-SDK theme shim calls AppStyle.injectBrandColors with the pine and ember values; light keeps kernel neutrals.")]
    t = "".join(f'<tr><td>{a}</td><td>{b}</td></tr>' for a, b in rows)
    SECTIONS.append(("notes", 102, "Build notes"))
    return (f'<section class="pair" id="notes"><div class="shead"><h2 id="sec-102">102 · Build notes<em>FOR THE PRS</em></h2>'
            f'<p class="lede">How each element maps to the shared SDK components, so the build respects the rules the <a href="{V1}">v1 audit</a> found broken.</p></div>'
            f'<div class="sws" style="margin-bottom:22px">{chips}</div><div class="tw"><table class="map">{t}</table></div></section>')

CSS = open(os.path.join(HERE, "style2.css")).read()

def page():
    body = principles() + build() + build_notes()
    SECTIONS.sort(key=lambda s: s[1])
    nav = "".join(f'<a href="#{i}">{n} · {html.escape(t)}</a>' for i, n, t in SECTIONS)
    return f'''<title>Polaris Redesign v2</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;1,9..144,400;1,9..144,500&family=Manrope:wght@400;500;600&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header class="top"><div><p class="kick">Polaris · Render v2</p><h1>A loan application that <i>shows</i> its working.</h1>
<p class="lede big">Every screen of the six-step application, redrawn so each one has a single picture to read: the month, the tiles, the receipt, the timeline. Dark and light on the SDK tokens. Chips 2101 up, sections 91 to 102.</p></div>
<div class="v2"><b>Changed since v1</b><ul><li>Affordability is a bar of your month, not three fields and a result.</li><li>A real typing state with the number pad.</li><li>ID number echoed as a date of birth.</li><li>Documents as tiles with thumbnails.</li><li>The cost of the loan stated as one number.</li><li>Consent and review share a timeline.</li><li>Approval shows the wallet before and after.</li></ul></div></header>
<nav class="jb" aria-label="Sections">{nav}</nav>
{body}
</div>'''

if __name__ == "__main__":
    open(OUT, "w").write(page())
    print("wrote", OUT, os.path.getsize(OUT), "top chip", _chip[0])
