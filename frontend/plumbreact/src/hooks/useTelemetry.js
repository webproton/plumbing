


// src/hooks/useTelemetry.js
import { useEffect } from "react";
import { UAParser } from "ua-parser-js";
import FingerprintJS from "@fingerprintjs/fingerprintjs";
import { generateUUID } from "../utils/uuid";
import { sendTelemetry } from "../services/telemetryService";

export function useTelemetry() {
  useEffect(() => {
    async function collectAndSend() {
      // 1️⃣ Идентификаторы
      const deviceId =
        localStorage.getItem("device_id") ||
        (crypto.randomUUID?.() || generateUUID());
      localStorage.setItem("device_id", deviceId);

      const sessionId =
        sessionStorage.getItem("session_id") ||
        (crypto.randomUUID?.() || generateUUID());
      sessionStorage.setItem("session_id", sessionId);

      // 2️⃣ Парсинг UserAgent
      const parser = new UAParser();
      const uaResult = parser.getResult();

      let deviceType = uaResult.device.type || "desktop";
      let deviceModel = uaResult.device.model || null;
      let deviceVendor = uaResult.device.vendor || null;

      // 2a. Современный API userAgentData
      if (navigator.userAgentData) {
        try {
          const uaData = await navigator.userAgentData.getHighEntropyValues([
            "platform",
            "model",
            "brands",
          ]);
          if (uaData.model) {
            deviceModel = uaData.model;
            deviceType = deviceType === "desktop" ? "mobile" : deviceType;
          }
          if (uaData.brands?.length) {
            deviceVendor = uaData.brands[0].brand;
          }
        } catch (e) {
          console.warn("userAgentData error", e);
        }
      }

      // 2b. Фallback для iOS
      if (/iPhone/i.test(navigator.userAgent)) {
        deviceVendor = "Apple";
        deviceModel = deviceModel || "iPhone";
        deviceType = "mobile";
      } else if (/iPad/i.test(navigator.userAgent)) {
        deviceVendor = "Apple";
        deviceModel = deviceModel || "iPad";
        deviceType = "tablet";
      } else if (/Android/i.test(navigator.userAgent)) {
        deviceType = "mobile";

        // Если модель пустая, пробуем вытащить из UA
        if (!deviceModel) {
          const match = navigator.userAgent.match(/Android.*;\s([^)]+)\)/i);
          if (match && match[1]) {
            const rawModel = match[1].trim();
            deviceModel = rawModel.length > 2 ? rawModel : "Unknown Android Device";
          }
        }

        // Производитель
        if (!deviceVendor && deviceModel) {
          deviceVendor = deviceModel.split(" ")[0];
        }
      }

      // Safety net: если всё равно пусто
      if (!deviceModel || deviceModel.length < 2) deviceModel = "Unknown Device";
      if (!deviceVendor || deviceVendor.length < 2) deviceVendor = "Unknown Vendor";

      // 3️⃣ FingerprintJS
      let canvas_hash = null;
      try {
        const fp = await FingerprintJS.load();
        const result = await fp.get();
        canvas_hash = result.visitorId;
      } catch (e) {
        console.warn("FingerprintJS error", e);
      }

      // 4️⃣ Собираем все данные телеметрии
      const telemetryData = {
        device_id: deviceId,
        session_id: sessionId,
        browser: uaResult.browser.name,
        browser_version: uaResult.browser.version,
        os: uaResult.os.name,
        os_version: uaResult.os.version,
        device_type: deviceType,
        device_model: deviceModel,
        device_vendor: deviceVendor,
        screen_width: window.screen.width,
        screen_height: window.screen.height,
        device_pixel_ratio: window.devicePixelRatio,
        color_depth: window.screen.colorDepth,
        lang: navigator.language,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        connection_type: navigator.connection?.type || null,
        connection_rtt: navigator.connection?.rtt || null,
        connection_downlink: navigator.connection?.downlink || null,
        cpu_cores: navigator.hardwareConcurrency,
        ram_gb: navigator.deviceMemory || null,
        touch_support: "ontouchstart" in window,
        canvas_hash,
      };

      // 5️⃣ Отправка на бэкенд
      try {
        await sendTelemetry(deviceId, sessionId, telemetryData);
      } catch (e) {
        console.warn("Telemetry send error", e);
      }
    }

    collectAndSend();
  }, []);
}

