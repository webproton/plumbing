// src/pages/Login.js
import React, { useState, useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import { useHistory, Link } from "react-router-dom";

export default function Login() {
  const { login } = useContext(AuthContext);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const history = useHistory();

  const handleSubmit = async (e) => {
        // console.log("LOGIN URL:", `${process.env.REACT_APP_API_URL}`);

    // console.log("LOGIN URL:", `${process.env.REACT_APP_API_URL}/dj-rest-auth/login/`);
    e.preventDefault();
    try {
      await login(email, password);

      // localStorage.removeItem("wishlist");
      // window.dispatchEvent(new Event("storage")); // чтобы компоненты обновились
      history.push("/account/");
    } catch (err) {
      alert("Ошибка входа");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="auth-container">
      <h2>Вход</h2>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        required
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Пароль"
        required
      />
      <button type="submit">Войти</button>
      <Link to="/reset-password" className="link">
        Забыли пароль?
      </Link>
    </form>
  );
}