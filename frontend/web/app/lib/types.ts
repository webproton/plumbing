// Типы ответов Django API (см. app/apps/*/serializers.py). Decimal приходит строкой.

export type Money = string;

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Category {
  id: number;
  slug: string;
  name: string;
  photo: string | null;
  product_list: string;
}

export interface NamedRef {
  id: number;
  name: string | null;
}

export interface Variant {
  id: number;
  slug: string | null;
  variantSlug: string | null;
  productSlug: string | null;
  product: { id: number; slug: string | null; name: string | null };
  product_name: string | null;
  code: string | null;
  price: Money | null;
  original_price: Money | null;
  discount: number;
  available: boolean | null;
  in_stock: boolean;
  available_qty: Money;
  photo: string | null;
  description: string | null;
  features: string | null;
  brand: NamedRef | null;
  color: NamedRef | null;
  dimensions_width: Money | null;
  dimensions_height: Money | null;
  dimensions_depth: Money | null;
  dimensions_weight: Money | null;
}

export interface ProductListItem {
  id: number;
  slug: string;
  name: string;
  category: string | null;
  category_id: number | null;
  price: Money | null;
  photo: string | null;
  first_variant: Variant | null;
}

export interface ProductPhoto {
  id: number;
  photo: string;
}

export interface ProductDetail {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  photo: string | null;
  photos: ProductPhoto[];
  category: Category | null;
  variants: Variant[];
}

export interface CartItem {
  id: number;
  product: number;
  variant: number | null;
  product_name: string | null;
  photo: string | null;
  quantity: number;
  price: Money | null;
  available: Money | null;
}

export interface Cart {
  id: number;
  customer: number | null;
  cart_uuid: string;
  cart_items: CartItem[];
}

export interface OrderLine {
  name: string;
  sku: string;
  photo: string | null;
  quantity: Money;
  price: Money;
  total: Money;
  product_id: number | null;
  variant: { id: number; price: Money };
}

export interface OrderListItem {
  id: number;
  creation_date: string;
  total_price: Money;
  number_products: number | string;
  status_order: string;
  status_order_display: string;
  payment_status: string;
  payment_status_display: string;
  payment_type_display: string;
  can_be_canceled: boolean;
  list_of_product_images: { photo: string; product_id: number | null; variant_id: number }[];
}

export interface OrderDetail {
  number_order: string;
  creation_date: string;
  customer_name: string;
  address: string;
  city: string | null;
  department_number: string | null;
  comment: string | null;
  email: string | null;
  total_price: Money;
  status_order: string;
  status_order_display: string;
  payment_status: string;
  payment_type: string;
  payment_type_display: string;
  list_of_products: OrderLine[];
}

export interface CreatedOrder {
  id: number;
  total_price: Money;
  items: OrderLine[];
}

export interface UserProfile {
  email: string;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  phone_number: string | null;
  city: string | null;
  address: string | null;
}

export interface WishlistItem {
  id: number;
  product_variant: Variant;
  productSlug: string | null;
  variantSlug: string | null;
  added_at: string;
}

export interface SiteSettings {
  phone: string | null;
  email: string | null;
  telegram: string | null;
  whatsapp: string | null;
}

/** Ошибки валидации DRF: {field: ["msg"]} или {detail: "msg"} */
export type FieldErrors = Record<string, string>;
