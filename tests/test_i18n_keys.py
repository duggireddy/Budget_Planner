"""EN/DE translation keys must match."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N_JS = ROOT / "static" / "i18n.js"


def _parse_lang_block(text: str, lang: str) -> set[str]:
    m = re.search(rf"\b{lang}:\s*\{{", text)
    assert m, f"missing {lang} block"
    start = m.end()
    depth = 1
    i = start
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    block = text[start : i - 1]
    return set(re.findall(r"^\s*(\w+):", block, re.MULTILINE))


def test_en_and_de_keys_match():
    text = I18N_JS.read_text(encoding="utf-8")
    en = _parse_lang_block(text, "en")
    de = _parse_lang_block(text, "de")
    only_en = en - de
    only_de = de - en
    assert not only_en, f"keys only in EN: {sorted(only_en)[:20]}"
    assert not only_de, f"keys only in DE: {sorted(only_de)[:20]}"


def test_helper_exports():
    text = I18N_JS.read_text(encoding="utf-8")
    for name in (
        "getMonthLabels",
        "chartSliceLabel",
        "summaryRowsForTable",
        "refreshUiLanguage",
    ):
        if name == "refreshUiLanguage":
            assert name in (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        else:
            assert name in text
