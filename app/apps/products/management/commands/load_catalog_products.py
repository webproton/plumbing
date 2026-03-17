import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

# Импорт моделей — если у тебя модели в другом модуле, поправь путь
from app.apps.products.models import (
    Product, ProductVariant, TypeOfProduct,
    Mechanism, MattressBase, UpholsteryMaterial,
    Pattern, BodyMaterial, Filling, Form,
    BedType, Armrest, IncludedItem, ColorOption, ColorProduct,Category
)


RUS_WORD_NUMBERS = {
    "нуль": 0, "ноль": 0, "один": 1, "одна": 1, "два": 2, "две": 2,
    "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8,
    "девять": 9, "десять": 10
}


def parse_mm(value):
    """Из '1940 мм', '1.3 m', '1320' -> Decimal('1940') / Decimal('1.3')"""
    if not value:
        return None
    v = str(value)
    # поиск числа с возможной дробной частью
    m = re.search(r'(\d+(?:[\.,]\d+)?)', v)
    if not m:
        return None
    num = m.group(1).replace(',', '.')
    try:
        return Decimal(num)
    except Exception:
        return None


def parse_int_or_word(value):
    if not value:
        return None
    v = str(value).strip()
    m = re.search(r'(\d+)', v)
    if m:
        try:
            return int(m.group(1))
        except:
            pass
    low = v.lower()
    for k, n in RUS_WORD_NUMBERS.items():
        if k in low:
            return n
    return None


def parse_bool_exist(value):
    if not value:
        return False
    low = value.lower()
    if "есть" in low or "да" in low:
        return True
    # "под заказ" трактуем как False (есть, но по заказу)
    return False


def split_items(value):
    """Разбить строку типа 'Ткань, Микрофибра, Рогожка' -> list[str]"""
    if not value:
        return []
    parts = re.split(r',|;|/|\band\b| и |,|\\n', value)
    return [p.strip() for p in parts if p and p.strip()]


