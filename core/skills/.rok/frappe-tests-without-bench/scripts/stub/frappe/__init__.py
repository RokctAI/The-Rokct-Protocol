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

"""Minimal frappe stand-in for running polaris's mock-based unit tests without a bench."""

from types import SimpleNamespace


class _dict(dict):
    __getattr__ = dict.get

    def __setattr__(self, k, v):
        self[k] = v


class ValidationError(Exception):
    pass


class DoesNotExistError(ValidationError):
    pass


def throw(msg, exc=ValidationError, *a, **k):
    raise exc(msg)


def whitelist(*a, **k):
    if a and callable(a[0]):
        return a[0]
    return lambda f: f


def _(s, *a):
    return s


class _DB:
    def get_value(self, *a, **k):
        raise NotImplementedError("db.get_value")

    def set_value(self, *a, **k):
        raise NotImplementedError("db.set_value")

    def exists(self, *a, **k):
        raise NotImplementedError("db.exists")

    def savepoint(self, *a, **k):
        pass

    def rollback(self, *a, **k):
        pass


db = _DB()
conf = _dict()
form_dict = _dict()
session = SimpleNamespace(user="test@example.com")


def get_all(*a, **k):
    raise NotImplementedError("get_all")


def get_attr(path):
    mod, _, attr = path.rpartition(".")
    import importlib

    return getattr(importlib.import_module(mod), attr)


def log_error(*a, **k):
    pass


def get_doc(*a, **k):
    raise NotImplementedError("get_doc")


def bold(s):
    return s


# --- additions for the ID check tests ---
class AuthenticationError(Exception):
    pass


class PermissionError(Exception):
    pass


local = SimpleNamespace(site="test.site", request=None)


def get_roles(*a, **k):
    return []


def get_request_header(*a, **k):
    return None


def get_list(*a, **k):
    raise NotImplementedError("get_list")


def get_single_value(*a, **k):
    raise NotImplementedError


def cache():
    raise NotImplementedError("cache")
