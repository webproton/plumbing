import React, { useState } from "react";
import ProfileService from "../services/ProfileService";

const PasswordChangeForm = () => {
  const [newPassword1, setNewPassword1] = useState("");
  const [newPassword2, setNewPassword2] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await ProfileService.changePassword(newPassword1, newPassword2);
      setMessage("Пароль успешно изменён");
      setNewPassword1("");
      setNewPassword2("");
    } catch (err) {
      setMessage("Ошибка при смене пароля");
    }
  };

  return (
    <form className="subform" onSubmit={handleSubmit}>
      <h3>Сменить пароль</h3>
      <input
        type="password"
        placeholder="Новый пароль"
        value={newPassword1}
        onChange={(e) => setNewPassword1(e.target.value)}
      />
      <input
        type="password"
        placeholder="Повторите новый пароль"
        value={newPassword2}
        onChange={(e) => setNewPassword2(e.target.value)}
      />
      <button type="submit">Сменить</button>
      <p>{message}</p>
    </form>
  );
};

export default PasswordChangeForm;
