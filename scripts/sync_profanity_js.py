#!/usr/bin/env python3
"""Генерирует frontend/src/profanity.js из backend/forumapp/profanity.py.

Запускать после любого изменения правил цензуры:
    python scripts/sync_profanity_js.py

Это гарантирует, что клиентская и серверная проверки синхронны.

Конвертер Python-regex -> JS (ES2018+, флаги "iu"):
  * удаляет inline (?i) (флаг i задаётся в new RegExp);
  * \\d/\\w вне классов -> [0-9]/[A-Za-z0-9_] (ASCII-семантика как в Python);
  * переводит диапазоны а-я -> а-яё (включая инверсные классы);
  * убирает недопустимые экранирования внутри классов (\\@ \\# \\$ \\- ...);
  * нормализует порядок элементов в классах (символы, ranges, спецсимволы),
    чинит опечатки вида [. -.] (перевёрнутый диапазон -> литералы);
  * перед проверками ставит re.lastIndex = 0 (паттерны с глобальным флагом
    иначе «запоминают» позицию и зацикливают translitHit — реальный баг,
    из-за которого страница висела на бесконечном цикле);
  * ограничивает длину текста 5000 символов (по ТЗ максимум 2000);
  * проверяет каждый паттерн компилятором V8 (node new RegExp);
  * прогоняет JS-зеркало на контрольных кейсах против Python-эталона.

ВАЖНО: клиент зеркалит только _PATTERNS + _LATIN_PATTERNS + _TRANSLIT_RE.
Мягкий мат (_SOFT_PATTERNS) остаётся строгой серверной проверкой (strict=True).
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from forumapp import profanity as P  # noqa: E402

HEADER = (
    "// Клиентская цензура: ЗЕРКАЛИРУЕТ правила backend/forumapp/profanity.py.\n"
    "// НЕ РЕДАКТИРУЙТЕ ВРУЧНУЮ — перегенерируйте: python scripts/sync_profanity_js.py\n"
    "// Используется для мгновенного предупреждения под полем формы; серверная\n"
    "// проверка остаётся обязательной (безопасность).\n"
    "// Клиент зеркалит и мягкий мат (_SOFT_PATTERNS) — как сервер при strict=True.\n"
)

BODY = '''
const PATTERNS = [
%(patterns)s,
%(soft)s
];

const LATIN_PATTERNS = [
%(latin)s
];

const TRANSLIT_RE = %(translit)s;

const WHITELIST = new Set([%(whitelist)s]);

const LEET = [["3", "з"], ["6", "б"], ["0", "о"], ["1", "и"], ["4", "ч"], ["7", "т"]];

function normalize(text) {
  let out = text;
  for (const [d, l] of LEET) out = out.split(d).join(l);
  return out;
}

// как Python str.isalpha(): только буквы Unicode (включая Ё)
function isAlpha(ch) { return ch !== undefined && /\\p{L}/u.test(ch); }

// как Python str.isalnum() для BMP-символов
function isAlnum(ch) { return ch !== undefined && /[\\p{L}\\p{N}]/u.test(ch); }

// Токен слова по границам isalnum()+@#$* (зеркало _token_whitelisted).
function alnumToken(text, start, end) {
  let i = start;
  while (i > 0 && (isAlnum(text[i - 1]) || "@#$*".includes(text[i - 1]))) i -= 1;
  let j = end;
  while (j < text.length && (isAlnum(text[j]) || "@#$*".includes(text[j]))) j += 1;
  return text.slice(i, j);
}

// Совпадение лежит целиком внутри чистого whitelist-слова (границы = только
// буквы) — зеркало Python _match_in_whitelisted_word.
function cleanAlphaWordWhitelisted(text, start, end) {
  let i = start;
  while (i > 0 && isAlpha(text[i - 1])) i -= 1;
  let j = end;
  while (j < text.length && isAlpha(text[j])) j += 1;
  return WHITELIST.has(text.slice(i, j).toLowerCase());
}

// Безопасная проверка паттерна: все совпадения через matchAll (без ручного
// exec/lastIndex — именно он зацикливал страницу). Логика — точное зеркало
// Python contains_profanity для _PATTERNS:
//   * совпадение игнорируется, если оно полностью внутри чистого
//     whitelist-слова (_match_in_whitelisted_word);
//   * дополнительно пропускаем, если алnum-токен совпадения короче самого
//     совпадения или сам токен есть в whitelist (зеркало _token_whitelisted —
//     защищает транслитные маски вроде cyka от ложных срабатываний).
function patternHits(pattern, source) {
  const re = new RegExp(pattern.source, pattern.flags.includes("g") ? pattern.flags : pattern.flags + "g");
  for (const m of source.matchAll(re)) {
    if (m[0].length === 0) continue;
    // Точное зеркало Python: совпадение игнорируется только если оно целиком
    // лежит внутри чистого whitelist-слова (_match_in_whitelisted_word).
    // Алnum-токен проверяется лишь когда совпадение НЕ содержит спецсимволов
    // (иначе обфускация вроде "п.и.з.д.а" ошибочно считалась бы легальным).
    if (cleanAlphaWordWhitelisted(source, m.index, m.index + m[0].length)) continue;
    if (!/[\\W\\d_@#$*]/u.test(m[0])) {
      const tok = alnumToken(source, m.index, m.index + m[0].length);
      if (tok.length < m[0].length) continue;
      if (WHITELIST.has(tok.toLowerCase())) continue;
    }
    return true;
  }
  return false;
}

// Транслит: зеркало _translit_hit — проверка _token_whitelisted (алnum+@#$*).
function translitHit(text) {
  const re = new RegExp(TRANSLIT_RE.source, TRANSLIT_RE.flags.includes("g") ? TRANSLIT_RE.flags : TRANSLIT_RE.flags + "g");
  for (const m of text.matchAll(re)) {
    if (m[0].length === 0) continue;
    if (WHITELIST.has(alnumToken(text, m.index, m.index + m[0].length).toLowerCase())) continue;
    return true;
  }
  return false;
}

function latinHit(text) {
  for (const p of LATIN_PATTERNS) {
    if (patternHits(p, text)) return true;
  }
  return false;
}

export function containsProfanity(text) {
  if (!text) return false;
  text = String(text).slice(0, 5000); // защита от ReDoS по длинным вставкам
  if (latinHit(text)) return true;
  if (translitHit(text)) return true;
  const variants = [text, normalize(text)];
  for (const p of PATTERNS) {
    for (const src of variants) {
      if (patternHits(p, src)) return true;
    }
  }
  return false;
}

const PROFANITY_MESSAGE =
  "Сообщение содержит нецензурную брань. Пожалуйста, выражайтесь вежливо.";

export { PROFANITY_MESSAGE };
export default containsProfanity;
'''


def js_str(s: str) -> str:
    """Python str -> JS string literal (двойные кавычки, \\uXXXX для не-ASCII)."""
    out = []
    for ch in s:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif 0x20 <= o < 0x7F:
            out.append(ch)
        elif o <= 0xFFFF:
            out.append("\\u%04x" % o)
        else:
            out.append("\\u{%x}" % o)
    return '"' + "".join(out) + '"'


# ---------- конвертер regex ----------

_CLASS_OK_ESCAPES = set("bBdDwWsSnrtfvabfn")  # допустимые escapes внутри [...] в JS


def _split_top_level_alts(body: str):
    parts, depth, cur, i = [], 0, [], 0
    n = len(body)
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n:
            cur.append(body[i:i + 2]); i += 2; continue
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        if c == "|" and depth == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(c)
        i += 1
    parts.append("".join(cur))
    return parts


def _rewrite_boundary_lookbehinds(src: str) -> str:
    """(?<=^X) или альтернативы с ^ -> (?:(?<=X)|(?:^)) (JS lookbehind не любит ^)."""
    def repl(m):
        inner = m.group(1)
        alts = _split_top_level_alts(inner)
        has_start = any(a.startswith("^") for a in alts)
        cleaned = "|".join(a.lstrip("^") for a in alts)
        if has_start and cleaned:
            return "(?:(?<=%s)|(?:^))" % cleaned
        return m.group(0)
    return re.sub(r"\(\?<=([^()]+)\)", repl, src)


def _class_items(inner: str):
    letters, ranges, specials = [], [], []
    i, n = 0, len(inner)
    while i < n:
        c = inner[i]
        if c == "\\" and i + 1 < n:
            nxt = inner[i + 1]
            if nxt in _CLASS_OK_ESCAPES:
                specials.append("\\" + nxt); i += 2; continue
            i += 1; c = nxt  # недопустимое экранирование -> литерал
        if i + 2 < n and inner[i + 1] == "-" and inner[i + 2] != "]":
            lo, hi = c, inner[i + 2]
            if ord(lo) <= ord(hi):
                ranges.append((lo, hi)); i += 3; continue
            specials.extend([lo, "-"]); i += 2; continue  # перевёрнутый range
        if c.isalnum() or c in "Ёё":
            letters.append(c)
        else:
            specials.append(c)
        i += 1
    return letters, ranges, specials


def _expand_ru_ranges(ranges):
    out = []
    for lo, hi in ranges:
        if (lo, hi) == ("\u0430", "\u044f"):      # а-я -> а-я + ё
            out.append(("\u0430", "\u044f")); out.append(("\u0451", "\u0451"))
        elif lo == "\u0430" and hi == "\u044e":   # а-ю тоже включает я..ю, но без ё
            out.append(("\u0430", "\u044f")); out.append(("\u0451", "\u0451"))
        else:
            out.append((lo, hi))
    seen, uniq = set(), []
    for r in out:
        if r not in seen:
            seen.add(r); uniq.append(r)
    return uniq


def _dedup(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x); out.append(x)
    return out


def _normalize_class_body(inner: str, neg: bool) -> str:
    letters, ranges, specials = _class_items(inner)
    ranges = _expand_ru_ranges(ranges)
    parts = sorted(set(letters))
    for lo, hi in ranges:
        parts.append("%s-%s" % (lo, hi))
    fixed = []
    for s in specials:
        if s.startswith("\\"):
            fixed.append(s)
        elif s in "[]^$.|?*+(){}":
            fixed.append("\\" + s)
        else:
            fixed.append(s)
    # '-' всегда последним литералом класса
    had_dash = "-" in fixed
    fixed = [f for f in _dedup(fixed) if f != "-"]
    body = "".join(_dedup(parts)) + "".join(fixed)
    if had_dash:
        body += "-"
    return ("^" if neg else "") + body


def _rebuild_classes(src: str) -> str:
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == "\\" and i + 1 < n:
            out.append(src[i:i + 2]); i += 2; continue
        if c == "[":
            j = i + 1
            neg = j < n and src[j] == "^"
            if neg:
                j += 1
            if j < n and src[j] == "]":
                j += 1
            k = j
            while k < n:
                if src[k] == "\\":
                    k += 2; continue
                if src[k] == "]":
                    break
                k += 1
            inner = src[j:k]
            out.append("[")
            out.append(_normalize_class_body(inner, neg))
            out.append("]")
            i = k + 1
            continue
        out.append(c); i += 1
    return "".join(out)


def _asciiize_shorthands(src: str) -> str:
    out, i, n = [], 0, len(src)
    in_class = False
    while i < n:
        c = src[i]
        if c == "\\" and i + 1 < n:
            nxt = src[i + 1]
            if not in_class:
                if nxt == "d":
                    out.append("[0-9]"); i += 2; continue
                if nxt == "D":
                    out.append("[^0-9]"); i += 2; continue
                if nxt == "w":
                    out.append("[A-Za-z0-9_]"); i += 2; continue
                if nxt == "W":
                    out.append("[^A-Za-z0-9_]"); i += 2; continue
            out.append(src[i:i + 2]); i += 2; continue
        if c == "[":
            in_class = True
        elif c == "]" and in_class:
            in_class = False
        out.append(c); i += 1
    return "".join(out)


def py_to_js(src: str) -> str:
    s = re.sub(r"\(\?i\)", "", src)              # флаг i вынесен в RegExp
    s = _rewrite_boundary_lookbehinds(s)         # (?<=^..) -> (^)-альтернатива
    s = _asciiize_shorthands(s)                  # внеклассовые \d \w
    s = _rebuild_classes(s)                      # чистка классов + а-яё
    s = s.replace("(?P<", "(?<")                 # именованные группы
    s = re.sub(r"(?<!\\)\\Z", "$", s)            # Python \Z -> JS $
    return s


def _verify_in_node(pattern: str) -> None:
    code = ("try{new RegExp(%s,'iu')}catch(e){console.log('ERR:'+e.message);process.exit(0)}"
            "console.log('OK')" % js_str(pattern))
    try:
        r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        print("WARNING: node не найден, пропуск V8-проверки")
        return
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out.endswith("OK"):
        raise SystemExit("SYNC ABORTED: паттерн не компилируется V8:\n  %r\n  -> %s %s"
                         % (pattern, out, (r.stderr or "")[:200]))


CASES_HIT = ["хуй", "нахуй", "пизда", "ебать", "заебал", "ёбаный", "блядь",
             "сука", "мудак", "говно", "шлюха", "срать", "ху@й", "б@ять",
             "п.и.з.д.а", "zaebal", "pizdec", "blyat", "xyi", "fuck", "shit", "bitch"]
CASES_CLEAN = ["привет", "хлеб", "мебель", "лебедь", "ответ", "среда", "блин",
               "proxy", "проектирование", "выезд", "урожай", "мудрый", "гондон",
               "бледный", "член", "сукно", "Django REST Framework", "PostgreSQL"]


def main() -> None:
    patterns = [py_to_js(p) for p in P._PATTERNS]
    latin = [py_to_js(p.pattern) for p in P._LATIN_PATTERNS]
    translit = py_to_js(P._TRANSLIT_RE.pattern)

    for pat in patterns + latin + [translit]:
        _verify_in_node(pat)
    print("V8 OK: %d паттернов компилируются" % (len(patterns) + len(latin) + 1))

    # Python-эталон должен проходить свои же кейсы (soft-паттерны включены strict=True)
    miss = [t for t in CASES_HIT if not P.contains_profanity(t, strict=True)]
    fp = [t for t in CASES_CLEAN if P.contains_profanity(t, strict=True)]
    if miss or fp:
        raise SystemExit("SYNC ABORTED: Python-эталон не проходит кейсы: miss=%r fp=%r" % (miss, fp))

    soft = [py_to_js(p) for p in P._SOFT_PATTERNS]
    for pat in soft:
        _verify_in_node(pat)
    module_src = HEADER + BODY % {
        "patterns": ",\n".join("  new RegExp(%s, \"iu\")" % js_str(p) for p in patterns),
        "soft": ",\n".join("  new RegExp(%s, \"iu\")" % js_str(p) for p in soft),
        "latin": ",\n".join("  new RegExp(%s, \"iu\")" % js_str(p) for p in latin),
        "translit": "new RegExp(%s, \"iu\")" % js_str(translit),
        "whitelist": ", ".join(js_str(w) for w in sorted(P._WHITELIST)),
    }

    dst = os.path.join(ROOT, "frontend", "src", "profanity.js")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(module_src)

    # самопроверка JS-зеркала через node на тех же кейсах
    tmp = "/tmp/_profanity_check.mjs"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(module_src)
    check_code = (
        "import cp from '%s';\n"
        "const hit=%s, clean=%s;\n"
        "const miss=hit.filter(t=>!cp(t));\n"
        "const fp=clean.filter(t=>cp(t));\n"
        "if(miss.length||fp.length){console.log('MISMATCH miss='+JSON.stringify(miss)+' fp='+JSON.stringify(fp));}\n"
        "else{console.log('JS MIRROR OK '+hit.length+' hit / '+clean.length+' clean');}\n"
    ) % (tmp, json.dumps(CASES_HIT, ensure_ascii=False), json.dumps(CASES_CLEAN, ensure_ascii=False))
    r = subprocess.run(["node", "--input-type=module", "-e", check_code],
                       capture_output=True, text=True, timeout=60)
    out = (r.stdout or "").strip()
    if "JS MIRROR OK" not in out:
        raise SystemExit("SYNC ABORTED: JS-зеркало расходится с Python:\n  %s\n  %s" % (out, (r.stderr or "")[:400]))
    print(out)
    print("OK: сгенерирован %s (%d байт)" % (dst, os.path.getsize(dst)))


if __name__ == "__main__":
    main()
