#!/usr/bin/env python3
"""Генерирует frontend/src/profanity.js из backend/forumapp/profanity.py.

Запускать после любого изменения правил цензуры:
    python scripts/sync_profanity_js.py
Это гарантирует, что клиентская и серверная проверки синхронны.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from forumapp import profanity as P  # noqa: E402

HEADER = (
    "// Клиентская цензура: ЗЕРКАЛИРУЕТ правила backend/forumapp/profanity.py.\n"
    "// НЕ РЕДАКТИРУЙТЕ ВРУЧНУЮ — перегенерируйте: python scripts/sync_profanity_js.py\n"
    "// Используется для мгновенного предупреждения под полем формы; серверная\n"
    "// проверка остаётся обязательной (безопасность).\n"
)

BODY = '''
const PATTERNS = [
%(patterns)s
];

const WHITELIST = new Set([%(whitelist)s]);

const LEET = [["3", "з"], ["6", "б"], ["0", "о"], ["1", "и"], ["4", "ч"], ["7", "т"]];

function normalize(text) {
  let out = text;
  for (const [d, l] of LEET) out = out.split(d).join(l);
  return out;
}

function matchInWhitelistedWord(text, start, end) {
  let i = start;
  while (i > 0 && /[\\p{L}]/u.test(text[i - 1])) i -= 1;
  let j = end;
  while (j < text.length && /[\\p{L}]/u.test(text[j])) j += 1;
  return WHITELIST.has(text.slice(i, j).toLowerCase());
}

export function containsProfanity(text) {
  if (!text) return false;
  const variants = [text, normalize(text)];
  for (const pattern of PATTERNS) {
    for (const source of variants) {
      const re = new RegExp(pattern.source, "giu");
      let m;
      while ((m = re.exec(source)) !== null) {
        if (m[0].length === 0) { re.lastIndex += 1; continue; }
        if (!matchInWhitelistedWord(source, m.index, m.index + m[0].length)) {
          return true;
        }
      }
    }
  }
  return false;
}

export const PROFANITY_MESSAGE =
  "Сообщение содержит нецензурную лексику. Пожалуйста, воздержитесь от мата.";
'''


def js_str(s: str) -> str:
    """Python-строка regex -> JS строковый литерал в двойных кавычках."""
    out = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{out}"'


def main() -> None:
    patterns = ",\n".join(
        f'  new RegExp({js_str(p.replace("(?i)", ""))}, "iu")' for p in P._PATTERNS
    )
    whitelist = ", ".join(js_str(w) for w in sorted(P._WHITELIST))
    body = BODY % {"patterns": patterns, "whitelist": whitelist}
    dest = os.path.join(ROOT, "frontend", "src", "profanity.js")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(HEADER + body)
    print(f"Wrote {dest}: {len(P._PATTERNS)} patterns, {len(P._WHITELIST)} whitelist words")


if __name__ == "__main__":
    main()
