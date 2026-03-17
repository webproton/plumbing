


export const addToCart = (item, quantity = 1) => {
  const cart = JSON.parse(localStorage.getItem("cart")) || [];

  let cartItem;

  if (item.product_variant) {
    // Для Wishlist
    const variant = item.product_variant;
    cartItem = {
      productId: variant.product?.id || variant.id,
      variantId: variant.id,
      productSlug: variant.product?.slug || "",
      variantSlug: variant.slug || "",
      name: variant.product_name || variant.name || "Product",
      price: parseFloat(variant.price || 0),
      quantity,
      photo: variant.product_photo || variant.photo || "",
    };
  } else if (item.first_variant) {
    // Для NewProducts и CategoryProducts
    const variant = item.first_variant;
    cartItem = {
      productId: item.id,
      variantId: variant.id,
      productSlug: item.slug || "",
      variantSlug: variant.slug || "",
      name: item.name,
      price: parseFloat(variant.price || item.price || 0),
      quantity,
      photo: variant.photo || item.photo || "",
    };
  } else if (item.id && item.selectedVariant) {
    // Для ProductDetail
    const variant = item.selectedVariant;
    cartItem = {
      productId: item.id,
      variantId: variant.id,
      productSlug: item.slug || "",
      variantSlug: variant.slug || "",
      name: item.name,
      price: parseFloat(variant.price || 0),
      quantity,
      photo: variant.photo || (item.photos && item.photos[0]) || "",
    };
  } else {
    console.error("Invalid item structure for addToCart", item);
    return;
  }

  // Проверяем, есть ли товар в корзине
  const existingItem = cart.find(
    c => c.productId === cartItem.productId && c.variantId === cartItem.variantId
  );

  let updatedCart;
  if (existingItem) {
    // Увеличиваем количество, если товар уже есть
    updatedCart = cart.map(c =>
      c.productId === cartItem.productId && c.variantId === cartItem.variantId
        ? { ...c, quantity: c.quantity + cartItem.quantity }
        : c
    );
  } else {
    // Добавляем новый товар
    updatedCart = [...cart, cartItem];
  }

  // Сохраняем в localStorage и диспатчим события
  localStorage.setItem("cart", JSON.stringify(updatedCart));
  window.dispatchEvent(new Event("storage"));
  window.dispatchEvent(new CustomEvent("cartUpdated"));
};



export const removeFromCart = (productId, variantId) => {
  const cart = JSON.parse(localStorage.getItem("cart")) || [];
  const updatedCart = cart.filter(
    item => !(item.productId === productId && item.variantId === variantId)
  );
  localStorage.setItem("cart", JSON.stringify(updatedCart));
  window.dispatchEvent(new Event("storage"));
};

export const updateCartItemQuantity = (productId, variantId, newQuantity) => {
  if (newQuantity < 1) return;

  const cart = JSON.parse(localStorage.getItem("cart")) || [];
  const updatedCart = cart.map(item =>
    item.productId === productId && item.variantId === variantId
      ? { ...item, quantity: newQuantity }
      : item
  );
  localStorage.setItem("cart", JSON.stringify(updatedCart));
  window.dispatchEvent(new Event("storage"));
};

export const syncCart = (component) => {
  const savedCart = JSON.parse(localStorage.getItem("cart")) || [];
  if (JSON.stringify(savedCart) !== JSON.stringify(component.state.cart)) {
    component.setState({ cart: savedCart });
  }
};