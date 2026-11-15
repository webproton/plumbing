"""
Умный поиск товаров — в каталоге и в кабинете продавца.

Люди ищут по-своему, не так, как написано в карточке:
- слова в любом порядке и с любыми окончаниями: «змішувач кухня» → «Змішувач для кухні»;
- по-русски: «смеситель», «водонагреватель», «группа безопасности» → украинские названия;
- синонимы: «бойлер» = «водонагрівач», «раковина» = «умивальник».
Каждое слово запроса должно найтись (в названии, бренде, артикуле); у слова — несколько вариантов написания.
- слитно или раздельно: «twbkt» = «TWB KT» = «TWB-KT» = «twb.kt» (compact_q, лукап __compact);
- с опечаткой: ничего не нашлось по «twb» → «Можливо, ви шукали «tbw»?» и товары по исправленному запросу (suggest).
"""

import re
from collections import Counter
from collections.abc import Callable, Iterable

from django.core.cache import cache

from django.db.models import CharField, Lookup, Q, TextField

_WORD = re.compile(r"[\w'’\-.]+", re.UNICODE)
_ENDINGS = set("аеєиіїоуюяыэёьй")
MAX_WORDS = 6


def stem(word: str) -> str:
    """Основа без окончания: «кухні»/«кухня»/«кухни» → «кухн», «воды»/«вода» → «вод». Коды — как есть."""
    word = word.lower().replace("ё", "е").replace("’", "'").strip("'-.")
    if len(word) <= 3 or any(ch.isdigit() for ch in word):
        return word
    for _ in range(2 if len(word) > 4 else 1):  # от коротких слов отрезаем не больше одной буквы
        if len(word) > 3 and word[-1] in _ENDINGS:
            word = word[:-1]
    return word


# основа слова → другие основы (рус. → укр., синонимы). Ключи и значения — основы (через stem).
_RAW_SYNONYMS = {
    "смеситель": ["змішувач"],
    "кран-смеситель": ["змішувач"],
    "змішувач": ["кран-змішувач"],
    "водонагреватель": ["водонагрівач", "бойлер"],
    "водонагрівач": ["бойлер"],
    "бойлер": ["водонагрівач"],
    "раковина": ["умивальник", "раковин"],
    "умивальник": ["раковин"],
    "мойка": ["мийк"],
    "мийка": ["мойк"],
    "унитаз": ["унітаз"],
    "смывной": ["змивн"],
    "бачок": ["бачок", "бачк"],
    "полотенцесушитель": ["рушникосушк", "сушарк"],
    "рушникосушка": ["полотенцесуш", "сушарк"],
    "фильтр": ["фільтр"],
    "картридж": ["картридж"],
    "насосная": ["насосн"],
    "погружной": ["занурювальн", "свердловин"],
    "скважинный": ["свердловин", "занурювальн"],
    "дренажный": ["дренажн"],
    "циркуляционный": ["циркуляційн"],
    "гидроаккумулятор": ["гідроакумулятор", "гідробак", "розширювальн"],
    "гідроакумулятор": ["гідробак"],
    "расширительный": ["розширювальн"],
    "группа": ["груп"],
    "безопасности": ["безпек"],
    "радиатор": ["радіатор"],
    "батарея": ["радіатор"],
    "котел": ["котел", "котл"],
    "коллектор": ["колектор"],
    "теплый": ["тепл"],
    "пол": ["підлог"],
    "труба": ["труб"],
    "фитинг": ["фітинг"],
    "уголок": ["кутник", "кут"],
    "колено": ["коліно", "кутник"],
    "тройник": ["трійник"],
    "переходник": ["перехідник"],
    "заглушка": ["заглушк"],
    "сифон": ["сифон"],
    "шланг": ["шланг"],
    "подводка": ["підводк", "гнучк"],
    "гибкая": ["гнучк"],
    "клапан": ["клапан"],
    "обратный": ["зворотн"],
    "задвижка": ["засувк"],
    "вентиль": ["вентил"],
    "счетчик": ["лічильник"],
    "лічильник": ["счетчик"],
    "редуктор": ["редуктор"],
    "давления": ["тиск"],
    "душевой": ["душов"],
    "лейка": ["лійк"],
    "ванна": ["ванн"],
    "ванной": ["ванн"],
    "кухня": ["кухн"],
    "латунь": ["латун"],
    "латунный": ["латун"],
    "нержавейка": ["нерж"],
    "полипропилен": ["поліпропілен", "ppr"],
    "металлопластик": ["металопласт"],
    "пайка": ["пайк"],
    "наружная": ["зовнішн"],
    "внутренняя": ["внутрішн"],
    "резьба": ["різьб"],
    "шаровый": ["кульов"],
    "шаровой": ["кульов"],
    "отопление": ["опаленн"],
    "отопления": ["опаленн"],
    "канализация": ["каналізац"],
    "канализационный": ["каналізаційн"],
    "водопровод": ["водопровід", "водопостачанн"],
    "сгон": ["згон"],
    "прокладка": ["прокладк"],
    "уплотнитель": ["ущільнювач"],
    "резиновый": ["гумов"],
    "пакля": ["клоччя", "льон"],
    "кронштейн": ["кронштейн", "кріпленн"],
    "крепление": ["кріпленн"],
}
SYNONYMS: dict[str, set[str]] = {}
for _word, _others in _RAW_SYNONYMS.items():
    SYNONYMS.setdefault(stem(_word), set()).update(stem(o) for o in _others)


