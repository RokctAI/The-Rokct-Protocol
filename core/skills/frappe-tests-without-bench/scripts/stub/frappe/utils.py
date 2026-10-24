import datetime
from dateutil.relativedelta import relativedelta
def getdate(v=None):
    if v is None: return datetime.date.today()
    if isinstance(v, datetime.datetime): return v.date()
    if isinstance(v, datetime.date): return v
    return datetime.date.fromisoformat(str(v)[:10])
def add_days(d, n): return getdate(d) + datetime.timedelta(days=n)
def add_months(d, n): return getdate(d) + relativedelta(months=n)
def nowdate(): return datetime.date.today().isoformat()
def now_datetime(): return datetime.datetime.now()
def cint(v):
    try: return int(float(v))
    except Exception: return 0
def flt(v, p=None):
    try: return float(v)
    except Exception: return 0.0
def fmt_money(amount, precision=2, currency=None, **k):
    return f"{currency+' ' if currency else ''}{amount:,.2f}"
