from django.db import models
from transliterate import translit 
from model_utils import Choices
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from decimal import Decimal,ROUND_HALF_UP
from app.apps.sellers.models import Seller
import random
import string
import uuid
from io import BytesIO
# import barcode
from barcode import get_barcode_class
from barcode.writer import ImageWriter
import qrcode
from django.core.files import File
from model_utils.models import StatusModel, TimeStampedModel

User = get_user_model()

class BedType(models.Model):
    name = models.CharField(max_length=255, verbose_name="Тип кровати")
    def __str__(self):
        return self.name

class Pattern(models.Model):
    name = models.CharField(max_length=255, verbose_name="Узор (однотонный, в полоску и т.д.)")

    def __str__(self):
        return self.name
    
class Mechanism(models.Model):
    name = models.CharField(max_length=255, verbose_name="Механизм раскладки")
    def __str__(self):
        return self.name

class MattressBase(models.Model):
    name = models.CharField(max_length=255, verbose_name="Основание под матрас")
    def __str__(self):
        return self.name

class UpholsteryMaterial(models.Model):
    name = models.CharField(max_length=255, verbose_name="Материал обивки")
    def __str__(self):
        return self.name


class Form(models.Model):
    name = models.CharField(max_length=255, verbose_name="Форма")
    def __str__(self):
        return self.name

class Filling(models.Model):
    name = models.CharField(max_length=255, verbose_name="Наполнение")
    def __str__(self):
        return self.name

class Armrest(models.Model):
    name = models.CharField(max_length=255, verbose_name="Подлокотники")
    def __str__(self):
        return self.name

class IncludedItem(models.Model):
    name = models.CharField(max_length=255, verbose_name="В комплект входит")
    def __str__(self):
        return self.name

class ColorOption(models.Model):
    name = models.CharField(max_length=255, verbose_name="Выбор цвета")
    def __str__(self):
        return self.name

class BodyMaterial(models.Model):
    name = models.CharField(max_length=255, verbose_name="Материал корпуса")
    def __str__(self):
        return self.name