def query_words(query: str) -> list[set[str]]:
    """Запрос → для каждого слова набор вариантов основы. Предлоги и одиночные буквы пропускаем."""
    words = [w for w in _WORD.findall(query or "") if len(w) > 1 or w.isdigit()][:MAX_WORDS]
    result = []
    for word in words:
        base = stem(word)
        if base in {"для", "на", "из", "из-под", "под", "від", "под", "з", "із", "до", "в", "и", "і", "та"}:
            continue
        options = {base, *SYNONYMS.get(base, ())}
        if "ы" in base or "э" in base:  # рус. «трубы», «экран» → укр. «труби», «екран»
            options.add(base.replace("ы", "и").replace("э", "е"))
        result.append(options)
    return result


def match_all(query: str, field_q: Callable[[str], Q]) -> Q | None:
    """Q: каждое слово (любой его вариант) находится через field_q(основа). None — искать нечего."""
    words = query_words(query)
    if not words:
        return None
    result = Q()
    for options in words:
        any_option = Q()
        for option in sorted(options):
            any_option |= field_q(option)
        result &= any_option
    return result


# --- слитно или раздельно: «twbkt» находит «TWB KT», «TWB-KT», «twb.kt», «AB-12/5» — «ab125» ---
# разделители: пробел, неразрывный пробел, дефисы и тире, точка, запятая, слеши, подчёркивание, апострофы
SEPARATORS = (" ", " ", "-", "‑", "–", ".", ",", "/", "\\", "_", "'", "’", "ʼ")
MIN_COMPACT = 3  # короче — совпадёт почти со всем


def compact(text: str) -> str:
    """Без регистра, пробелов, дефисов, точек, слешей и апострофов."""
    text = (text or "").lower()
    for sep in SEPARATORS:
        text = text.replace(sep, "")
    return text


class Compact(Lookup):
    """field__compact="twbkt": поле без разделителей (как compact) содержит строку. Работает и через связи
    (variants__code__compact). SQL — вложенные REPLACE, индекс не нужен: те же затраты, что у icontains."""

    lookup_name = "compact"
    prepare_rhs = False

    def as_sql(self, compiler, connection):
        lhs, params = self.process_lhs(compiler, connection)
        sql = f"LOWER({lhs})"
        params = list(params)
        for sep in SEPARATORS:
            sql = f"REPLACE({sql}, %s, %s)"
            params += [sep, ""]
        value = connection.ops.prep_for_like_query(compact(str(self.rhs)))
        return f"{sql} LIKE %s ESCAPE '\\'", [*params, f"%{value}%"]


def register_lookups() -> None:
    CharField.register_lookup(Compact)
    TextField.register_lookup(Compact)


def compact_q(query: str, *fields: str) -> Q | None:
    """Q «любое из полей содержит запрос без разделителей». None — запрос слишком короткий."""
    value = compact(query)
    if len(value) < MIN_COMPACT:
        return None
    result = Q()
    for field in fields:
        result |= Q(**{f"{field}__compact": value})
    return result


# --- опечатки: «twb» вместо «tbw», «змішуач» вместо «змішувач» → подсказка и товары по исправленному запросу ---
_PART = re.compile(r"[^\W_]+", re.UNICODE)
VOCAB_TTL = 600  # словарь каталога пересобирается раз в 10 минут — новые товары подсказываются не сразу


