// src/api/axiosInstance.js
import axios from "axios";
import { getCookie } from "../utils/csrf";

// const BASE_URL = "http://localhost:8000"; // Или импортируй из .env файла
// const BASE_URL = process.env.REACT_APP_API_URL; // Или импортируй из .env файла
const BASE_URL = process.env.REACT_APP_API_URL ||  "http://192.168.68.109:8000";
// const BASE_URL = process.env.REACT_APP_API_URL


const axiosInstance = axios.create({
  // baseURL: BASE_URL  || "http://localhost/",
  baseURL: BASE_URL,
  withCredentials: true, // для работы с куками, если используешь dj-rest-auth + cookie
});


axiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    const csrfToken = getCookie("csrftoken");
    if (csrfToken) {
      config.headers["X-CSRFToken"] = csrfToken;
    }

    // --------------------------
    // Добавляем device_id и session_id для антифрод
    // --------------------------
    const deviceId = localStorage.getItem("device_id");
    const sessionId = sessionStorage.getItem("session_id");
    if (deviceId) config.headers["X-Device-Id"] = deviceId;
    if (sessionId) config.headers["X-Session-Id"] = sessionId;

    return config;
  },
  (error) => Promise.reject(error)
);


axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refresh = localStorage.getItem("refresh");
      if (refresh) {
        try {
          const res = await axios.post(`${BASE_URL}/dj-rest-auth/token/refresh/`, { refresh });

          // const res = await axios.post("http://localhost:8000/dj-rest-auth/token/refresh/", { refresh });
          localStorage.setItem("access", res.data.access);
          originalRequest.headers.Authorization = `Bearer ${res.data.access}`;
          return axiosInstance(originalRequest);
        } catch (err) {
          console.error("Refresh failed:", err);
          localStorage.removeItem("access");
          localStorage.removeItem("refresh");
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export default axiosInstance;