import React, { useState } from "react";
import axiosInstance from "../services/axiosInstance";

const EmailChangeForm = () => {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await axiosInstance.post("/api/dj-rest-auth/email/", { email });
      setMessage("Письмо с подтверждением отправлено");
    } catch (err) {
      setMessage("Ошибка при отправке email");
    }
  };

  return (
    <form className="subform" onSubmit={handleSubmit}>
      <h3>Сменить email</h3>
      <input
        type="email"
        placeholder="Новый email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <button type="submit">Сменить email</button>
      <p>{message}</p>
    </form>
  );
};

export default EmailChangeForm;
