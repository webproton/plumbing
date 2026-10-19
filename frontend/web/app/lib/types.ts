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

// ---------- склад / кабинет продавца ----------

export interface WarehouseMe {
  is_staff_user: boolean;
  is_superuser: boolean;
  seller: { id: number; shop_name: string } | null;
  seller_pending: boolean;
  warehouses: { id: number; name: string; is_default: boolean }[];
}

export interface StockRow {
  id: number;
  variant: number;
  variant_name: string;
  sku: string | null;
  barcode: string | null;
  warehouse: number;
  warehouse_name: string;
  quantity: string;
  reserved: string;
  cost_price: string | null;
  price: string | null;
  value: string | null;
}

export type MovementType =
  | "in"
  | "out"
  | "return_in"
  | "return_out"
  | "adjustment"
  | "adjustment_out"
  | "transfer_in"
  | "transfer_out";

export interface MovementRow {
  id: number;
  movement_type: MovementType;
  quantity: string;
  price_per_unit: string | null;
  document_number: string | null;
  comment: string;
  created_at: string;
  variant: number;
  variant_name: string | null;
  warehouse: number;
  warehouse_name: string;
  supplier_name: string | null;
  created_by_email: string | null;
}

export interface WarehouseDashboard {
  positions: number;
  units: string | number;
  value: string | number;
  reserved_units: string | number;
  documents_pending: number;
  documents_need_review: number;
  recent_movements: MovementRow[];
}

export interface VariantLookup {
  id: number;
  name: string;
  sku: string | null;
  barcode: string | null;
  cost_price: string | null;
  price: string | null;
  stock: string;
  reserved: string;
  available: string;
}

export interface Supplier {
  id: number;
  name: string;
  code: string;
  contact_person: string;
  phone: string;
  email: string;
  address: string;
  is_active: boolean;
}

export interface WarehouseRow {
  id: number;
  name: string;
  address: string;
  is_default: boolean;
}

export type LineStatus = "matched" | "needs_review" | "new" | "invalid";
export type MatchMethod = "memory" | "barcode" | "sku" | "fuzzy" | "manual";
export interface ProcessingReport {
  received: number;
  created: number;
  skipped: { row: number; reason: string }[];
}

export interface InvoiceLine {
  position: number;
  name: string;
  sku: string;
  barcode: string;
  unit: string;
  currency: string;
  qty: string | null;
  price: string | null;
  status: LineStatus;
  variant_id: number | null;
  method: MatchMethod | null;
  confidence: number;
  candidates: { variant_id: number; score: number }[];
  error: string | null;
}

export type ParseEngine = "parser" | "universal" | "manual" | "profile" | "ai";
export type ColumnRole = "name" | "qty" | "price" | "total" | "sku" | "barcode" | "unit";
export interface ColumnMap {
  header_row: number | null;
  columns: Partial<Record<ColumnRole, number>>;
}
export interface ParseQuality {
  verdict: "ok" | "warning" | "bad" | "empty";
  score: number;
  lines: number;
  consistent: number;
  inconsistent_positions: number[];
  missing: number;
  sum_items: number;
  doc_total: number | null;
  sum_match: boolean | null;
}
export interface InvoiceTable {
  needs_ai: boolean;
  columns: number[];
  rows: { index: number; cells: string[] }[];
  total_rows: number;
  suggested: ColumnMap | null;
  roles: ColumnRole[];
}

export interface InvoiceDoc {
  id: number;
  document_type: string;
  document_number: string | null;
  supplier: number | null;
  supplier_name: string | null;
  uploaded_at: string;
  processed: boolean;
  processed_at: string | null;
  movements_count: number;
  summary: Record<LineStatus, number> | null;
  extracted_data: {
    error?: string;
    code?: string | null;
    lines?: InvoiceLine[];
    processing_report?: ProcessingReport;
    detected_supplier?: string;
    engine?: ParseEngine;
    quality?: ParseQuality;
    columns?: ColumnMap | null;
  } | null;
  column_map: ColumnMap | null;
  ai: { enabled: boolean; status: "" | "queued" | "running" | "done" | "failed"; error: string; has_result: boolean };
}

export interface ScanCard {
  status: "found";
  variant_id: number;
  name: string;
  sku: string | null;
  barcode: string | null;
  cost_price: string | null;
  price: string | null;
  stock_total: string;
  reserved: string;
  available: string;
  stock_current: string | null;
  photo: string | null;
}

// ---------- импорт товаров ----------

export type RunStatus = "pending" | "running" | "preview" | "applying" | "done" | "failed";
export type RowAction = "create" | "update" | "error";

