import React from "react";
import { getCompareList, saveCompareList } from "../utils/compare";
import Navigation from "./Navigation";
import { Link } from "react-router-dom";

// Маппинг ключей на русские названия
const fieldLabels = {
  brand: "Бренд",
  manufacturer: "Производитель",
  material: "Материал",
  type_of_product: "Тип товара",
  ball: "Мяч",
  product_thread: "Резьба",
  thread_size: "Размер резьбы",
  entity: "Сущность",
  features: "Особенности",
  color: "Цвет",
  mechanism: "Механизм",
  mattress_base: "Основание матраса",
  storage_niche: "Ниша для хранения",
  armrests: "Подлокотники",
  seat_height: "Высота сиденья",
  seat_depth: "Глубина сиденья",
  filling: "Наполнение",
  bed_type_form: "Форма кровати",
  bed_type: "Тип кровати",
  pattern: "Узор",
  body_material: "Материал корпуса",
  mattress_hardnesses: "Жёсткость матраса",
  max_load: "Макс. нагрузка",
  upper_modules: "Верхние модули",
  lower_modules: "Нижние модули",
  tv_niche: "Ниша под ТВ",
  gender: "Пол",
  series: "Серия",
  production_time_days: "Срок производства, дней",
  countertop_material: "Материал столешницы",
  room_type: "Тип комнаты",
  facade_thickness: "Толщина фасада",
  legs_color: "Цвет ножек",
  countertop_color: "Цвет столешницы",
  facade_color: "Цвет фасада",
  price_segment: "Ценовой сегмент",
  cover: "Чехол",
  width_options: "Варианты ширины",
  armrest_width: "Ширина подлокотника",
  seat_width: "Ширина сиденья",
  corner_width: "Ширина угла",
  winter_summer_effect: "Эффект зим/лето",
  drawers: "Ящики",
  facade_with_showcase: "Фасад с витриной",
  facade_design: "Дизайн фасада",
  legs_material: "Материал ножек",
  furniture_set: "Мебельный комплект",
  doors_count: "Количество дверей",
  warranty: "Гарантия",
  warranty_period_months: "Срок гарантии, мес",
  footboard_height: "Высота изножья",
  angle_variants: "Варианты угла",
  expanded_height: "Высота в разложенном виде",
  expanded_width: "Ширина в разложенном виде",
  armrest_height: "Высота подлокотника",
  extra_orthopedic_fillings: "Доп. ортопедические наполнители",
  interior_style: "Стиль интерьера",
  has_3d_constructor: "Есть 3D-конструктор",
  is_color_customizable: "Возможность изменить цвет",
};

const dimensionLabels = {
  width: "Ширина",
  height: "Высота",
  weight: "Вес",
  thickness: "Толщина",
  depth: "Глубина",
};

