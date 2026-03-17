import { useState } from "react";
import { FaPhoneAlt, FaEnvelope, FaTelegramPlane } from "react-icons/fa"; // иконки
import { sendCallbackRequest } from "../services/callbackService";

export default function CallbackForm() {
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [telegram, setTelegram] = useState("");



  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!phone.trim()) {
      alert("Пожалуйста, укажите номер телефона!");
      return;
    }

    try {
      const result = await sendCallbackRequest({ phone, email, telegram });
      alert("Ваша заявка успешно отправлена!");
      // console.log(result);
      setPhone("");
      setEmail("");
      setTelegram("");
    } catch (err) {
      alert("Ошибка при отправке заявки, попробуйте позже.");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="callback-form">
      <div className="callback-input">
        <FaPhoneAlt className="input-icon" />
        <input
          type="text"
          placeholder="Телефон *"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          required
        />
      </div>

      <div className="callback-input">
        <FaEnvelope className="input-icon" />
        <input
          type="email"
          placeholder="Email (необязательно)"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>

      <div className="callback-input">
        <FaTelegramPlane className="input-icon" />
        <input
          type="text"
          placeholder="Telegram (необязательно)"
          value={telegram}
          onChange={(e) => setTelegram(e.target.value)}
        />
      </div>

      <button type="submit" className="callback-submit">
        Заказать звонок
      </button>
    </form>
  );
}
