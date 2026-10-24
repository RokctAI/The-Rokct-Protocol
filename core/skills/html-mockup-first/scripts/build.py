#!/usr/bin/env python3
"""Builds the Polaris SDK UI redesign render page (single scrollable strip)."""
import base64, html, io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "polaris_redesign.html")
SCR = os.path.abspath(os.path.join(HERE, "..", "polaris", "marketing", "tour", "store"))

# ---- chip numbering: one global space; this page allocates 2001+ ----------
_chip = [2000]
def next_chip():
    _chip[0] += 1
    return _chip[0]

# ---- icons (remix-style line glyphs, 24 box) ---------------------------------
IC = {
 "close": '<path d="M6 6l12 12M18 6L6 18"/>',
 "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
 "lock": '<rect x="5" y="10.5" width="14" height="9.5" rx="2.2"/><path d="M8.5 10.5V8a3.5 3.5 0 017 0v2.5"/>',
 "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8v.01"/>',
 "doc": '<path d="M7 3.5h7l4 4V20a.5.5 0 01-.5.5h-10.5a.5.5 0 01-.5-.5V4a.5.5 0 01.5-.5z"/><path d="M14 3.5V8h4"/>',
 "camera": '<path d="M4 8.5h3l1.5-2.5h7L17 8.5h3V19H4z"/><circle cx="12" cy="13.2" r="3.2"/>',
 "id": '<rect x="3.5" y="5.5" width="17" height="13" rx="2.2"/><circle cx="9" cy="11.5" r="2"/><path d="M6.2 16c.6-1.6 1.7-2.3 2.8-2.3s2.2.7 2.8 2.3M14 10.5h4M14 13.5h3"/>',
 "bank": '<path d="M3.5 9.5L12 4l8.5 5.5M5.5 10v7M10 10v7M14 10v7M18.5 10v7M3.5 19.5h17"/>',
 "up": '<path d="M12 16V5M7.5 9.5L12 5l4.5 4.5M5 19h14"/>',
 "wallet": '<path d="M4 7.5A2.5 2.5 0 016.5 5H18v3M4 7.5V17a2 2 0 002 2h13.5v-9.5H6.5A2.5 2.5 0 014 7.5z"/><circle cx="16" cy="14.2" r="1"/>',
 "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
 "x": '<circle cx="12" cy="12" r="8.5"/><path d="M9 9l6 6M15 9l-6 6"/>',
 "shield": '<path d="M12 3.5l7 2.6v5.4c0 4.2-2.9 7.2-7 9-4.1-1.8-7-4.8-7-9V6.1z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
 "coin": '<circle cx="12" cy="12" r="8.5"/><path d="M14.5 9.2c-.5-.7-1.4-1.1-2.5-1.1-1.5 0-2.5.8-2.5 1.9 0 2.6 5.1 1.2 5.1 3.9 0 1.1-1.1 1.9-2.6 1.9-1.2 0-2.2-.5-2.7-1.3M12 6.5v1.6M12 15.9v1.6"/>',
}
def icon(name, size=20, stroke=1.8, color="currentColor", fill="none"):
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="{fill}" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{IC[name]}</svg>')

# ---- demo figures: LoanCalculator with the SDK's own config -----------------
# R3,000 over 30 days, initiationFeeRate .15, serviceFeeFlat 86, ratePerDay .001, vat .15
CAP, INIT, SERVICE, INTEREST, VAT = 3000.00, 450.00, 86.00, 90.00, 80.40
TOTAL = CAP + INIT + SERVICE + INTEREST + VAT          # 3706.40
def money(x): return "R" + format(x, ",.2f")

# ---- frame scaffolding -------------------------------------------------------
class Frame:
    def __init__(self, sec, letter, mode, title, step, body, cta=None, cta2=None, done=False, bar=True, noappbar=False, secondary=None):
        self.sec, self.letter, self.mode = sec, letter, mode
        self.title, self.step, self.body, self.cta, self.cta2 = title, step, body, cta, cta2
        self.done, self.bar, self.noappbar, self.secondary = done, bar, noappbar, secondary
        self.chips = []