const ComparePage = () => {
  const compare = getCompareList();

  const handleRemove = (variantId) => {
    const updated = compare.filter((item) => item.variantId !== variantId);
    saveCompareList(updated);
    window.location.reload();
  };


  // Удалить все из сравнения
  const handleRemoveAll = () => {
    saveCompareList([]);
    window.location.reload();
  };

  if (compare.length === 0) return <p>Нет товаров для сравнения.</p>;

  const dynamicKeys = compare.length
    ? Object.keys(compare[0]).filter(
        (key) =>
          !["variantId", "productId", "productSlug", "variantSlug", "photo", "name", "price", "dimensions"].includes(key)
      )
    : [];

  const dimensionKeys = compare.length && compare[0].dimensions ? Object.keys(compare[0].dimensions) : [];

  // === Нормализуем данные: все значения массивы ===
  // Нормализуем данные: все значения массивы, включая name
  const normalizedCompare = compare.map((item) => {
    const newItem = { ...item };
    // Обрабатываем поле name
    if (typeof item.name === "string") {
      const words = item.name.split(/\s+/).filter(Boolean); // Разделяем по пробелам
      newItem.name = words.length > 1 ? words : [item.name]; // Если больше одного слова, создаём массив
    } else {
      newItem.name = [item.name];
    }
    // Обрабатываем динамические поля
    dynamicKeys.forEach((key) => {
      let val = item[key];
      if (Array.isArray(val)) {
        newItem[key] = val.flatMap((v) => {
          if (v && typeof v === "object" && v.name) {
            return v.name.split(/\s*,\s*/).filter(Boolean);
          }
          return v;
        });
      } else if (typeof val === "string") {
        const arr = val.split(/\s*,\s*/).filter(Boolean);
        newItem[key] = arr.length > 0 ? arr : [val];
      } else if (typeof val === "object" && val !== null) {
        if (val.name) {
          newItem[key] = val.name.split(/\s*,\s*/).filter(Boolean);
        } else {
          newItem[key] = [val];
        }
      } else {
        newItem[key] = [val];
      }
    });
    return newItem;
  });

  return (
    <>
      <Navigation />
      <div className="container">
        <h2>Сравнение товаров</h2>
          <button
            onClick={handleRemoveAll}
            style={{
              fontSize: "12px",
              padding: "4px 8px",
              borderRadius: "4px",
              backgroundColor: "#d9363e",
              color: "#fff",
              border: "none",
              cursor: "pointer"
            }}
          >
            Удалить все
          </button>
        {/* === Desktop View === */}
        <div className="compare-table desktop-only">
          <table>
            <tbody>
              {/* Фото */}
              <tr>
                <th>Фото</th>
                {normalizedCompare.map((item) => (
                  <td key={item.variantId}>
                    <img src={item.photo} width="60" alt={item.name} />
                  </td>
                ))}
              </tr>

              {/* Название */}
            <tr>
                <th>Название</th>
                {normalizedCompare.map((item) => (
                  <td key={item.variantId}>
                    <Link to={`/products/${item.productSlug}/variant/${item.variantSlug}`}>
                      {item.name.map((word, i) => (
                        <div key={i} style={{ display: "block" }}>
                          {word}
                        </div>
                      ))}
                    </Link>
                  </td>
                ))}
              </tr>

              {/* Цена */}
              <tr>
                <th>Цена</th>
                {normalizedCompare.map((item) => (
                  <td key={item.variantId}>₴ {item.price}</td>
                ))}
              </tr>

              {/* Динамические поля */}
              {dynamicKeys.map((key) => (
                <tr key={key}>
                  <th>{fieldLabels[key] || key}</th>
                  {normalizedCompare.map((item) => (
                    <td key={item.variantId}>
                      {item[key].map((v, i) => (
                        <div key={i} style={{ display: "block" }}>
                          {v && typeof v === "object" ? v.name || JSON.stringify(v) : v}
                        </div>
                      ))}
                    </td>
                  ))}
                </tr>
              ))}

              {/* Размеры */}
              {dimensionKeys.map((dimKey) => (
                <tr key={dimKey}>
                  <th>{dimensionLabels[dimKey] || dimKey}</th>
                  {normalizedCompare.map((item) => (
                    <td key={item.variantId}>{item.dimensions[dimKey]}</td>
                  ))}
                </tr>
              ))}

              {/* Кнопки удаления */}
              <tr>
                <th></th>
                {normalizedCompare.map((item) => (
                  <td key={item.variantId}>
                    <button
                      className="compare-remove-desktop"
                      onClick={() => handleRemove(item.variantId)}
                      aria-label="Удалить из сравнения"
                    >
                      ❌
                    </button>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>

        {/* === Mobile View === */}
        <div className="compare-mobile mobile-only">
          <div className="compare-scroll">
            {normalizedCompare.map((item) => (
              <div key={item.variantId} className="compare-card">
                <img src={item.photo} alt={item.name} className="compare-photo" />
                <div className="compare-info">
                  <strong>Название:</strong>{" "}
                  <Link to={`/products/${item.productSlug}/variant/${item.variantSlug}`}>
                    {item.name}
                  </Link>
                </div>
                <div className="compare-info">
                  <strong>Цена:</strong> ₴ {item.price}
                </div>

                {/* Динамические поля */}
                {dynamicKeys.map((key) => (
                  <div key={key} className="compare-info">
                    <strong>{fieldLabels[key] || key}:</strong>
                    {item[key].map((v, i) => (
                      <div key={i}>
                        {v && typeof v === "object" ? v.name || JSON.stringify(v) : v}
                      </div>
                    ))}
                  </div>
                ))}

                {/* Размеры */}
                {dimensionKeys.map((dimKey) => (
                  <div key={dimKey} className="compare-info">
                    <strong>{dimensionLabels[dimKey] || dimKey}:</strong> {item.dimensions[dimKey]}
                  </div>
                ))}

                <button
                  onClick={() => handleRemove(item.variantId)}
                  className="compare-remove-btn"
                >
                  ❌
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
};

export default ComparePage;
