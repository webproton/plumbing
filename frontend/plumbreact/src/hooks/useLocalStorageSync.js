import { useEffect, useContext } from "react";
import { AuthContext } from "./AuthProvider";

export function useLocalStorageSync(key, callback, fetchServerData = null) {
  const { user } = useContext(AuthContext);

  useEffect(() => {
    const handleStorage = async (event) => {
      if (event.key && event.key !== key) return;
      if (user && fetchServerData) {
        try {
          const serverData = await fetchServerData();
          callback(serverData);
          localStorage.setItem(key, JSON.stringify(serverData));
        } catch (error) {
          console.error(`Error fetching ${key} from server:`, error);
          const localData = JSON.parse(localStorage.getItem(key)) || [];
          callback(localData);
        }
      } else {
        const localData = JSON.parse(localStorage.getItem(key)) || [];
        callback(localData);
      }
    };

    window.addEventListener("storage", handleStorage);
    handleStorage({ key });

    return () => window.removeEventListener("storage", handleStorage);
  }, [key, callback, user, fetchServerData]);
}