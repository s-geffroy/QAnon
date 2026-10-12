"""Formatage des nombres et dates selon la langue."""
import datetime as dt

MONTHS = {
    "fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def num(lang, x, digits=0):
    s = f"{x:,.{digits}f}"
    if lang == "fr":
        s = s.replace(",", " ").replace(".", ",")
    return s


def pct(lang, x, digits=1):
    s = num(lang, 100 * x, digits)
    return f"{s} %" if lang == "fr" else f"{s}%"


def date(lang, value):
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    m = MONTHS[lang][value.month - 1]
    return f"{value.day} {m} {value.year}" if lang == "fr" else f"{m} {value.day}, {value.year}"