def status_bar():
    return ('<div class="sb"><span>9:41</span><span class="sbr">'
            '<svg width="16" height="11" viewBox="0 0 16 11"><path fill="currentColor" d="M1 8h2v2H1zM5 6h2v4H5zM9 3.5h2V10H9zM13 1h2v9h-2z"/></svg>'
            '<svg width="22" height="11" viewBox="0 0 22 11"><rect x=".5" y=".5" width="19" height="10" rx="2.5" fill="none" stroke="currentColor"/><rect x="2" y="2" width="14" height="7" rx="1.2" fill="currentColor"/><path d="M20.5 3.5v4" stroke="currentColor"/></svg></span></div>')

def appbar(title, step, bar=True, done=False):
    segs = "".join(f'<i class="seg{" on" if (done or n <= step) else ""}"></i>' for n in range(1, 7))
    prog = f'<div class="segs" role="img" aria-label="Step {step} of 6">{segs}</div>' if bar else ""
    right = f'<span class="stepn">{step}<small>/6</small></span>' if bar and not done else ""
    return (f'<div class="appbar">{status_bar()}<div class="abrow"><span class="abx">{icon("close", 18)}</span>'
            f'<span class="abt">{html.escape(title)}</span>{right}</div>{prog}</div>')

def render_frame(f, chips):
    cta = ""
    if f.cta:
        c = f'<div class="btn{" off" if f.cta[1] else ""}">{html.escape(f.cta[0])}</div>'
        c2 = f'<div class="btn ghost">{html.escape(f.cta2)}</div>' if f.cta2 else ""
        sec = f'<div class="fine">{icon("lock", 12, 2)}{html.escape(f.secondary)}</div>' if f.secondary else ""
        cta = f'<div class="ctaw">{c}{c2}{sec}</div>'
    ch = "".join(f'<i class="chip" style="left:{x}px;top:{y}px">{n}</i>' for n, x, y in chips)
    letter = f'<span class="flabel">{f.sec}{f.letter}</span>'
    head = "" if f.noappbar else appbar(f.title, f.step, f.bar, f.done)
    return (f'<figure class="fr"><div class="phone m-{f.mode}">{head}<div class="pbody">{f.body}</div>{cta}{ch}</div>'
            f'<figcaption>{letter}<b>{"Dark" if f.mode=="dark" else "Light"}</b></figcaption></figure>')

# ---- reusable bits -----------------------------------------------------------
def eyebrow(t): return f'<div class="eyebrow">{html.escape(t)}</div>'
def h1(t): return f'<h3 class="h1">{html.escape(t)}</h3>'
def sub(t): return f'<p class="sub">{html.escape(t)}</p>'
def field(label, value, helper=None, prefix=None, focus=False, ok=False):
    p = f'<span class="pfx">{prefix}</span>' if prefix else ""
    h = f'<div class="hlp">{html.escape(helper)}</div>' if helper else ""
    return (f'<div class="fld{" focus" if focus else ""}"><label>{html.escape(label)}</label>'
            f'<div class="val">{p}<span>{html.escape(value)}</span>{icon("check", 16, 2.2, "var(--ok)") if ok else ""}</div></div>{h}')
def meter(pct, kind="ok"):
    return f'<div class="meter"><i class="{kind}" style="width:{pct}%"></i></div>'
def row(a, b, strong=False):
    return f'<div class="lr{" tot" if strong else ""}"><span>{html.escape(a)}</span><b>{html.escape(b)}</b></div>'

# ---- screens (body markup is mode-agnostic; tokens do the theming) -----------
def s1_body():
    return (eyebrow("Step 1 of 6 · Affordability") + h1("What can you afford each month?")
        + sub("We check this first, so you never borrow more than you can repay.")
        + f'<div class="card hero"><div class="k">You are borrowing</div><div class="big">{money(CAP)}</div>'
          f'<div class="pills"><span>30 days</span><span>Repay {money(TOTAL)}</span><span>Due 22 Nov 2026</span></div></div>'
        + field("Monthly income (net)", "20,000.00", None, "R", ok=True)
        + field("Monthly living expenses", "5,000.00", None, "R", ok=True)
        + field("Other monthly debt repayments", "1,500.00", "Accounts, cards, other loans", "R", focus=True)
        + f'<div class="card res"><div class="rr"><span>Left over each month</span><b class="okc">R13,500.00</b></div>{meter(100)}'
          f'<div class="rr small"><span>Needed to repay</span><b>{money(TOTAL)}</b></div>'
          f'<div class="verdict ok">{icon("check", 15, 2.4)}<span>Comfortably covers your repayment</span></div></div>')

