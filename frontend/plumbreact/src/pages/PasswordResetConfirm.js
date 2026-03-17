import React, { useState } from "react";
import { useHistory, useLocation } from "react-router-dom";
import axiosInstance from "../services/axiosInstance";


export default function PasswordResetConfirm() {
  const [newPassword1, setNewPassword1] = useState("");
  const [newPassword2, setNewPassword2] = useState("");
  const [message, setMessage] = useState("");
  const history = useHistory();
  const location = useLocation();

  // Извлекаем параметры ?uid=...&token=...
  const searchParams = new URLSearchParams(location.search);
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await axiosInstance.post("/dj-rest-auth/password/reset/confirm/", {
        uid,
        token,
        new_password1: newPassword1,
        new_password2: newPassword2,
      });
      setMessage("Пароль успешно сброшен!");
      setTimeout(() => history.push("/login"), 3000);
    } catch (err) {
      setMessage("Ошибка сброса пароля");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="auth-container">
      <h2>Установка нового пароля</h2>
      <input
        type="password"
        placeholder="Новый пароль"
        value={newPassword1}
        onChange={(e) => setNewPassword1(e.target.value)}
        required
      />
      <input
        type="password"
        placeholder="Повторите новый пароль"
        value={newPassword2}
        onChange={(e) => setNewPassword2(e.target.value)}
        required
      />
      <button type="submit">Сменить пароль</button>
      {message && <p style={{ marginTop: "1rem", color: "#ff0000" }}>{message}</p>}
    </form>
  );
}
