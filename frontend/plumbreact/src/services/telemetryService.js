// // src/api/telemetryService.js
// import axiosInstance from "./axiosInstance";
// // import { collectTelemetryData } from "../utils/collectTelemetryData";

// export async function sendTelemetry(deviceId, sessionId, telemetryData) {
//   try {
//     // const telemetryData = await collectTelemetryData();

//     await axiosInstance.post("/api/telemetry/collect/", {
//       device_id: deviceId,
//       session_id: sessionId,
//       ...telemetryData,
//     });
//   } catch (error) {
//     console.error("try error:", error);
//   }
// }