def s1d_body():
    return (f'<div class="center">'
        f'<div class="ring warn">{icon("info", 30, 1.8)}</div>'
        f'<h3 class="h1 c">Not enough left over this month</h3>'
        f'<p class="sub c">Going by your figures, this loan would leave you short. We would rather say so now than set you up to miss a payment.</p></div>'
        f'<div class="card res"><div class="rr"><span>Left over each month</span><b>R1,300.00</b></div>{meter(35, "warn")}'
        f'<div class="rr small"><span>Needed to repay</span><b>{money(TOTAL)}</b></div>'
        f'<div class="verdict warn">{icon("info", 15, 2.2)}<span>Short by R2,406.40</span></div></div>'
        f'<div class="card tip"><div class="k">A smaller loan could work</div>'
        f'<div class="tipl"><b>R1,000.00</b><span>over 14 days repays</span><b>R1,285.40</b></div></div>')

def s2_body():
    return (eyebrow("Step 2 of 6 · Your details") + h1("Check these are right")
        + sub("We took these from your account. Add the two things we still need.")
        + '<div class="card who"><span class="av">LD</span><div><b>Lerato Dlamini</b><small>From your Polaris account</small></div>'
          f'<span class="tag">{icon("shield", 13, 2)}Verified</span></div>'
        + field("ID number", "8203155084083", "13 digits, exactly as on your ID", None, focus=True)
        + field("Mobile number", "082 555 0123", "So we can reach you about your application", None))

def doc_row(ico, title, hint, state):
    if state == "added":
        right = f'<span class="added">{icon("check", 14, 2.6)}Added</span>'
        hint = hint
    else:
        right = f'<span class="upl">{icon("up", 14, 2)}Upload</span>'
    return (f'<div class="drow{" done" if state=="added" else ""}"><span class="dic">{icon(ico, 20, 1.7)}</span>'
            f'<div class="dt"><b>{html.escape(title)}</b><small>{html.escape(hint)}</small></div>{right}</div>')

def s3_body():
    return (eyebrow("Step 3 of 6 · Documents") + h1("Add your documents")
        + sub("A clear photo is fine. Good light, all four corners showing.")
        + f'<div class="card prog"><div class="rr"><span>2 of 4 added</span><b>50%</b></div>{meter(50, "pr")}</div>'
        + '<div class="card list">'
        + doc_row("id", "ID document, front", "id-front.jpg · 1.2 MB", "added")
        + doc_row("id", "ID document, back", "id-back.jpg · 1.1 MB", "added")
        + doc_row("bank", "Bank statement", "PDF, last 3 months", "todo")
        + doc_row("camera", "Selfie holding your ID", "Face and ID both in frame", "todo")
        + '</div>' + f'<div class="fine l">{icon("lock", 12, 2)}JPG, PNG or PDF, up to 10 MB each</div>')

def s4_body():
    return (eyebrow("Step 4 of 6 · Agreement") + h1("Review your agreement")
        + f'<div class="card contract"><div class="k">You repay</div><div class="big">{money(TOTAL)}</div><div class="due">on 22 Nov 2026</div>'
          '<div class="hr"></div>'
        + row("Loan amount", money(CAP)) + row("Initiation fee", money(INIT)) + row("Service fee", money(SERVICE))
        + row("Interest, 30 days", money(INTEREST)) + row("VAT on fees", money(VAT))
        + '<div class="hr"></div>' + row("Total to repay", money(TOTAL), True) + '</div>'
        + '<p class="fine l">This is a binding agreement. Read it, then agree below.</p>')