def vocab_tokens(texts: Iterable[str | None]) -> Counter:
    """Словарь: слова из названий, артикулов, брендов (+ артикулы слитно: «TBW-KT-35» → «tbwkt35»), сколько раз встречаются."""
    counts: Counter = Counter()
    for text in texts:
        if not text:
            continue
        lower = str(text).lower().replace("ё", "е")
        counts.update(word for word in _PART.findall(lower) if len(word) >= 2)
        counts.update(glued for chunk in lower.split() if len(glued := compact(chunk)) >= 3 and glued != chunk)
    return counts


def cached_vocab(key: str, texts: Callable[[], Iterable[str | None]]) -> Counter:
    vocab = cache.get(key)
    if vocab is None:
        vocab = vocab_tokens(texts())
        cache.set(key, vocab, VOCAB_TTL)
    return vocab


def typo_distance(a: str, b: str, limit: int = 2) -> int:
    """Сколько правок между словами (замена, вставка, удаление, две соседние буквы местами); больше limit — limit + 1."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    before, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if before is not None and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], before[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        before, prev = prev, cur
    return prev[-1]


def _closest(word: str, vocab: Counter) -> str | None:
    """Ближайшее слово словаря или начало слова («twb» → «tbw» из «tbwkt35»); при равенстве — самое частое."""
    limit = 1 if len(word) <= 5 else 2
    best, best_key = None, None
    for token, count in vocab.items():
        options = [(token, False)]
        if len(token) > len(word):
            options.append((token[: len(word)], True))  # человек набрал начало артикула или слова
        for option, is_prefix in options:
            distance = typo_distance(word, option, limit)
            if distance > limit or distance == 0:
                continue
            key = (distance, is_prefix, -count, len(option))
            if best_key is None or key < best_key:
                best, best_key = option, key
    return best


def suggest(query: str, vocab: Counter) -> str | None:
    """Исправленный запрос или None. Слово, которое встречается в словаре (целиком или частью), не трогаем;
    незнакомое — заменяем ближайшим (1 опечатка, в словах длиннее 5 букв — 2). Вызывать, когда ничего не нашлось."""
    words = [w.replace("ё", "е") for w in _PART.findall((query or "").lower())][:MAX_WORDS]
    if not words or not vocab:
        return None
    result, changed = [], False
    for word in words:
        known = len(word) < 3 or word.isdigit() or any(word in token for token in vocab)
        fixed = None if known else _closest(word, vocab)
        result.append(fixed or word)
        changed = changed or bool(fixed)
    return " ".join(result) if changed else None


def did_you_mean(query: str, vocab: Counter, rare: int = 2) -> str | None:
    """Нашлось мало, потому что слово редкое — опечатка в самой карточке («змішуачем»), а у остальных «змішувач»:
    предлагаем частое написание ссылкой «Можливо, ви шукали …?» (без замены результатов)."""
    words = [w.replace("ё", "е") for w in _PART.findall((query or "").lower())][:MAX_WORDS]
    result, changed = [], False
    for word in words:
        fixed = None
        if len(word) >= 4 and not word.isdigit():
            seen = sum(count for token, count in vocab.items() if word in token)
            candidate = _closest(word, vocab) if seen <= rare else None
            if candidate and vocab.get(candidate, 0) >= max(5, 5 * seen):
                fixed = candidate
        result.append(fixed or word)
        changed = changed or bool(fixed)
    return " ".join(result) if changed else None


def with_suggestion(run_list, request, param: str, vocab: Callable[[], Counter]):
    """Список DRF: по ?param= ничего не нашлось → тот же список по исправленному запросу; в ответе — suggestion
    (фронтенд пишет «Нічого не знайшли за «twb». Показуємо «tbw»»)."""
    response = run_list()
    query = request.query_params.get(param, "").strip()
    if not query or not isinstance(response.data, dict):
        return response
    if 0 < (response.data.get("count") or 0) <= 3:
        if alt := did_you_mean(query, vocab()):
            response.data["did_you_mean"] = alt  # нашлось 1–3 по редкому слову — предложить частое
        return response
    if response.data.get("count") != 0:
        return response
    fixed = suggest(query, vocab())
    if not fixed:
        return response
    params = request._request.GET.copy()
    params[param] = fixed
    request._request.GET = params
    retry = run_list()
    if not retry.data.get("count"):
        return response
    retry.data["suggestion"] = fixed
    return retry

