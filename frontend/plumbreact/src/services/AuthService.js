// src/services/AuthService.js
import axiosInstance from "./axiosInstance";

const AuthService = {

login: async (email, password) => {
    try {
      const res = await axiosInstance.post("/api/dj-rest-auth/login/", {
        email,
        password,
      })
      const { access_token, refresh_token } = res.data; // Исправлено: access_token, refresh_token
      if (access_token && refresh_token) {
        localStorage.setItem("access", access_token);
        localStorage.setItem("refresh", refresh_token);
      } else {
        console.error("No access_token/refresh_token in response:", res.data);
      }
      return res.data;
    } catch (error) {
      console.error("Login error:", error.response?.data, error.response?.status);
      throw error;
    }
  },

register: async ({ email, password1, password2 }) => {
    try {
      const res = await axiosInstance.post("/api/dj-rest-auth/registration/", {
        email,
        password1,
        password2,
      });
      const { access_token, refresh_token } = res.data; // Исправлено
      if (access_token && refresh_token) {
        localStorage.setItem("access", access_token);
        localStorage.setItem("refresh", refresh_token);
      } else {
        console.error("No access_token/refresh_token in response:", res.data);
      }
      return res.data;
    } catch (error) {
      console.error("Register error:", error.response?.data, error.response?.status);
      throw error;
    }
  },
  logout: async () => {
    const res = await axiosInstance.post("/api/dj-rest-auth/logout/");
    return res.data;
  },

  getCurrentUser: async () => {
    const res = await axiosInstance.get("/api/dj-rest-auth/user/");
    // localStorage.removeItem("access"); // Очищаем токен
    // localStorage.removeItem("refresh");
    return res.data;
  },
};

export default AuthService;
