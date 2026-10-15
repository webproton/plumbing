// services/ProfileService.js
import axiosInstance from "./axiosInstance";

const PROFILE_ENDPOINT = "/api/dj-rest-auth/profile/";

const ProfileService = {
  // Получить профиль текущего пользователя
  getProfile: async () => {
    try {
      const response = await axiosInstance.get(PROFILE_ENDPOINT);
      return response.data;
    } catch (error) {
      console.error("Ошибка получения профиля:", error);
      throw error;
    }
  },

  // Обновить профиль
  updateProfile: async (data) => {
    try {
      const response = await axiosInstance.put(PROFILE_ENDPOINT, data);
      return response.data;
    } catch (error) {
      console.error("Ошибка обновления профиля:", error);
      throw error;
    }
  },
  
  // Сменить пароль
  changePassword: async (newPassword1, newPassword2) => {
    try {
      const response = await axiosInstance.post("/api/dj-rest-auth/password/change/", {
        new_password1: newPassword1,
        new_password2: newPassword2,
      });
      return response.data;
    } catch (error) {
      console.error("Ошибка смены пароля:", error);
      throw error;
    }
  },
};




export default ProfileService;