def s5_body():
    return (eyebrow("Step 5 of 6 · Submit") + h1("Ready to submit?")
        + f'<div class="card sum">{row("Amount", money(CAP))}{row("Paid out to", "Polaris wallet")}{row("Total to repay", money(TOTAL))}{row("Due", "22 Nov 2026")}</div>'
        + f'<div class="card consent"><span class="cb on">{icon("check", 14, 3)}</span><div><b>I authorise a DebiCheck mandate</b>'
          f'<small>{money(TOTAL)} on 22 Nov 2026. Your bank asks you to approve it on your phone.</small></div></div>'
        + f'<div class="note">{icon("info", 16, 2)}<span>The initiation fee of {money(INIT)} is debited as soon as your loan is approved.</span></div>')

def s6_body(kind):
    cfg = {
     "ok":   ("coin", "Approved", "R3,000.00 is in your wallet", "Your loan is approved and paid out. Repay on 22 Nov 2026.", "okring"),
     "wait": ("clock", "In review", "We are checking your application", "We will let you know as soon as there is a decision.", "warn"),
     "no":   ("x", "Not approved", "We could not approve this loan", "You can try again with a smaller amount.", "bad"),
    }[kind]
    ico, tag, title, msg, ring = cfg
    extra = ""
    if kind == "ok":
        extra = f'<div class="card sum">{row("Paid to wallet", money(CAP))}{row("Repay", money(TOTAL))}{row("Due", "22 Nov 2026")}</div>'
    if kind == "no":
        extra = f'<div class="card tip"><div class="k">What helps</div><div class="tipt">A smaller amount over fewer days costs less and is easier to repay.</div></div>'
    return (f'<div class="center top"><div class="ring {ring}">{icon(ico, 34, 1.8)}</div><div class="tagc {ring}">{tag}</div>'
            f'<h3 class="h1 c">{html.escape(title)}</h3><p class="sub c">{html.escape(msg)}</p></div>{extra}')

def apply_body():
    return ('<div class="hostbar"><b>Wallet</b><span>R1,250.00</span></div>'
        '<div class="card apply"><div class="k">Need a loan?</div><div class="big">R3,000.00</div>'
        '<div class="slider"><i style="width:58%"></i><u style="left:58%"></u></div><div class="sl"><span>R100</span><span>R5,000</span></div>'
        '<div class="pills"><span class="on">30 days</span><span>14 days</span><span>7 days</span></div>'
        '<div class="hr"></div>'
        + row("You repay", money(TOTAL), True) + row("Due", "22 Nov 2026") +
        '<div class="btn">Apply now</div>'
        f'<div class="fine c">{icon("lock", 12, 2)}Six short steps</div></div>')

# ---- chip layout -------------------------------------------------------------
def with_chips(frames, points):
    """points: list of (x, y). Even numbering alternates: odd-indexed point on light, even on dark."""
    nums = [next_chip() for _ in points]
    out = []
    for f in frames:
        pts = []
        for i, ((x, y), n) in enumerate(zip(points, nums)):
            on_light = (i % 2 == 0)
            if (f.mode == "light") == on_light:
                pts.append((n, x, y))
        out.append(render_frame(f, pts))
    return nums, "".join(out)

def pair(sec, letters, builder, **kw):
    return [Frame(sec, letters[0], "dark", **kw, body=builder()), Frame(sec, letters[1], "light", **kw, body=builder())]

SECTIONS = []
def section(sid, num, title, state, intro, frames_html, callouts, nums):
    notes = "".join(f'<li><i class="chip s">{n}</i><span>{t}</span></li>' for n, t in zip(nums, callouts))
    SECTIONS.append((sid, num, title))
    return (f'<section class="pair" id="{sid}"><div class="shead"><h2 id="sec-{num}">{num} · {html.escape(title)} <em>— {state}</em></h2>'
            f'<p class="lede">{intro}</p></div><div class="row">{frames_html}</div><ol class="notes">{notes}</ol></section>')

