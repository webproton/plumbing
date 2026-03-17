import axiosInstance from "./axiosInstance";


 
const API_URL = "/api/orders"; // URL вашего сервера

// Сервис для работы с корзиной
const CartService = {
  // Получение корзины это был рабочий вариат
  // getCart: async (cartUUID) => {
  //   return axiosInstance.get(`${API_URL}/cart/by-uuid/`, {
  //     params: { cart_uuid: cartUUID }, // Передаем cart_uuid как параметр
  //   });
  // },

    getCart: async () => {
    // cart_uuid теперь берется из cookie, не передаем в params
    return axiosInstance.get(`${API_URL}/cart/by-cookie/`);
  },
  


  createOrder: async (orderData) => {
    return axiosInstance.post(`${API_URL}/order-create/`, {
      customer_name: orderData.customer_name, // Имя клиента
      email: orderData.email, // Электронная почта
      phone_number: orderData.phone_number, // Телефон
      address: orderData.address, // Адрес
      city: orderData.city, // Город
      cart_uuid: orderData.cart_uuid, 
      // cart: orderData.cart,// UUID корзины
      delivery_type: orderData.delivery_type, // Тип доставки
      // Прочие поля, если они есть:
      department_number: orderData.department_number,
      comment: orderData.comment,
      telegram: orderData.telegram,   // <- добавлено
    whatsapp: orderData.whatsapp,   // <- добавлено
    });
  },
  

  createCart: async (cart_items, cart_uuid) => {
    try {
      const payload = {
        cart_items: cart_items, // Список товаров
      };
  
      // Если `cart_uuid` передан, добавляем его в тело запроса
      if (cart_uuid) {
        payload.cart_uuid = cart_uuid;
      }
  
      const response = await axiosInstance.post(`${API_URL}/cart/`, payload);
  
      if (response.data.cart_uuid) {
        localStorage.setItem("cart_uuid", response.data.cart_uuid); // Сохраняем cart_uuid
      }
  
      return response.data; // Возвращаем ответ с данными о корзине
    } catch (error) {
      console.error("Error creating cart:", error);
      throw error;
    }
  },
  

  // Удаление корзины
  deleteCart: async (cartId) => {
    return axiosInstance.delete(`${API_URL}/cart/${cartId}`);
  },
};

export default CartService;
