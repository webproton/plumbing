// // utils/compare.js

// export const getCompareList = () => {
//   return JSON.parse(localStorage.getItem("compare")) || [];
// };

// export const saveCompareList = (list) => {
//   localStorage.setItem("compare", JSON.stringify(list));
// };

// export const toggleCompareItem = (product) => {
//   let current = getCompareList();
//   const exists = current.some((item) => item.variantId === product.first_variant.id);
//   if (exists) {
//     current = current.filter((item) => item.variantId !== product.first_variant.id);
//   } else {
//     current.push({
//       productId: product.id,
//       variantId: product.first_variant.id,
//       productSlug: product.slug || product.first_variant.productSlug,                  // 👈 добавили
//       variantSlug: product.first_variant.slug,    // 👈 добавили
//       name: product.name,
//       price: product.price,
//       photo: product.photo,
//       brand: product.first_variant.brand?.name,
//       dimensions: {
//         width: product.first_variant.dimensions_width,
//         height: product.first_variant.dimensions_height,
//         weight: product.first_variant.dimensions_weight,
//         thickness: product.first_variant.dimensions_thickness,
//       },
//     });
//   }

//   saveCompareList(current);
//   window.dispatchEvent(new Event("compareUpdated"));
// };


export const getCompareList = () => {
  return JSON.parse(localStorage.getItem("compare")) || [];
};

export const saveCompareList = (list) => {
  localStorage.setItem("compare", JSON.stringify(list));
};

// export const toggleCompareItem = (product) => {
//   let current = getCompareList();
//   const variantId = product.first_variant.id;
//   const exists = current.some((item) => item.variantId === variantId);

//   if (exists) {
//     current = current.filter((item) => item.variantId !== variantId);
//   } else {
//     current.push({
//       productId: product.id,
//       variantId,
//       productSlug: product.slug || product.first_variant.productSlug,
//       variantSlug: product.first_variant.slug,
//       name: product.name,
//       price: product.price,
//       photo: product.photo,
//       brand: product.first_variant.brand?.name,
//       dimensions: {
//         width: product.first_variant.dimensions_width,
//         height: product.first_variant.dimensions_height,
//         weight: product.first_variant.dimensions_weight,
//         thickness: product.first_variant.dimensions_thickness,
//       },
//     });
//   }

//   saveCompareList(current);
//   window.dispatchEvent(new Event("compareUpdated"));

//   return !exists; // true если добавлено, false если удалено
// };


export const toggleCompareItem = (product) => {
  let current = getCompareList();
  const variantId = product.first_variant.id;
  const exists = current.some((item) => item.variantId === variantId);

  if (exists) {
    current = current.filter((item) => item.variantId !== variantId);
  } else {
    const variant = product.first_variant;

    // Собираем все поля продукта
    const compareItem = {
      productId: product.id,
      variantId,
      productSlug: product.slug || variant.productSlug,
      variantSlug: variant.slug,
      name: product.name,
      price: product.price,
      photo: variant.photo,
    };

    // Список полей для проверки
    const fields = [
      "brand",
      "manufacturer",
      "material",
      "type_of_product",
      "ball",
      "product_thread",
      "thread_size",
      "entity",
      "features",
      "color",
      "mechanism",
      "mattress_base",
      "storage_niche",
      "armrests",
      "seat_height",
      "seat_depth",
      "filling",
      "bed_type_form",
      "bed_type",
      "pattern",
      "body_material",
      "mattress_hardnesses",
      "max_load",
      "upper_modules",
      "lower_modules",
      "tv_niche",
      "gender",
      "series",
      "production_time_days",
      "countertop_material",
      "room_type",
      "facade_thickness",
      "legs_color",
      "countertop_color",
      "facade_color",
      "price_segment",
      "cover",
      "width_options",
      "armrest_width",
      "seat_width",
      "corner_width",
      "winter_summer_effect",
      "drawers",
      "facade_with_showcase",
      "facade_design",
      "legs_material",
      "furniture_set",
      "doors_count",
      "warranty",
      "warranty_period_months",
      "footboard_height",
      "angle_variants",
      "expanded_height",
      "expanded_width",
      "armrest_height",
      "extra_orthopedic_fillings",
      "interior_style",
      "has_3d_constructor",
      "is_color_customizable",
    ];

    // Перебираем все поля и добавляем только непустые
    fields.forEach((field) => {
      if (variant[field] !== null && variant[field] !== undefined) {
        compareItem[field] = variant[field];
      }
    });

    // Добавляем размеры
    compareItem.dimensions = {};
    ["width", "height", "weight", "thickness", "depth"].forEach((d) => {
      const val = variant[`dimensions_${d}`];
      if (val !== null && val !== undefined) compareItem.dimensions[d] = val;
    });

    current.push(compareItem);
  }

  saveCompareList(current);
  window.dispatchEvent(new Event("compareUpdated"));

  return !exists; // true если добавлено, false если удалено
};
