"""Resolve ambiguous touches without replacing already entered text."""

import re


# A small prior for ordinary English, not a dictionary or an autocorrect model.
# Words in the current editor contribute separately, including names.
_COMMON_WORDS = """
about after again against all also always another any are around as ask at away
back be because become been before being between both but by call came can come
could day did different do does doing down each end even every few find first
for found from get give go good got great had hand has have he help her here him
his home how however i if in into is it its just keep kind know large last later
learn left let life like little long look made make many may me mean might more
most much must my name need never new next no not now number of off old on once
one only open or other our out over own part people place point put question
quite read really right said same saw say see seem set she should show since so
some something start still such take tell than that the their them then there
these they thing think this those thought three through time to together too
try turn two under until up us use used very want was way we well went were
what when where which while who why will with without word work world would
write year yes yet you young your
""".split()


def _add_word(prefixes, word, weight):
    for length in range(2, len(word)):
        choices = prefixes.setdefault(word[:length], {})
        choices[word[length]] = choices.get(word[length], 0) + weight


_PREFIXES = {}
for _word in _COMMON_WORDS:
    _add_word(_PREFIXES, _word, 1)


def _letter(key):
    value = key.get("value", "")
    return len(value) == 1 and "a" <= value <= "z"


def _inside(key, x, y):
    return key["x"] <= x < key["x"] + key["width"] and key["y"] <= y < key["y"] + key["height"]


def _next_letters(text, cursor):
    # Qt cursor positions count UTF-16 code units, unlike Python string indices.
    encoded = text.encode("utf-16-le")
    before = encoded[:cursor * 2].decode("utf-16-le", errors="ignore")
    after = encoded[cursor * 2:].decode("utf-16-le", errors="ignore")
    if after and after[0].isalpha():
        return {}  # Editing inside a word should remain literal.
    token = re.search(r"\S+$", before)
    if not token or re.search(r"[\d@:/._\\]", token.group()):
        return {}
    match = re.search(r"\b[a-zA-Z]{2,24}$", before)
    if not match:
        return {}
    prefix = match.group().lower()
    choices = dict(_PREFIXES.get(prefix, {}))
    # Learn only from complete words currently visible to the editor. No text
    # or vocabulary is stored between calls, fields, applications or sessions.
    surrounding = before[:match.start()][-1024:] + " " + after[:1024]
    for word in set(re.findall(r"\b[a-zA-Z]{3,24}\b", surrounding.lower())):
        if word.startswith(prefix) and len(word) > len(prefix):
            next_letter = word[len(prefix)]
            choices[next_letter] = choices.get(next_letter, 0) + 2
    return choices


class TouchResolver:
    def __init__(self):
        self.reset()

    def reset(self):
        self._samples = 0
        self._offset_x = 0.0
        self._offset_y = 0.0

    def _learn(self, dx, dy):
        # Only confident central letter presses calibrate the touch offset.
        # A few stray taps cannot move a key's effective centre substantially.
        if abs(dx) > 0.25 or abs(dy) > 0.25:
            return
        self._samples += 1
        rate = 1.0 / min(self._samples, 32)
        self._offset_x += rate * (dx - self._offset_x)
        self._offset_y += rate * (dy - self._offset_y)

    def resolve(self, keys, x, y, *, assisted=True, adapt=True,
                text="", cursor=0, predictive=False):
        literal = next((index for index, key in enumerate(keys)
                        if _inside(key, x, y)), -1)
        if not assisted:
            return literal
        if literal >= 0:
            key = keys[literal]
            if not _letter(key) or not adapt:
                return literal
            dx = (x - key["x"]) / key["width"] - 0.5
            dy = (y - key["y"]) / key["height"] - 0.5
            # A deliberate central tap always wins, regardless of language or
            # calibration. Context can only affect the narrow boundary area.
            if abs(dx) <= 0.32 and abs(dy) <= 0.32:
                if adapt:
                    self._learn(dx, dy)
                return literal

        confidence = min(1.0, self._samples / 24) if adapt else 0.0
        offset_x = max(-0.10, min(0.10, self._offset_x)) * confidence
        offset_y = max(-0.10, min(0.10, self._offset_y)) * confidence
        choices = _next_letters(text, cursor) if predictive else {}
        largest = max(choices.values(), default=1)
        candidates = []
        for index, key in enumerate(keys):
            dx = (x - key["x"]) / key["width"] - 0.5
            dy = (y - key["y"]) / key["height"] - 0.5
            if abs(dx) > 0.70 or abs(dy) > 0.70:
                continue
            letter = _letter(key)
            score = ((dx - (offset_x if letter else 0)) ** 2
                     + (dy - (offset_y if letter else 0)) ** 2)
            # The bounded prior can move a letter boundary by roughly 6% of a
            # key width, rather than choosing a distant but more likely letter.
            if letter:
                score -= 0.12 * choices.get(key["value"], 0) / largest
            candidates.append((score, index))
        if not candidates:
            return -1
        _, selected = min(candidates)
        # Space, delete, shift, layout changes and submit require their own
        # rectangle. In particular, gaps must never accidentally submit text.
        if keys[selected].get("action") and selected != literal:
            return literal
        return selected
