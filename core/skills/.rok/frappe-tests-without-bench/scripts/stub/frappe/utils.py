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

import datetime
from dateutil.relativedelta import relativedelta


def getdate(v=None):
    if v is None:
        return datetime.date.today()
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    return datetime.date.fromisoformat(str(v)[:10])


def add_days(d, n):
    return getdate(d) + datetime.timedelta(days=n)


def add_months(d, n):
    return getdate(d) + relativedelta(months=n)


def nowdate():
    return datetime.date.today().isoformat()


def now_datetime():
    return datetime.datetime.now()


def cint(v):
    try:
        return int(float(v))
    except Exception:
        return 0


def flt(v, p=None):
    try:
        return float(v)
    except Exception:
        return 0.0


def fmt_money(amount, precision=2, currency=None, **k):
    return f"{currency + ' ' if currency else ''}{amount:,.2f}"