class MattressHardness(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Жесткость матраса")

    def __str__(self):
        return self.name
    
class AngleVariant(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Вариант угла")

    def __str__(self):
        return self.name


class FurnitureSetItem(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Элемент комплектации гарнитура")

    def __str__(self):
        return self.name
    
class ExtraOrthopedicFilling(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Название наполнителя")

    def __str__(self):
        return self.name

class InteriorStyle(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Название стиля")

    def __str__(self):
        return self.name

# Create your models here.
class Category(TimeStampedModel):
    """категорії продукта """

    name = models.CharField(max_length=255, verbose_name="category name")
    description = models.TextField(verbose_name="description", blank=True, null=True)
    photo = models.ImageField(upload_to="category/", verbose_name="photo", blank=True, null=True)
    slug = models.SlugField(max_length=255,unique=True,blank=True,null=True)
    barcode_type = models.CharField(max_length=20, choices=[("EAN13","EAN13"),("CODE128","CODE128"),("QR","QR")], default="QR")
    barcode_image = models.ImageField(upload_to="categories/barcodes/", blank=True, null=True)
    barcode = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="Штрихкод")

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        if not self.barcode:
            # Генерируем уникальный код для категории
            self.barcode = f"C{uuid.uuid4().int % 10**12:012d}"

        super().save(*args, **kwargs)
    def generate_barcode_image(self):
        buffer = BytesIO()
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(self.barcode)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(buffer, format="PNG")
        buffer.seek(0)
        filename = f"{self.slug}_{self.barcode}.png"
        self.barcode_image.save(filename, File(buffer), save=False)
        # if self.photo:
        #     img = Image.open(self.photo.path)
        #     new_size = (355, 187)
        #     img.thumbnail(new_size)
        #     new_img = Image.new("RGB", new_size, (255, 255, 255))
        #     paste_position = ((new_size[0] - img.width) // 2,
        #                     (new_size[1] - img.height) // 2)
        #     new_img.paste(img, paste_position)
        #     new_img.save(self.photo.path)


    def __str__(self):
        return self.name


class Brand(models.Model):
    """бренд фірма деталі  один із атрибутів продукта """
    name = models.CharField(max_length=255, verbose_name="brand name", blank=True, null=True)
    description = models.TextField(verbose_name="description", blank=True, null=True)

    def __str__(self):
        return self.name


class Thread(models.Model):
    """size thread резьби"""

    SIZE_THREAD = Choices("1/8", "1/4", "3/8", "1/2", "5/8", "3/4", "1", "1 1/4", "1 1/2", "2", "3", "4", "5")

    inches = models.CharField(choices=SIZE_THREAD, verbose_name="inches", max_length=255,
                              help_text="дюйми 1/2...", blank=True, null=True)

    def __str__(self):

        return self.inches


class TypeOfProduct(models.Model):
    """ тип продукту??? скоріш за все видалити
    або маєця на увазі муфта кран  кут і таке інше """
    TYPEPRODUCT = Choices("kranu", "smesitelya", "tryba",)
    name = models.CharField(max_length=255, choices=TYPEPRODUCT, verbose_name="product type", blank=True, null=True)
    custom_type_product = models.CharField(max_length=255, verbose_name="custom product type", blank=True, null=True)
    # product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='type_of_product',blank=True,null=True)

    def __str__(self):
        return self.name


class Manufacturer(models.Model):
    "Виробник"
    # name = models.CharField(max_length=255,blank=True,null=True)
    brand_name = models.ForeignKey(Brand, blank=True, null=True, related_name='brand',
                                   on_delete=models.CASCADE, verbose_name='Brand title')
    country = models.CharField(max_length=255, blank=True, null=True)
    # products = models.ManyToManyField(Product, related_name='manufacturers',blank=True,null=True)

    def __str__(self):
        return self.country


class ProductThread(models.Model):
    """різьба продукту внутрішня наружня В/Н ...
    один із атрибутів продукта """
    THREAD_TYPE = Choices("B", "H", "BH", "BB", "HH", "BBH", "BBB", "HHH", "HHB", "BHB", "BHH")
    thread_type = models.CharField(choices=THREAD_TYPE, verbose_name="internal or external",
                                   max_length=255, blank=True, null=True)

    def __str__(self):
        return self.thread_type


class MaterialProduct(models.Model):
    '''один із атрибутів продукта'''

    name = models.CharField(max_length=255, verbose_name="Матеріал з чого..")

    def __str__(self):
        return self.name
class Ball(models.Model):
    '''один із атрибутів продукта'''
    ball_material_type = models.ForeignKey(MaterialProduct, on_delete=models.CASCADE,
                                           related_name='ball', verbose_name="ball", blank=True, null=True)
    def __str__(self):
        return str(self.ball_material_type)


class ColorProduct(models.Model):
    """ один із атрибутів продукта """
    name = models.CharField(max_length=255, verbose_name='Color product', blank=True, null=True)
    def __str__(self):
        return str(self.name)




class Product(TimeStampedModel):
    """products
        базова модель продукту 
        в цілому все влаштовує )  """
        
#     seller = models.ForeignKey(
#     Seller,
#     on_delete=models.CASCADE,
#     related_name="products", blank=True, null=True
# )
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='products', blank=True, null=True)  # ← обязательно!
    name = models.CharField(max_length=255, verbose_name="product name", blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products',
                                 verbose_name="category", blank=True, null=True)

    description = models.TextField(verbose_name="description", blank=True, null=True)
    photo = models.ImageField(upload_to='products/', verbose_name="photo", blank=True, null=True)

    slug = models.SlugField(max_length=255,unique=True,blank=True,null=True)


    def __str__(self):
        return self.name



    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            # Транслитерируем кириллицу в латиницу
            translit_name = translit(self.name, 'ru', reversed=True)
            base_slug = slugify(translit_name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
# products/models.py → в ProductVariant
class ProductVariant(TimeStampedModel):
    """
    Вариант продукта.
    У одного продукта может быть несколько вариантов (цвет, размер, материал, комплектация).
    Используется для отображения разных конфигураций товара в магазине.
    """
    
    
    CURRENCY_CHOICES = [
        ('UAH', 'Гривна ₴'),
        ('USD', 'Доллар $'),
        ('EUR', 'Евро €'),
    ]
    
    # Валюта, в которой ведется закупка этого товара
    purchase_currency = models.CharField(
        max_length=3, 
        choices=CURRENCY_CHOICES, 
        default='UAH',
        verbose_name="Валюта закупки",
        blank=True,
        null=True
    )
    
    
    slug = models.SlugField(max_length=255,blank=True,null=True)
    code = models.CharField(max_length=50, verbose_name="Код товара", unique=True, blank=True, null=True)
    
    
    barcode = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="Штрихкод (EAN13 / SKU)")
    #Скорее всего дублирование логики вместо stock & reserved  испол StockMovement (журнал склада)
    stock = models.PositiveIntegerField(default=0, verbose_name="Общий остаток")
    reserved = models.PositiveIntegerField(default=0)
    
    
    barcode_image = models.ImageField(upload_to="products/barcodes/", blank=True, null=True)
    barcode_type = models.CharField(
        max_length=20,
        choices=[("EAN13","EAN13"),("CODE128","CODE128"),("QR","QR")],
        default="CODE128",
        verbose_name="Тип штрихкода"
    )
    # 📦 Основные данные
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='variants'
    )
    variant_name = models.CharField(
        max_length=255, null=True, blank=True,
        verbose_name="VariantName=prd.name + type etc"
    )
    description = models.TextField(verbose_name="Описание", blank=True, null=True)

    # 📐 Общие размеры
    dimensions_width = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Ширина",
        blank=True, null=True, default=10
    )
    dimensions_height = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Высота",
        blank=True, null=True, default=10
    )
    dimensions_weight = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Вес",
        blank=True, null=True, default=10
    )
    dimensions_thickness = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Толщина",
        blank=True, null=True, default=10
    )
    dimensions_depth = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Глубина",
        blank=True, null=True
    )

    # 🛏 Размеры для кровати
    sleeping_places = models.PositiveIntegerField(
        blank=True, null=True, verbose_name="Количество спальных мест"
    )
    bed_width = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Ширина спального места"
    )
    bed_length = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Длина спального места"
    )
    custom_size_available = models.BooleanField(
        default=False, verbose_name="Изготовление нестандартных размеров"
    )

    # 🏭 Производитель / бренд / материал
    brand = models.ForeignKey(
        Brand, on_delete=models.CASCADE, related_name='product_variants',
        verbose_name="Бренд", blank=True, null=True
    )
    manufacturer = models.ForeignKey(
        Manufacturer, on_delete=models.CASCADE, blank=True, null=True,
        verbose_name="Производитель", related_name='product_variants'
    )
    material = models.ForeignKey(
        MaterialProduct, on_delete=models.CASCADE,
        related_name='product_variants', verbose_name="Материал",
        blank=True, null=True
    )

    # ⚙️ Технические характеристики
    type_of_product = models.ForeignKey(
        TypeOfProduct, on_delete=models.CASCADE,
        verbose_name="Тип продукта (уголок/сгон/тройник)",
        related_name='product_variants', blank=True, null=True
    )
    ball = models.ForeignKey(
        Ball, on_delete=models.CASCADE, related_name='product_variant',
        verbose_name="Шар", blank=True, null=True
    )
    product_thread = models.ForeignKey(
        ProductThread, verbose_name="Резьба (B/H)",
        on_delete=models.CASCADE, blank=True, null=True,
        related_name='product_variants'
    )
    thread_size = models.ForeignKey(
        Thread, on_delete=models.CASCADE, verbose_name="Размер резьбы",
        blank=True, null=True, related_name='product_variants'
    )
    entity = models.PositiveIntegerField(
        verbose_name="Количество единиц", blank=True, null=True, default=10
    )
    features = models.TextField(verbose_name="Особенности", blank=True, null=True)

    # 🎨 Цвета и фото
    color = models.ForeignKey(
        ColorProduct, on_delete=models.CASCADE, related_name="product_variants",
        verbose_name='Цвет продукта', blank=True, null=True
    )
    color_options = models.ManyToManyField(
        ColorOption, blank=True, related_name='product_variants',
        verbose_name="Выбор цвета"
    )
    photo = models.ImageField(
        upload_to="product_variants/", null=True, blank=True
    )

    # 🪑 Опции мебели
    mechanism = models.ForeignKey(
        Mechanism, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='product_variants', verbose_name="Механизм трансформации"
    )
    mattress_base = models.ForeignKey(
        MattressBase, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='product_variants', verbose_name="Основание матраса"
    )
    upholstery_materials = models.ManyToManyField(
        UpholsteryMaterial, blank=True, related_name='product_variants',
        verbose_name="Материалы обивки"
    )
    storage_niche = models.BooleanField(
        default=False, blank=True, null=True, verbose_name="Ниша для хранения"
    )
    armrests = models.ForeignKey(
        Armrest, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='product_variants', verbose_name="Подлокотники"
    )
    seat_height = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Высота сидения"
    )
    seat_depth = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Глубина сиденья"
    )
    filling = models.ForeignKey(
        Filling, on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="product_variants",
        verbose_name="Наполнение"
    )
    bed_type_form = models.ForeignKey(
        Form, on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="product_variants",
        verbose_name="Форма"
    )
    bed_type = models.ForeignKey(
        BedType, on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="product_variants",
        verbose_name="Тип кровати"
    )
    pattern = models.ForeignKey(
        Pattern, on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="product_variants",
        verbose_name="Узор"
    )

    body_material = models.ForeignKey(
        BodyMaterial, on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="product_variants",
        verbose_name="Материал корпуса"
    )
    # ℹ️ Доп. данные
    included_items = models.ManyToManyField(
        IncludedItem, blank=True, related_name='product_variants',
        verbose_name="В комплект входит"
    )
    like_user = ArrayField(
        models.IntegerField(), default=list,
        verbose_name="Лайки пользователей", blank=True, null=True
    )



    # 🔹 Новые поля
    # Жесткость матраса
    mattress_hardnesses = models.ManyToManyField(
        MattressHardness,
        blank=True,
        related_name='product_variants',
        verbose_name="Жесткость матраса"
    )


    # Максимальная нагрузка
    max_load = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Максимальная нагрузка (кг)"
    )

    # Нижние модули (ManyToMany на ProductVariant или отдельную модель Module)
    upper_modules = models.CharField(max_length=255, blank=True, null=True, verbose_name="Верхние модули")
    lower_modules = models.CharField(max_length=255, blank=True, null=True, verbose_name="Нижние модули")


    # Ниша для телевизора
    tv_niche = models.BooleanField(
        default=False, blank=True, null=True, verbose_name="Ниша для телевизора"
    )

    # Пол
    gender = models.CharField(
        max_length=20, blank=True, null=True,
        choices=[('male', 'Мужской'), ('female', 'Женский'), ('unisex', 'Универсальный')],
        verbose_name="Пол"
    )

    # Серия
    series = models.CharField(max_length=255, blank=True, null=True, verbose_name="Серия")

    # Состояние
    # condition = models.CharField(
    #     max_length=255, blank=True, null=True,
    #     choices=[('new', 'Новый'), ('used', 'Б/У'), ('sale', 'Распродажа')],
    #     verbose_name="Состояние"
    # )

    # Срок изготовления
    production_time_days = models.DecimalField(
        max_digits=15, decimal_places=0, blank=True, null=True,
        verbose_name="Срок изготовления (дни)"
    )

    # Столешница
    countertop_material = models.ForeignKey(
        MaterialProduct, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='countertop_variants',
        verbose_name="Столешница (материал)"
    )

    # Тип помещения
    room_type = models.CharField(
        max_length=255, blank=True, null=True,
        choices=[('kitchen', 'Кухня'), ('living', 'Гостиная'), ('bedroom', 'Спальня')],
        verbose_name="Тип помещения"
    )

    # Толщина фасада
    facade_thickness = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True,
        verbose_name="Толщина фасада (мм)"
    )

    # Цвет ножек
    legs_color = models.ForeignKey(
        ColorOption, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='legs_color_variants',
        verbose_name="Цвет ножек"
    )

    # Цвет столешницы
    countertop_color = models.ForeignKey(
        ColorOption, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='countertop_color_variants',
        verbose_name="Цвет столешницы"
    )

    # Цвет фасада
    facade_color = models.ForeignKey(
        ColorOption, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='facade_color_variants',
        verbose_name="Цвет фасада"
    )

    # Ценовой сегмент
    price_segment = models.CharField(
        max_length=255, blank=True, null=True,
        choices=[('budget', 'Недорогие'), ('mid', 'Средний'), ('premium', 'Премиум')],
        verbose_name="Ценовой сегмент"
    )

    # Чехол
    cover = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Чехол"
    )

    # Ширина на выбор
    width_options = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Ширина на выбор (мм)"
    )

    # Ширина подлокотника
    armrest_width = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Ширина подлокотника (мм)"
    )

    # Ширина сиденья
    seat_width = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Ширина сиденья (мм)"
    )

    # Ширина угла кухни
    corner_width = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Ширина угла кухни (мм)"
    )

    # Эффект Зима-Лето
    winter_summer_effect = models.BooleanField(
        default=False, blank=True, null=True,
        verbose_name="Эффект Зима-Лето"
    )

    # Ящики на направляющих
    drawers = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Ящики на направляющих"
    )

    # Фасад с витриной
    facade_with_showcase = models.BooleanField(
        default=False, blank=True, null=True, verbose_name="Фасад с витриной"
    )

    # Оформление фасада
    facade_design = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Оформление фасада"
    )

    # Материал ножек
    legs_material = models.ForeignKey(
        MaterialProduct, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='legs_material_variants',
        verbose_name="Материал ножек"
    )

    # Комплектация гарнитура
    furniture_set = models.ManyToManyField(
        FurnitureSetItem, blank=True, related_name='product_variants',
        verbose_name="Комплектация гарнитура"
    )

    # Количество дверей
    doors_count = models.PositiveIntegerField(
        blank=True, null=True, verbose_name="Количество дверей"
    )

    # Гарантия и срок
    warranty = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Гарантия"
    )
    warranty_period_months = models.DecimalField(
        max_digits=15, decimal_places=0, blank=True, null=True, verbose_name="Гарантийный срок (месяцы)"
    )

    # Высота изножья кровати
    footboard_height = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Высота изножья кровати"
    )

    # Варианты угла
    angle_variants = models.ManyToManyField(
        AngleVariant, blank=True, related_name='product_variants',
        verbose_name="Варианты угла"
    )
    # 🔹 Новые поля (дополнения)

    # Высота в разложенном виде
    expanded_height = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Высота в разложенном виде"
    )
    expanded_width = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Ширина в разложенном виде"
    )
    # Высота подлокотника
    armrest_height = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Высота подлокотника"
    )

    # Дополнительное ортопедическое наполнение на выбор
    extra_orthopedic_fillings = models.ManyToManyField(
        'ExtraOrthopedicFilling', blank=True, related_name='product_variants',
        verbose_name="Дополнительное ортопедическое наполнение на выбор"
    )

    # Интерьерный стиль
    interior_style = models.ForeignKey(
        'InteriorStyle', blank=True, null=True, on_delete=models.SET_NULL,
        related_name='product_variants',
        verbose_name="Интерьерный стиль"
    )

    # Конструктор 3D
    has_3d_constructor = models.BooleanField(
        default=False, blank=True, null=True,
        verbose_name="Конструктор 3D"
    )

    is_color_customizable = models.BooleanField(default=False, verbose_name="Цвет по заказу")


    


    # 💲 Цена и наличие
    price = models.DecimalField(
        verbose_name="Цена продажи", max_digits=20, decimal_places=4,
        blank=True, null=True, default=100
    )
    discount = models.PositiveIntegerField(default=0, verbose_name="Скидка %")
    original_price = models.DecimalField(max_digits=20, decimal_places=4, blank=True, null=True, verbose_name="Оригинальная цена(Старая цена (маркетинг)")
    
    # Новое поле:
    cost_price = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True, verbose_name="Себестоимость (закупка)")
    
    available = models.BooleanField(
        verbose_name="В наличии", default=True, blank=True, null=True
    )

    class Meta:
        unique_together = ('product', 'slug')

   

    def save(self, *args, **kwargs):
        # Генерация slug
        if not self.slug:
            text_to_slug = f"{self.product.name}-{self.variant_name}" if self.variant_name else self.product.name
            translit_text = translit(text_to_slug, 'ru', reversed=True)
            base_slug = slugify(translit_text)
            slug = base_slug
            counter = 1
            while ProductVariant.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        # Генерация кода и штрихкода
        if not self.code:
            self.code = self.generate_unique_code()
        if not self.barcode:
            self.barcode = self.generate_barcode()
        if not self.barcode_image:
            self.generate_barcode_image()

        # Цены и скидки
        if self.discount > 0 and not self.original_price:
            self.original_price = Decimal(str(self.price)) if self.price is not None else None
            if self.original_price is not None:
                self.price = self.original_price * (Decimal('1.0') - Decimal(self.discount) / Decimal('100'))
        elif self.discount == 0 and self.original_price:
            self.price = Decimal(str(self.original_price)) if self.original_price is not None else None
            self.original_price = None

        # Округление цен
        if self.price is not None:
            self.price = Decimal(str(self.price)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        if self.original_price is not None:
            self.original_price = Decimal(str(self.original_price)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
            
            
        # 🔥 ДОБАВИТЬ: Защитная проверка себестоимости
        if self.cost_price is not None:
            self.cost_price = Decimal(str(self.cost_price)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
            if self.price is not None and self.cost_price > self.price:
                # Можно просто кидать предупреждение в лог или вызывать ValidationError
                # Но для работы через API лучше оставить как предупреждение или не давать сохранять:
                pass

        super().save(*args, **kwargs)
    
    # def generate_unique_code(self):
    #     prefix = "PRD"  # можно любой префикс
    #     while True:
    #         random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    #         code = f"{prefix}-{self.product.id}-{random_part}"
    #         if not ProductVariant.objects.filter(code=code).exists():
    #             return code
            
          
    
    
    def generate_unique_code(self):
        prefix = "P"
        product_part = f"{self.product_id:04d}"[-4:]

        random_part = ''.join(
            random.choices(string.ascii_uppercase + string.digits, k=8)
        )

        return f"{prefix}{product_part}{random_part}"
        
    def generate_code(self):
        return f"P{uuid.uuid4().hex[:8].upper()}"


    def generate_barcode(self):
        return f"2{uuid.uuid4().int % 10**12:012d}"
    
    
    def generate_barcode_image(self):
        """
        Генерация картинки штрихкода или QR-кода для печати.
        """
        if not self.barcode:
            self.barcode = self.generate_barcode()

        buffer = BytesIO()

        if self.barcode_type == "QR":
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(self.barcode)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(buffer, format="PNG")
        else:
            
            bc_class = get_barcode_class(self.barcode_type)
            # Для EAN13 нужно убрать любые буквы и взять 12 цифр
            code_value = self.barcode
            if self.barcode_type == "EAN13":
                code_value = ''.join(filter(str.isdigit, self.barcode))[:12]
            bc = bc_class(code_value, writer=ImageWriter())
            bc.write(buffer)
            
            
            
            
            
            # bc_class = barcode.get_barcode_class(self.barcode_type)
            # bc = bc_class(self.barcode, writer=ImageWriter())
            # bc.write(buffer)

        buffer.seek(0)
        filename = f"{self.slug}_{self.barcode}.png"
        self.barcode_image.save(filename, File(buffer), save=False)
            
    def __str__(self):
        return f"{self.product.name} - Variant"

    
class Wishlist(TimeStampedModel):
    # Залогиненный пользователь → user записывается.

    # Анонимный пользователь → session_key сохраняется.
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name="User"
    )
    # session_key = models.CharField(
    #     max_length=40, null=True, blank=True,
    #     verbose_name="Session Key"
    # )
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, verbose_name="ProductVariant")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Time Added")

    class Meta:
        unique_together = (("user", "product_variant"))

    def __str__(self):
        return f"{self.user } — {self.product_variant}"
    
    
    
class ProductPhoto(models.Model):
    """Product Photos
     стандартизація фото по певному формату і розміру"""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='photos')
    product_var = models.ForeignKey(ProductVariant, on_delete=models.CASCADE,blank=True, null=True, related_name='photos_variant')

    photo = models.ImageField(upload_to='products_new/', verbose_name="photo")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # if self.photo:
        #     img = Image.open(self.photo.path)

        #     # Resize the image to 100x100 pixels
        #     new_size = (355, 187)
        #     img.thumbnail(new_size)
        #     new_img = Image.new("RGB", new_size, (255, 255, 255))
        #     paste_position = (
        #         (new_size[0] - img.width) // 2,
        #         (new_size[1] - img.height) // 2
        #     )
        #     new_img.paste(img, paste_position)
        #     new_img.save(self.photo.path)
    def __str__(self):
        return f"Photo for {self.product.name}"    