# ---- build -------------------------------------------------------------------
def build():
    parts = []

    # 1 · affordability
    fr = pair(80, "ab", s1_body, title="Loan application", step=1, cta=("Check affordability", False), secondary="Used only to check what you can afford")
    nums, fh = with_chips(fr, [(381,107),(381,178),(381,300),(381,398),(381,600)])
    parts.append(section("s1", 80, "Affordability", "REDESIGN",
        "The first thing every applicant sees. It was a stock Material form with a blue app bar and raw numbers; it is now the Polaris pine and ember, with the loan they chose pinned at the top and a live read of what is left over.",
        fh, ["Segmented progress replaces the blue stock progress bar; the app bar is the shared CommonAppBar card.",
             "Step name in the eyebrow, one plain question as the title. The robotic “Step 1: Affordability Check” is gone.",
             "The loan they chose stays in view: amount, term, total to repay and due date, so the figures they type have something to be measured against.",
             "Currency fields: R prefix, thousands separators, helper line under the field being edited. Built on OutlinedBorderTextField's tokens.",
             "Live “left over” read and meter. The same sum the code already does (income − expenses − obligations ≥ total), shown before they press anything. The button is pinned to the bottom, so no empty grey void."], nums))

    fr = pair(81, "ab", s1d_body, title="Loan application", step=1, cta=("Change loan amount", False), cta2="Close")
    nums, fh = with_chips(fr, [(381,191),(381,395),(381,505)])
    parts.append(section("s1d", 81, "Affordability · not affordable", "REDESIGN",
        "Today this is a bare icon, two sentences and a button that says “Go back and reduce loan amount”. A decline should be calm, specific and offer a way forward.",
        fh, ["Warning ring uses the status warn colour, not a red error. Nothing has gone wrong.",
             "The shortfall is stated in rand. Meter shows how far short.",
             "A concrete smaller loan that fits (R1,000 over 14 days, repays R1,285.40, same calculator). One tap returns them to the amount."], nums))

    # 2 · details
    fr = pair(82, "ab", s2_body, title="Loan application", step=2, cta=("Confirm and continue", False))
    nums, fh = with_chips(fr, [(381,284),(381,360),(381,442)])
    parts.append(section("s2", 82, "Personal details", "REDESIGN",
        "Name and surname were two lines of plain text (“First Name: Lerato”). Now they are an identity card, and the two fields we need are explained.",
        fh, ["Identity card: initials avatar, name, source, Verified tag. Read-only prefill from PolarisUserPrefill.",
             "ID number with the format spelled out. Number keyboard, 13 digit check.",
             "Mobile number with the reason we ask."], nums))

    # 3 · documents
    fr = pair(83, "ab", s3_body, title="Loan application", step=3, cta=("Continue", True), secondary="2 documents still to add")
    nums, fh = with_chips(fr, [(381,280),(381,367),(381,494),(381,770)])
    parts.append(section("s3", 83, "Documents", "REDESIGN",
        "Four ListTiles with a stock Upload button each. Now one grouped list with real state.",
        fh, ["Overall progress: 2 of 4 added.",
             "Each row says what it is and what a good file looks like. Added rows show the file name and size.",
             "Upload is a quiet pill, not a full Material button. Tapping opens the existing picker (10 MB limit unchanged).",
             "Continue stays disabled until all four are in, exactly as the code does today, and says how many are left."], nums))

    # 4 · contract
    fr = pair(84, "ab", s4_body, title="Loan application", step=4, cta=("I agree to these terms", False))
    nums, fh = with_chips(fr, [(381,247),(381,330),(381,482)])
    parts.append(section("s4", 84, "Agreement", "REDESIGN",
        "The old card was a tinted block with the fee lines in bold accent colour and an ISO date (2026-11-22). Now it reads like a statement.",
        fh, ["Lead with the number that matters: what they repay and when.",
             "Every fee line is tabular and aligned, in the fleet money format (R3,706.40) from the shared formatter, not toStringAsFixed.",
             "Total is its own row. The binding-agreement sentence moves below the card where it can be read."], nums))

    # 5 · consent
    fr = pair(85, "ab", s5_body, title="Loan application", step=5, cta=("Submit application", False))
    nums, fh = with_chips(fr, [(381,260),(381,380),(381,460)])
    parts.append(section("s5", 85, "Consent and submit", "REDESIGN",
        "Default Card, default CheckboxListTile, and the fee warning printed in red as though it were an error.",
        fh, ["One summary card for what is being agreed.",
             "DebiCheck consent as a deliberate checkbox card, with what happens next on your phone.",
             "The initiation fee notice is an ember-tinted note, not error red. It is information the law requires, not a fault."], nums))

    # 6 · outcomes
    allparts = []
    for tag, sid, num in (("ok", "s6a", 86), ("wait", "s6b", 87), ("no", "s6c", 88)):
        fr = pair(num, "ab", lambda t=tag: s6_body(t), title="Loan application", step=6, cta=("Done", False), done=True, bar=True)
        nums, fh = with_chips(fr, [(381,219),(381,304)])
        names = {"ok": ("Approved", "A paid-out loan lands with the money first: what arrived, where, and when to repay."),
                 "wait": ("In review", "Pending is not a fault state, so it uses the warm status colour and says what happens next."),
                 "no": ("Declined", "Calm wording, nothing charged, and one useful suggestion.")}[tag]
        parts.append(section(sid, num, "Outcome · " + names[0], "REDESIGN", names[1], fh,
            ["Status ring and tag. All six progress segments are filled; the step counter goes away.", "Title says the result in plain words. Details sit in a card below."], nums))

    # apply card
    fr = pair(89, "ab", apply_body, title="Home", step=0, cta=None, noappbar=True)
    nums, fh = with_chips(fr, [(381,143),(381,225),(381,355)])
    parts.append(section("s7", 89, "Apply card (embeddable)", "REDESIGN",
        "PolarisApplyCard sits inside any host page. It was a stock Material card with two default sliders and raw R-prefixed numbers; it now matches the fleet card language so it looks native on the wallet and marketplace pages that embed it.",
        fh, ["Same card fill, hairline and radius as the host's own cards in both modes.",
             "Amount and term controls use the brand primary. Term presets for the common cases.",
             "The repay line is the answer; the button is the only primary action on the card."], nums))
    return "\n".join(parts)

