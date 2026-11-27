"""Сборка app-ads.txt iDen Games (GitHub Actions, раз в сутки; только stdlib).

Разделы по порядку: sources/own.txt (AdMob студии), строки CAS с https://cas.ai/app-ads.txt (CAS держит их
актуальными), sources/yandex.txt (РСЯ / Yandex Mobile Ads). Других строк в файле нет.
Строка, убранная из всех источников (например, CAS вычеркнул её из своего списка), уходит и из app-ads.txt.
Дубли убираются. Из директив CAS переносятся inventorypartnerdomain=; OwnerDomain=, ManagerDomain=, CONTACT=\nвыкидываются — они объявляют владельца файла, а файл наш.
Защита: CAS недоступен, отдал подозрительно мало строк или разом пропало больше MAX_LOST записей — выходим
с ошибкой и файл НЕ меняется.
Источник правил — factory/registry/app_ads/ (фабрика iDen Games); sources/*.txt синхронизирует фабрика.
"""
import datetime as dt
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAS_URL = "https://cas.ai/app-ads.txt"
MIN_CAS = 3000  # меньше — значит, что-то не так с ответом CAS
MAX_LOST = 500  # больше пропавших за раз — похоже на обрезанный список, нужна проверка человеком
DIRECTIVE = re.compile(r"^\s*[A-Za-z]+\s*=")
PARTNER = re.compile(r"^[ \t]*inventorypartnerdomain[ \t]*=[ \t]*([^\s#,]+)", re.I | re.M)


def norm(line):
    line = line.split("#", 1)[0].strip()
    if not line or DIRECTIVE.match(line):
        return None
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 3:
        return None
    parts[0], parts[2] = parts[0].lower(), parts[2].upper()
    if parts[2] not in ("DIRECT", "RESELLER"):
        return None
    return ", ".join(p for p in parts[:4] if p)


def records(text):
    return [k for k in (norm(l) for l in text.splitlines()) if k]


def partners(text):
    return list(dict.fromkeys("inventorypartnerdomain=" + d.lower() for d in PARTNER.findall(text)))


def read(name):
    path = os.path.join(ROOT, "sources", name)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def main():
    req = urllib.request.Request(CAS_URL, headers={"User-Agent": "iDenGames-app-ads-builder"})
    with urllib.request.urlopen(req, timeout=60) as r:
        cas = r.read().decode("utf-8", "replace")
    cas_recs = records(cas)
    if len(cas_recs) < MIN_CAS:
        sys.exit(f"CAS отдал {len(cas_recs)} записей (< {MIN_CAS}) — файл не меняю")
    path = os.path.join(ROOT, "app-ads.txt")
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    sections = [("own (AdMob iDen Games)", records(read("own.txt"))), (f"cas ({CAS_URL})", cas_recs),
                ("yandex (РСЯ / Yandex Mobile Ads)", records(read("yandex.txt")))]
    seen, body = set(), []
    if partners(cas):
        body += ["", "#=== директивы CAS"] + partners(cas)
    for name, recs in sections:
        # seen.add возвращает None: условие заодно запоминает строку и убирает дубли внутри раздела
        recs = [x for x in recs if not (x.lower() in seen or seen.add(x.lower()))]
        body += ["", f"#=== {name} — {len(recs)}"] + recs
    head = ["# app-ads.txt iDen Games — обновляется автоматически раз в сутки (.github/workflows/app-ads.yml)",
            "# Не править руками: источники — sources/*.txt и " + CAS_URL]
    text = "\n".join(head + body) + "\n"
    if set(records(old)) == set(records(text)) and set(partners(old)) == set(partners(text)):
        print(f"без изменений: {len(seen)} записей")
        return
    lost = set(x.lower() for x in records(old)) - seen
    if len(lost) > MAX_LOST:
        sys.exit(f"новый файл потерял бы {len(lost)} прежних записей (> {MAX_LOST}) — не меняю")
    for x in sorted(lost):
        print("убрана:", x)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"обновлён {dt.date.today()}: {len(seen)} записей")


if __name__ == "__main__":
    main()
