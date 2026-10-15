// src/api/callbackService.js
import { getCookie } from "../utils/csrf";
import axiosInstance from "./axiosInstance";

// Отправка заявки на callback
export async function sendCallbackRequest({ phone, email, telegram }) {
  try {
    const response = await axiosInstance.post("/api/callback/request/", {
      phone,
      email,
      telegram,
    });

    return response.data;
  } catch (err) {
    console.error("Ошибка при отправке callback:", err);
    throw err;
  }
}

// export async function sendCallbackRequest({ phone, email, telegram }) {
//   try {
//     const response = await fetch("/api/callback/request/", {
//       method: "POST",
//       headers: {
//         "Content-Type": "application/json",
//         "X-CSRFToken": getCookie("csrftoken"),
//       },
//       body: JSON.stringify({ phone, email, telegram }),
//     });

//     if (!response.ok) {
//       throw new Error(`Ошибка запроса: ${response.status}`);
//     }

//     return await response.json();
//   } catch (err) {
//     console.error("Ошибка при отправке callback:", err);
//     throw err;
//   }
// }
