import React from "react";
import { FaPhone, FaEnvelope, FaTelegramPlane } from "react-icons/fa";
import styles from "../css/Contacts.module.css";

const Contacts = () => {
  return (
    <div className={styles.contactsPage}>
      <h2>Контакты</h2>
      <p>
        Свяжитесь с нами удобным для вас способом. Мы всегда готовы ответить на ваши вопросы и помочь с заказом.
      </p>

      <div className={styles.infoBlocks}>
        <div className={styles.infoBlock}>
          <h4>
            <FaPhone aria-hidden="true" /> Телефон
          </h4>
          <p>
            <FaPhone aria-hidden="true" />
            <a href="tel:+38050505">+38 (050) 123-45-67</a>
          </p>
        </div>

        <div className={styles.infoBlock}>
          <h4>
            <FaEnvelope aria-hidden="true" /> Email
          </h4>
          <p>
            <FaEnvelope aria-hidden="true" />
            <a href="mailto:info@company.com">info@company.com</a>
          </p>
        </div>

        <div className={styles.infoBlock}>
          <h4>
            <FaTelegramPlane aria-hidden="true" /> Telegram
          </h4>
          <p>
            <FaTelegramPlane aria-hidden="true" />
            <a href="https://t.me/username" target="_blank" rel="noopener noreferrer">@username</a>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Contacts;