# parsers/utils.py
import copy

from parsers.schema import UNIVERSAL_SCHEMA


def normalize_output(result: dict):
    """
    Добивает недостающие поля до единого стандарта
    """

    def merge(base, data):
        for k, v in base.items():
            if isinstance(v, dict):
                data.setdefault(k, {})
                merge(v, data[k])
            else:
                data.setdefault(k, v)
        return data

    return merge(copy.deepcopy(UNIVERSAL_SCHEMA), result)