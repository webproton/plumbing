import { type RouteConfig, index, layout, prefix, route } from "@react-router/dev/routes";

export default [
  // для поисковиков — только в корне сайта
  route("robots.txt", "routes/seo/robots.ts"),
  route("sitemap.xml", "routes/seo/sitemap.ts"),

  // все страницы доступны без префикса (українська) и с /ru (русский)
  route(":lang?", "routes/lang-layout.tsx", [
    index("routes/home.tsx"),
    route("catalog", "routes/catalog.tsx"),
    route("product/:slug", "routes/product.tsx"),
    route("cart", "routes/cart.tsx"),
    route("checkout", "routes/checkout.tsx"),
    route("order/:id/success", "routes/order-success.tsx"),
    route("wishlist", "routes/wishlist.tsx"),

    route("login", "routes/auth/login.tsx"),
    route("register", "routes/auth/register.tsx"),
    route("logout", "routes/auth/logout.tsx"),
    route("confirm-email/:key", "routes/auth/confirm-email.tsx"),
    route("reset-password", "routes/auth/reset-password.tsx"),
    route("reset-password/confirm", "routes/auth/reset-password-confirm.tsx"),

    ...prefix("account", [
      layout("routes/account/layout.tsx", [
        index("routes/account/profile.tsx"),
        route("orders", "routes/account/orders.tsx"),
        route("orders/:id", "routes/account/order.tsx"),
        route("orders/:id/invoice", "routes/account/order-invoice.tsx"),
      ]),
    ]),

    ...prefix("seller", [
      layout("routes/seller/layout.tsx", [
        index("routes/seller/index.tsx"),
        route("products", "routes/seller/products.tsx"),
        route("products/new", "routes/seller/product-new.tsx"),
        route("products/:id", "routes/seller/product-edit.tsx"),
        route("labels", "routes/seller/labels.tsx"),
        route("settings", "routes/seller/settings.tsx"),
        route("orders", "routes/seller/orders.tsx"),
        route("orders/:id", "routes/seller/order.tsx"),
        route("orders/:id/invoice", "routes/seller/order-invoice.tsx"),
        route("stock", "routes/seller/stock.tsx"),
        route("movements", "routes/seller/movements.tsx"),
        route("operations", "routes/seller/operations.tsx"),
        route("scanner", "routes/seller/scanner.tsx"),
        route("warehouses", "routes/seller/warehouses.tsx"),
        route("suppliers", "routes/seller/suppliers.tsx"),
        route("prices", "routes/seller/prices.tsx"),
        route("help", "routes/seller/help.tsx"),
        route("documents", "routes/seller/documents.tsx"),
        route("documents/:id", "routes/seller/document.tsx"),
        route("documents/:id/file", "routes/seller/document-file.tsx"),
        route("documents/:id/columns", "routes/seller/document-columns.tsx"),
        route("variants", "routes/seller/variants.tsx"),
        route("import", "routes/seller/import.tsx"),
        route("import/template", "routes/seller/import-template.tsx"),
        route("import/:id", "routes/seller/import-run.tsx"),
        route("sources", "routes/seller/sources.tsx"),
        route("sources/new", "routes/seller/source-edit.tsx", { id: "seller-source-new" }),
        route("sources/:id", "routes/seller/source.tsx"),
        route("sources/:id/edit", "routes/seller/source-edit.tsx", { id: "seller-source-edit" }),
      ]),
    ]),

    route("delivery", "routes/pages/delivery.tsx"),
    route("contacts", "routes/pages/contacts.tsx"),
    route("callback", "routes/callback.tsx"),
    route("np/cities", "routes/np/cities.tsx"),
    route("np/warehouses", "routes/np/warehouses.tsx"),
    route("np/estimate", "routes/np/estimate.tsx"),

    // старые адреса SPA → новые (сохраняем ссылки и SEO)
    route("products", "routes/legacy/products.tsx"),
    route("products/:slug", "routes/legacy/product.tsx", { id: "legacy-product" }),
    route("products/:slug/variant/:variant", "routes/legacy/product.tsx", { id: "legacy-product-variant" }),
    route("category", "routes/legacy/category.tsx"),

    route("*", "routes/not-found.tsx"),
  ]),
] satisfies RouteConfig;
