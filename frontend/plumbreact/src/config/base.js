const base = {
  environment: '',
  apiUrl: '/api', // базовый путь к API
  tokenPrefix: 'Token',
  localStorageTokenKey: 'token',
  urls: {
    auth: '/dj-rest-auth/',
    registration: '/dj-rest-auth/registration/',
    products: '/products/',
    categories: '/category/',
    newProducts: '/new_products/',
    wishlist: '/wishlist/',
    ordersHistory: '/orders/history/',
    cart: '/orders/cart/',
    createOrder: '/orders/order-create/',
    callbackRequest: '/callback/request/',
    callbackSettings: '/callback/site-settings/',
  },
};

export default base;
