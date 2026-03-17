// src/components/CallbackButton.jsx
import { useState } from "react";
import CallbackForm from "../pages/CallbackForm"


export default function CallbackButton() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Плавающая кнопка */}
      <button 
        className="callback-btn" 
        onClick={() => setIsOpen(true)}
      >
        Заказать звонок
      </button>

      {/* Модальное окно */}
      {isOpen && (
        <div className="callback-modal">
          <div className="callback-modal-content">
            <button 
              className="callback-close" 
              onClick={() => setIsOpen(false)}
            >
              ✕
            </button>
            <h3>Заказать звонок</h3>
            <CallbackForm />
          </div>
        </div>
      )}
    </>
  );
}
