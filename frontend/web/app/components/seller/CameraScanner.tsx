import { Camera, CameraOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useT } from "~/i18n/react";

import { Button } from "../ui";

// BarcodeDetector есть в Chrome/Android и Safari 17+; в lib.dom его пока нет — описываем нужное
interface Detector {
  detect(source: CanvasImageSource): Promise<{ rawValue: string }[]>;
}
declare global {
  interface Window {
    BarcodeDetector?: new (opts?: { formats?: string[] }) => Detector;
  }
}

const FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "qr_code"];
const SAME_CODE_PAUSE_MS = 2000;

/** Сканирование камерой телефона. Код отдаётся в onScan; повтор того же кода игнорируется 2 секунды. */
export function CameraScanner({ onScan }: { onScan: (code: string) => void }) {
  const t = useT();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const supported = typeof window !== "undefined" && "BarcodeDetector" in window;
  const onScanRef = useRef(onScan);
  useEffect(() => {
    onScanRef.current = onScan; // актуальный обработчик без перезапуска камеры
  });

  useEffect(() => {
    if (!active) return;
    let stopped = false;
    let stream: MediaStream | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let last = { code: "", at: 0 };

    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        if (stopped || !videoRef.current) return;
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        const detector = new window.BarcodeDetector!({ formats: FORMATS });
        const tick = async () => {
          if (stopped || !videoRef.current) return;
          try {
            const [found] = await detector.detect(videoRef.current);
            if (found && (found.rawValue !== last.code || Date.now() - last.at > SAME_CODE_PAUSE_MS)) {
              last = { code: found.rawValue, at: Date.now() };
              navigator.vibrate?.(60);
              onScanRef.current(found.rawValue);
            }
          } catch {
            /* кадр не готов — пробуем дальше */
          }
          timer = setTimeout(tick, 250);
        };
        tick();
      } catch {
        setError(t("wh.scan.cameraDenied"));
        setActive(false);
      }
    })();

    return () => {
      stopped = true;
      clearTimeout(timer);
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [active]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!supported) return <p className="text-sm text-muted">{t("wh.scan.cameraUnsupported")}</p>;

  return (
    <div className="space-y-2">
      <Button type="button" variant={active ? "danger" : "secondary"} onClick={() => (setError(null), setActive((a) => !a))}>
        {active ? <CameraOff className="size-4" aria-hidden /> : <Camera className="size-4" aria-hidden />}
        {active ? t("wh.scan.cameraOff") : t("wh.scan.cameraOn")}
      </Button>
      {error && <p className="text-sm text-danger">{error}</p>}
      {active && <video ref={videoRef} playsInline muted className="aspect-video w-full max-w-md rounded-2xl bg-black object-cover" />}
    </div>
  );
}
