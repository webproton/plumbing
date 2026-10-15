import React, { useState } from "react";
import axiosInstance from "../services/axiosInstance";


export default function ResetPassword() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await axiosInstance.post("/api/dj-rest-auth/password/reset/", { email });
      setMessage("Письмо для сброса пароля отправлено!");
    } catch (error) {
      setMessage("Ошибка при сбросе пароля.");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="auth-container">
      <h2>Сброс пароля</h2>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Введите email"
        required
      />
      <button type="submit">Сбросить пароль</button>
      {message && <p style={{ marginTop: "1rem", color: "#ff0000" }}>{message}</p>}
    </form>
  );
}