# ---- audit table -------------------------------------------------------------
AUDIT = [
 ("Colour only from AppStyle tokens, brand injected per app", "Wizard uses Material's default blue (AppBar, ElevatedButton, LinearProgressIndicator). PolarisTheme.defaultTheme() hard-codes 0xFF1976D2 / 0xFFFF9800 / 0xFFF44336 / 0xFF4CAF50 (polaris_models.dart:57-62), used by steps 4, 5 and 6.", "AppStyle.primary, *For(brightness) tokens and the shared status colours; PolarisTheme colours stop being read by the screens."),
 ("The composed app injects its own palette", "No Polaris palette is injected, so AppStyle falls back to the Juvo orange #FF6600. The published tour images are orange for that reason.", "Polaris home-SDK theme shim calls AppStyle.injectBrandColors with the pine and ember palette (needs Ray's palette call, section 90)."),
 ("Mode comes from Theme.of(context).brightness", "No application step reads the theme; light and dark only change by accident of Material defaults.", "Every surface and ink goes through AppStyle.cardFor / inkFor / strokeFor."),
 ("Shared components, not stock Material", "polaris_application_page.dart:76 AppBar, :88 LinearProgressIndicator; steps 1-5 use TextField, ElevatedButton, Card, CheckboxListTile. loan_screen.dart already uses CommonAppBar, CustomButton, KeyboardDismisser.", "CommonAppBar, CustomButton, OutlinedBorderTextField, KeyboardDismisser."),
 ("Type from AppStyle fonts, sizes from ScreenUtil", "Raw TextStyle(fontSize: 20, fontWeight: bold) throughout; zero ScreenUtil uses in the wizard.", "AppStyle.interNormal / interSemi at .sp sizes."),
 ("Strings through TrKeys", "Every wizard string is hard-coded English ('Step 1: Affordability Check').", "TrKeys entries for each string."),
 ("Money through AppHelpers.numberFormat", "'R${x.toStringAsFixed(2)}' prints R3706.40; inputs show 20000.", "AppHelpers.numberFormat gives R3,706.40; inputs format as you type."),
 ("Dates are human", "dueDate.toIso8601String().split('T').first prints 2026-11-22.", "22 Nov 2026 via intl."),
 ("Pinned actions, no dead space", "Button sits under the fields; the rest of the screen is an empty grey void (visible in the store image).", "Primary action pinned at the bottom inside the safe area."),
 ("Errors are friendly", "SnackBar 'Submission failed: $e' prints the exception.", "Plain message plus retry; detail goes to telemetry."),
]

