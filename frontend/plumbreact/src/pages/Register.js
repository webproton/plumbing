import React, { useState, useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import { useHistory } from "react-router-dom";

export default function Register() {
  const { register } = useContext(AuthContext);
  const [form, setForm] = useState({ email: "", password1: "", password2: "" });
  const [message, setMessage] = useState(""); // новое состояние для уведомлений
  const history = useHistory();

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

const handleSubmit = async (e) => {
  e.preventDefault();
  try {
    await register(form);
    setMessage(
      "Регистрация прошла успешно! Пожалуйста, проверьте вашу почту для подтверждения регистрации."
    );
    setForm({ email: "", password1: "", password2: "" });

    // Через 3 секунды редирект на главную
    setTimeout(() => {
      history.push("/");
    }, 3000);
  } catch (err) {
    setMessage("Ошибка регистрации. Попробуйте снова.");
  }
};


  return (
    <div className="auth-container">
      <form onSubmit={handleSubmit}>
        <h2>Регистрация</h2>
        <input
          name="email"
          type="email"
          placeholder="Email"
          value={form.email}
          onChange={handleChange}
          required
        />
        <input
          name="password1"
          type="password"
          placeholder="Пароль"
          value={form.password1}
          onChange={handleChange}
          required
        />
        <input
          name="password2"
          type="password"
          placeholder="Повтор пароля"
          value={form.password2}
          onChange={handleChange}
          required
        />
        <button type="submit">Зарегистрироваться</button>
      </form>

      {message && (
        <div className="success-message" style={{ marginTop: "15px", color: "green" }}>
          {message}
        </div>
      )}
    </div>
  );
}

