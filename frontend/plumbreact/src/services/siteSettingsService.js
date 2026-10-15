// src/api/siteSettingsService.js
import axiosInstance from "./axiosInstance";

export async function getSiteSettings() {
  try {
    const response = await axiosInstance.get("/api/callback/site-settings/");
    return response.data;
  } catch (error) {
    console.error("Ошибка при получении настроек сайта:", error);
    throw error;
  }
}