def audit_html():
    rows = "".join(f'<tr><td>{html.escape(a)}</td><td>{html.escape(b)}</td><td>{html.escape(c)}</td></tr>' for a, b, c in AUDIT)
    return (f'<section class="pair" id="audit"><div class="shead"><h2 id="sec-79">79 · Audit against the SDK UI rules <em>— FINDINGS</em></h2>'
            f'<p class="lede">Every application screen was read against what the shared kernel and the one Polaris screen that already follows it (loan_screen.dart) do. The rules below are the fleet conventions in base_sdk, not new ones.</p></div>'
            f'<div class="tw"><table><thead><tr><th>Rule</th><th>What Polaris does now</th><th>Fix in the redesign</th></tr></thead><tbody>{rows}</tbody></table></div></section>')

def before_html():
    def b64(name):
        p = os.path.join(SCR, name)
        if not os.path.exists(p): return ""
        try:
            from PIL import Image
            im = Image.open(p).convert("RGB")
            w, h = im.size
            im = im.crop((int(w*0.13), int(h*0.38), int(w*0.87), h)).resize((330, int(330 * (h*0.62) / (w*0.74))))
            buf = io.BytesIO(); im.save(buf, "JPEG", quality=70)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            return ""
    a, b = b64("06-polaris_affordability.png"), b64("07-polaris_details.png")
    if not a: return ""
    imgs = f'<figure class="bf"><img src="{a}" alt="Committed tour image, affordability step" width="330"><figcaption>Today: affordability, from marketing/tour/store/06</figcaption></figure>'
    if b: imgs += f'<figure class="bf"><img src="{b}" alt="Committed tour image, details step" width="330"><figcaption>Today: details, from marketing/tour/store/07</figcaption></figure>'
    return f'<section class="pair" id="before"><div class="shead"><h2 id="sec-78">78 · What ships today <em>— COMMITTED TOUR IMAGES</em></h2><p class="lede">Cropped from the committed store images in RokctAI/polaris. Blue stock app bar and button, no brand, raw numbers, empty grey below the button.</p></div><div class="row">{imgs}</div></section>'

def palette_html():
    sw = [("Surface","#0b1f1a"),("Card","#10302a"),("Card alt","#0e2a24"),("Hairline","#255548"),("Text 2","#9db8ae"),("Primary (ember)","#ff7a59")]
    chips = "".join(f'<div class="sw"><i style="background:{c}"></i><b>{n}</b><code>{c}</code></div>' for n, c in sw)
    return (f'<section class="pair" id="palette"><div class="shead"><h2 id="sec-90">90 · Palette and tokens <em>— NEEDS RAY</em></h2>'
        f'<p class="lede">The redesign uses the pine and ember already ruled for the Polaris landing page (Ray, 18 Oct), injected through AppStyle.injectBrandColors so the screens only ever name a token. Light mode keeps the kernel neutrals, with the same ember primary. Nothing in the screens is a raw hex.</p></div>'
        f'<div class="sws">{chips}</div></section>')

CSS = open(os.path.join(HERE, "style.css")).read()

def page():
    secs = audit_html() + before_html() + build() + palette_html()
    nav = ("".join(f'<a href="#{i}">{n} · {html.escape(t)}</a>' for i, n, t in
            [("audit", 79, "Audit"), ("before", 78, "Today")] + SECTIONS) + '<a href="#palette">90 · Palette</a>')
    return f'''<title>Polaris Redesign</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header class="top"><p class="kick">Polaris · SDK UI rules</p><h1>Polaris, redesigned to the SDK rules</h1>
<p class="lede big">The loan application was ported from RokctApp as stock Material. Below: what breaks the rules, then every screen redrawn in dark and light on the shared tokens, components and money format. Elements carry chips 2001 and up, screens carry section letters (sections 78 to 90). Nothing here is built yet.</p></header>
<nav class="jb" aria-label="Sections">{nav}</nav>
{page_body(secs)}
</div>'''

def page_body(secs): return secs

if __name__ == "__main__":
    open(OUT, "w").write(page())
    print("wrote", OUT, os.path.getsize(OUT))
