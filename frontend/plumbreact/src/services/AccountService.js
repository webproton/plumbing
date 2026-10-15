// src/services/AccountService.js
import axiosInstance from "./axiosInstance";

const USER_ENDPOINT = "/api/dj-rest-auth/user/";
const USER_ORDERS_ENDPOINT = "/api/orders/history/";

const AccountService = {
  // Получить текущего пользователя
  getCurrentUser: async () => {
    try {
      const response = await axiosInstance.get(USER_ENDPOINT);
      return response.data;
    } catch (error) {
      console.error("Ошибка получения пользователя:", error);
      throw error;
    }
  },


  // Получить историю заказов текущего пользователя
  getUserOrders: async () => {
    try {
      const response = await axiosInstance.get(USER_ORDERS_ENDPOINT);
      return response.data;
    } catch (error) {
      console.error("Ошибка получения истории заказов:", error);
      throw error;
    }
  },

  // Получить детали одного заказа
  getOrderDetails: async (orderId) => {
    try {
      const response = await axiosInstance.get(`${USER_ORDERS_ENDPOINT}${orderId}/`);
      return response.data;
    } catch (error) {
      console.error("Ошибка загрузки деталей заказа:", error);
      throw error;
    }
  },


  // Отмена заказа
  cancelOrder: async (orderId) => {
    try {
      const response = await axiosInstance.post(`${USER_ORDERS_ENDPOINT}${orderId}/cancel/`);
      return response.data;
    } catch (error) {
      console.error("Ошибка отмены заказа:", error);
      throw error;
    }
  },



};



export default AccountService;
