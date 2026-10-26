"""Демо-витрины для показа клиентам (велосипеды, инструмент, сантехника) и демо-товары по направлениям."""

DEMO_STOREFRONTS = [
    {
        "slug": "velo",
        "name": "Вело-магазин (демо)",
        "tagline": "Велосипеди, запчастини, екіпірування та сервіс",
        "tagline_ru": "Велосипеды, запчасти, экипировка и сервис",
        "verticals": ["bikes"],
        "brand_color": "#15803d",
        "sort_order": 10,
    },
    {
        "slug": "instrument",
        "name": "Інструмент (демо)",
        "tagline": "Ручний та електроінструмент, витратні матеріали",
        "tagline_ru": "Ручной и электроинструмент, расходные материалы",
        "verticals": ["tools"],
        "brand_color": "#c2410c",
        "sort_order": 20,
    },
    {
        "slug": "santekhnika",
        "name": "Сантехніка (демо)",
        "tagline": "Сантехніка, опалення та фільтри для води",
        "tagline_ru": "Сантехника, отопление и фильтры для воды",
        "verticals": ["plumbing"],
        "brand_color": "#1d6fa5",
        "sort_order": 30,
    },
]

# направление → [(слаг категории дерева, товар, [(артикул, вариант, цена)])]
DEMO_PRODUCTS = {
    "bikes": [
        (
            "velosypedy-dorosli",
            'Гірський велосипед 29" алюмінієвий',
            [("DEMO-VELO-01", "рама M", 15900), ("DEMO-VELO-02", "рама L", 15900)],
        ),
        ("velosypedy-dorosli", 'Міський велосипед 28" з кошиком', [("DEMO-VELO-03", None, 12900)]),
        ("dytiachi-velosypedy", 'Дитячий велосипед 20"', [("DEMO-VELO-04", None, 6500)]),
        ("dytiachi-velosypedy", 'Біговел 12"', [("DEMO-VELO-05", None, 2200)]),
        ("elektrotransport", "Електросамокат 350 Вт", [("DEMO-VELO-06", None, 13900)]),
        ("velo-pokryshky", "Покришка 29×2.20", [("DEMO-VELO-07", None, 650)]),
        ("velo-pokryshky", 'Камера 29" Presta', [("DEMO-VELO-08", None, 220)]),
        ("velo-transmisiia", "Ланцюг 9 швидкостей", [("DEMO-VELO-09", None, 790)]),
        ("velo-transmisiia", "Касета 11-36, 9 швидкостей", [("DEMO-VELO-10", None, 1250)]),
        ("velo-halma", "Гальмівні колодки дискові, пара", [("DEMO-VELO-11", None, 260)]),
        ("velo-sholomy", "Велошолом з вентиляцією", [("DEMO-VELO-12", "M", 1450), ("DEMO-VELO-13", "L", 1450)]),
        ("velo-zamky", "Замок U-lock", [("DEMO-VELO-14", None, 890)]),
        ("velo-osvitlennia", "Ліхтар передній USB", [("DEMO-VELO-15", None, 590)]),
        ("velo-nasosy", "Насос ручний з манометром", [("DEMO-VELO-16", None, 680)]),
        ("velo-obsluhovuvannia", "Технічне обслуговування велосипеда", [("DEMO-VELO-17", None, 900)]),
    ],
    "tools": [
        ("dryli-shurupoverty", "Акумуляторний шуруповерт 18 В, 2 акумулятори", [("DEMO-TOOL-01", None, 3990)]),
        ("dryli-shurupoverty", "Перфоратор SDS-Plus 800 Вт", [("DEMO-TOOL-02", None, 4290)]),
        ("bolharky-shlifmashyny", "Болгарка 125 мм 900 Вт", [("DEMO-TOOL-03", None, 1990)]),
        ("pyly-elektro", "Електролобзик 650 Вт", [("DEMO-TOOL-04", None, 1790)]),
        ("nabory-instrumentu", "Набір інструменту 108 предметів у кейсі", [("DEMO-TOOL-05", None, 2490)]),
        ("molotky", "Молоток слюсарний 500 г", [("DEMO-TOOL-06", None, 320)]),
        ("vykrutky-bity", "Набір викруток 6 шт.", [("DEMO-TOOL-07", None, 390)]),
        ("kliuchi", "Ключ розвідний 250 мм", [("DEMO-TOOL-08", None, 420)]),
        ("vymiriuvannia", "Рулетка 5 м з фіксатором", [("DEMO-TOOL-09", None, 180)]),
        ("vymiriuvannia", "Рівень будівельний 60 см", [("DEMO-TOOL-10", None, 450)]),
        ("dysky-sverdla", "Набір свердел по металу 19 шт.", [("DEMO-TOOL-11", None, 520)]),
        ("zasoby-zakhystu", "Окуляри захисні", [("DEMO-TOOL-12", None, 120)]),
    ],
}