class Command(BaseCommand):
    help = "Загружает первые 6 продуктов из каталогов divany и krovat (парсит description.txt и фото)"

    def handle(self, *args, **options):
        # Путь к каталогам
        roots = [
            ("divany", settings.BASE_DIR / "divany" / "images"),
            ("krovat", settings.BASE_DIR / "krovat" / "images"),
        ]

        type_map = {
            "divany": "Диваны",
            "krovat": "Кровать",
        }


        category_map = {
            "divany": "Диваны",
            "krovat": "Кровать",
        }

        created_count = 0
        max_products = 6

        for root_key, root_path in roots:
            root_path = Path(root_path)
            if not root_path.exists():
                self.stdout.write(self.style.WARNING(f"Папка не найдена: {root_path} — пропускаю"))
                continue

            # сортируем папки для детерминизма
            for folder in sorted([p for p in root_path.iterdir() if p.is_dir()]):
                if created_count >= max_products:
                    break

                try:
                    with transaction.atomic():
                        self.stdout.write(f"Обрабатываю: {folder}")
                        # product name: первые два слова (по подчёркиванию)
                        folder_words = folder.name.split("_")
                        product_name = " ".join(folder_words[:2]).strip()
                        variant_name = folder.name.replace("_", " ").strip()

                        # читаем description.txt (чувствителен к кодировке)
                        description_file = None
                        # сначала пробуем точное имя
                        candidate = folder / "description.txt"
                        if not candidate.exists():
                            # ищем любой .txt в папке
                            candidates = list(folder.glob("*.txt"))
                            if candidates:
                                candidate = candidates[0]
                            else:
                                candidate = None

                        raw_text = ""
                        if candidate:
                            try:
                                raw_text = candidate.read_text(encoding="utf-8", errors="ignore")
                            except Exception:
                                raw_text = candidate.read_text(encoding="cp1251", errors="ignore")

                        # Убираем блоки Short Description и Full Description (включая заголовки)
                        # Берём часть после "Characteristics:" или "Characteristics" или "Характеристики"
                        chars_text = ""
                        # ищем маркер "Characteristics:"
                        if "Characteristics:" in raw_text:
                            chars_text = raw_text.split("Characteristics:", 1)[1]
                        elif "Characteristics" in raw_text:
                            parts = raw_text.split("Characteristics", 1)
                            chars_text = parts[1] if len(parts) > 1 else ""
                        elif "Характеристики" in raw_text:
                            chars_text = raw_text.split("Характеристики", 1)[1]
                        else:
                            # если няма, пытаемся взять всю строку после "Full Description" если есть,
                            # иначе вторую половину текста
                            if "Full Description" in raw_text:
                                chars_text = raw_text.split("Full Description", 1)[1]
                            else:
                                chars_text = raw_text

                        # Парсим пары "Ключ: Значение"
                        characteristics = {}
                        for line in chars_text.splitlines():
                            if not line or line.strip() == "":
                                continue
                            if ":" in line:
                                k, v = line.split(":", 1)
                                characteristics[k.strip()] = v.strip()
                        # Определяем категорию в зависимости от корневой папки
                        cat_name = category_map.get(root_key)
                        category_obj = None
                        if cat_name:
                            category_obj, _ = Category.objects.get_or_create(name=cat_name)

                        # Создаём/получаем Product
                        product, _ = Product.objects.get_or_create(
                            name=product_name,
                            defaults={"description": raw_text,
                                        "category": category_obj
                                      }
                        )

                        # Создаём вариант (сохраняем минимально, потом апдейтим)
                        variant = ProductVariant.objects.create(
                            product=product,
                            variant_name=variant_name,
                            description=raw_text,
                        )

                        # type_of_product: в зависимости от корня
                        type_name = type_map.get(root_key)
                        if type_name:
                            tp_obj, _ = TypeOfProduct.objects.get_or_create(name=type_name)
                            variant.type_of_product = tp_obj

                        # Заполняем числовые поля
                        # Ширина / Высота / Глубина / Спальное место и т.д.
                        # возможные ключи: "Ширина", "Высота", "Глубина длинна", "Глубина", "Ширина спального места", "Длина спального места"
                        if "Ширина" in characteristics:
                            variant.dimensions_width = parse_mm(characteristics.get("Ширина"))
                        if "Width" in characteristics:
                            variant.dimensions_width = variant.dimensions_width or parse_mm(characteristics.get("Width"))
                        if "Высота" in characteristics:
                            variant.dimensions_height = parse_mm(characteristics.get("Высота"))
                        if "Глубина длинна" in characteristics:
                            variant.dimensions_depth = parse_mm(characteristics.get("Глубина длинна"))
                        if "Глубина" in characteristics:
                            variant.dimensions_depth = variant.dimensions_depth or parse_mm(characteristics.get("Глубина"))
                        if "Ширина спального места" in characteristics:
                            variant.bed_width = parse_mm(characteristics.get("Ширина спального места"))
                        if "Длина спального места" in characteristics:
                            variant.bed_length = parse_mm(characteristics.get("Длина спального места"))
                        if "Спальных мест" in characteristics:
                            variant.sleeping_places = parse_int_or_word(characteristics.get("Спальных мест"))
                        if "Ширина спального места" in characteristics:
                            variant.bed_width = parse_mm(characteristics.get("Ширина спального места"))
                        if "Длина спального места" in characteristics:
                            variant.bed_length = parse_mm(characteristics.get("Длина спального места"))
                        if "Высота сидения" in characteristics:
                            variant.seat_height = parse_mm(characteristics.get("Высота сидения"))
                        if "Глубина сиденья" in characteristics:
                            variant.seat_depth = parse_mm(characteristics.get("Глубина сиденья"))

                        # Булевы поля
                        if "Ниша для хранения" in characteristics:
                            variant.storage_niche = parse_bool_exist(characteristics.get("Ниша для хранения"))

                        # FK поля (get_or_create по названию)
                        # Механизм раскладки
                        mech_name = characteristics.get("Механизм раскладки") or characteristics.get("Механизм")
                        if mech_name:
                            mech_obj, _ = Mechanism.objects.get_or_create(name=mech_name)
                            variant.mechanism = mech_obj

                        # Основание под матрас
                        mb_name = characteristics.get("Основание под матрас")
                        if mb_name:
                            mb_obj, _ = MattressBase.objects.get_or_create(name=mb_name)
                            variant.mattress_base = mb_obj

                        # Наполнение
                        fill_name = characteristics.get("Наполнение")
                        if fill_name:
                            fill_obj, _ = Filling.objects.get_or_create(name=fill_name)
                            variant.filling = fill_obj

                        # Форма
                        form_name = characteristics.get("Форма")
                        if form_name:
                            form_obj, _ = Form.objects.get_or_create(name=form_name)
                            variant.form = form_obj

                        # Тип кровати
                        bedtype_name = characteristics.get("Тип кровати")
                        if bedtype_name:
                            bt_obj, _ = BedType.objects.get_or_create(name=bedtype_name)
                            variant.bed_type = bt_obj

                        # Подлокотники
                        armrest_name = characteristics.get("Подлокотники")
                        if armrest_name:
                            arm_obj, _ = Armrest.objects.get_or_create(name=armrest_name)
                            variant.armrests = arm_obj

                        # Особенность -> поместим в поле features
                        special = characteristics.get("Особенность") or characteristics.get("Особенности")
                        if special:
                            variant.features = special

                        # Узор -> Pattern
                        pat = characteristics.get("Узор")
                        if pat:
                            pat_obj, _ = Pattern.objects.get_or_create(name=pat)
                            variant.pattern = pat_obj

                        # Материал корпуса -> BodyMaterial (берем первый, если несколько)
                        body_mat = characteristics.get("Материал корпуса")
                        if body_mat:
                            body_list = split_items(body_mat)
                            if body_list:
                                bm_obj, _ = BodyMaterial.objects.get_or_create(name=body_list[0])
                                variant.body_material = bm_obj

                        # Цвет обивки (ColorProduct) + выбор цвета (ColorOption)
                        color_value = characteristics.get("Цвет обивки")
                        if color_value:
                            color_obj, _ = ColorProduct.objects.get_or_create(color=color_value)
                            variant.color = color_obj

                        color_options_value = characteristics.get("Выбор цвета")
                        if color_options_value:
                            for co in split_items(color_options_value):
                                co_obj, _ = ColorOption.objects.get_or_create(name=co)
                                # M2M добавим после сохранения

                        # Материал обивки -> M2M UpholsteryMaterial
                        mats_value = characteristics.get("Материал обивки")
                        if mats_value:
                            mats = split_items(mats_value)
                            # создаём объекты и добавим после сохранения

                        # В комплект входит -> IncludedItem (M2M)
                        included = characteristics.get("В комплект входит")
                        if included:
                            incs = split_items(included)
                            # добавим после сохранения

                        # save variant (сначала кэшем установленные FK)
                        variant.save()

                        # Добавляем M2M после сохранения
                        # upholstery_materials
                        if mats_value:
                            for name in mats:
                                m_obj, _ = UpholsteryMaterial.objects.get_or_create(name=name)
                                variant.upholstery_materials.add(m_obj)

                        # color_options (если был)
                        if color_options_value:
                            for co in split_items(color_options_value):
                                co_obj, _ = ColorOption.objects.get_or_create(name=co)
                                variant.color_options.add(co_obj)

                        # included_items
                        if included:
                            for inc in incs:
                                inc_obj, _ = IncludedItem.objects.get_or_create(name=inc)
                                variant.included_items.add(inc_obj)

                        # сохраняем финально
                        variant.save()

                        # добавляем одно фото (первое подходящее)
                        image_patterns = ("*.webp", "*.WEBP", "*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG")
                        found_image = None
                        for pat in image_patterns:
                            imgs = list(folder.glob(pat))
                            if imgs:
                                found_image = imgs[0]
                                break
                        if found_image:
                            with open(found_image, "rb") as f:
                                fname = found_image.name
                                variant.photo.save(fname, File(f), save=True)
                                self.stdout.write(f"  - фото добавлено: {fname}")

                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(f"Создан вариант: {variant} (product: {product.name})"))
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"Ошибка обработки {folder}: {exc}"))
                    # не прерываем цикл, просто идём дальше
                    continue

            if created_count >= max_products:
                break

        self.stdout.write(self.style.SUCCESS(f"Готово — создано/обновлено {created_count} вариантов"))