export interface ImportRowData {
  sku: string;
  barcode: string;
  name: string;
  variant: string;
  group: string;
  category: string;
  brand: string;
  price: string | null;
  old_price: string | null;
  cost: string | null;
  quantity: string | null;
  photos: string[];
  visible: boolean | null;
}

export interface ImportRow {
  row: number;
  action: RowAction;
  data: ImportRowData;
  errors: string[];
  warnings: string[];
  variant_id: number | null;
  result?: "create" | "update" | "failed";
}

export interface ImportRunStats {
  rows?: number;
  create?: number;
  update?: number;
  errors?: number;
  stock?: number;
  warnings?: number;
  columns?: Record<string, string>;
  result?: { created: number; updated: number; failed: number; stock: number };
  // синхронизация источника
  total?: number;
  new?: number;
  changed?: number;
  unchanged?: number;
  missing?: number;
  linked_auto?: number;
  price_changed?: number;
  hidden?: number;
  shown?: number;
  skipped?: number;
  duplicates?: number;
  format?: string;
}

export interface ImportRun {
  id: number;
  kind: "template" | "sync";
  status: RunStatus;
  source: number | null;
  source_name: string | null;
  file_name: string;
  options: { warehouse_id?: number | null; publish?: boolean };
  stats: ImportRunStats;
  error: string;
  created_by_email: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export type SourceKind = "feed" | "api" | "web";
export type AuthType = "none" | "basic" | "bearer" | "header" | "query" | "login";

export interface ImportSource {
  id: number;
  name: string;
  kind: SourceKind;
  url: string;
  has_file: boolean;
  file_name: string;
  format: "auto" | "yml" | "xml" | "csv" | "xlsx" | "json";
  auth_type: AuthType;
  auth_login: string;
  has_secret: boolean;
  adapter: string;
  field_map: Record<string, string>;
  options: Record<string, string | number>;
  currency: string;
  price_mode: "rrp" | "markup";
  markup_percent: string;
  price_rounding: string;
  category: number | null;
  category_name: string | null;
  supplier: number | null;
  supplier_name: string | null;
  publish_new: boolean;
  update_prices: boolean;
  hide_when_unavailable: boolean;
  sync_interval_minutes: number;
  is_active: boolean;
  last_sync_at: string | null;
  next_sync_at: string | null;
  last_status: "" | "running" | "ok" | "error";
  last_error: string;
  counts: { total: number; new: number; linked: number; ignored: number; missing: number } | null;
  created_at: string;
}

export interface SiteAdapterInfo {
  code: string;
  title: string;
  description: string;
  options: Record<string, string>;
}

export type SupplierItemStatus = "new" | "linked" | "ignored";

export interface SupplierItemRow {
  id: number;
  external_id: string;
  sku: string;
  barcode: string;
  name: string;
  brand: string;
  category_name: string;
  url: string;
  price: string | null;
  old_price: string | null;
  cost: string | null;
  currency: string;
  quantity: string | null;
  available: boolean | null;
  photo: string | null;
  params: Record<string, string>;
  status: SupplierItemStatus;
  variant: number | null;
  variant_name: string | null;
  variant_price: string | null;
  our_price: string | null;
  match_method: string;
  missing: boolean;
  changed_at: string;
}

export interface SupplierCategory {
  category_name: string;
  total: number;
  new: number;
}

// ---------- редактор товаров (кабинет) ----------

export interface ManageProductRow {
  id: number;
  name: string;
  slug: string | null;
  category: number | null;
  category_name: string | null;
  photo: string | null;
  variants_count: number;
  price_min: Money | null;
  stock: Money;
  visible: boolean;
  sku: string | null;
  modified: string;
}

export interface ManageVariant {
  id: number;
  variant_name: string | null;
  code: string | null;
  barcode: string | null;
  price: Money | null;
  original_price_value: Money | null;
  discount: number;
  cost_price: Money | null;
  available: boolean | null;
  brand: string | null;
  description: string | null;
  stock: Money;
  reserved: Money;
  available_stock: Money;
  dimensions_width: Money | null;
  dimensions_height: Money | null;
  dimensions_depth: Money | null;
  dimensions_weight: Money | null;
  photo: string | null;
}

export interface ManageProduct {
  id: number;
  name: string;
  slug: string | null;
  category: number | null;
  category_name: string | null;
  description: string | null;
  seller_name: string | null;
  photo: string | null;
  photos: { id: number; url: string | null; product_var: number | null }[];
  variants: ManageVariant[];
  created: string;
  modified: string;
}
