import React, { useEffect, useState } from "react";
import axiosInstance from "../services/axiosInstance";
import { useParams, useHistory } from "react-router-dom";

export default function EmailConfirm() {
  const { key } = useParams();
  const [message, setMessage] = useState("Подтверждение...");
  const history = useHistory();

  useEffect(() => {
    const confirmEmail = async () => {
      try {
        await axiosInstance.post("/api/dj-rest-auth/registration/verify-email/", { key });
        setMessage("Email успешно подтвержден!");
        setTimeout(() => history.push("/login"), 3000);
      } catch (error) {
        setMessage("Ошибка подтверждения.");
      }
    };

    confirmEmail();
  }, [key]);

  return (
    <div className="auth-container">
      <h2>{message}</h2>
    </div>
  );
}
