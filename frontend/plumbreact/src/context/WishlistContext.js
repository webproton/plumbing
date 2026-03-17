import React, { createContext, useContext, useEffect, useState } from "react";
import debounce from "lodash.debounce";
import ProductsService from "../services/ProductService";
import { AuthContext } from "./AuthContext";

export const WishlistContext = createContext({
  wishlist: [],
  toggleWishlist: () => {},
  clearWishlist: () => {},
});

export const WishlistProvider = ({ children }) => {
  const { user } = useContext(AuthContext);
  const [wishlist, setWishlist] = useState([]);
  const [pendingRequests, setPendingRequests] = useState(new Set()); // Отслеживание активных запросов
  const service = new ProductsService();

  const syncServerWishlist = async () => {
    try {
      const serverWishlist = await service.getWishlist();
      setWishlist(serverWishlist);
      localStorage.setItem("wishlist", JSON.stringify(serverWishlist));
      window.dispatchEvent(new Event("storage"));
    } catch (err) {
      console.error("Ошибка синхронизации wishlist:", err);
    }
  };

  const migrateLocalToServerWishlist = async () => {
    if (!user?.pk) return;

    try {
      const localWishlist = JSON.parse(localStorage.getItem("wishlist")) || [];
      if (localWishlist.length === 0) {
        await syncServerWishlist();
        return;
      }

      const serverWishlist = await service.getWishlist();
      const serverIds = new Set(serverWishlist.map(item => item.product_variant?.id));

      for (const item of localWishlist) {
        const id = item.product_variant?.id;
        if (id && !serverIds.has(id) && !pendingRequests.has(id)) {
          try {
            setPendingRequests(prev => new Set(prev).add(id));
            await service.addToWishlist(id);
          } catch (err) {
            console.warn(`Не удалось добавить variant ${id}:`, err.response?.data || err.message);
          } finally {
            setPendingRequests(prev => {
              const newSet = new Set(prev);
              newSet.delete(id);
              return newSet;
            });
          }
        }
      }

      await syncServerWishlist();
    } catch (err) {
      console.error("Ошибка миграции local → server:", err);
    }
  };

  useEffect(() => {
    if (user?.pk) {
      migrateLocalToServerWishlist();
    } else {
      const local = JSON.parse(localStorage.getItem("wishlist")) || [];
      setWishlist(local);
    }
  }, [user]);

  const toggleWishlist = debounce(async (variantOrId) => {
    try {
      const variant = typeof variantOrId === "object" ? variantOrId : null;
      const variantId = typeof variantOrId === "number" ? variantOrId : variant?.id;

      if (!variantId || pendingRequests.has(variantId)) return;

      setPendingRequests(prev => new Set(prev).add(variantId));

      try {
        if (user?.pk) {
          const serverWishlist = await service.getWishlist();
          const exists = serverWishlist.some(item => item.product_variant?.id === variantId);

          if (exists) {
            const item = serverWishlist.find(item => item.product_variant?.id === variantId);
            await service.removeFromWishlist(item.id);
          } else {
            await service.addToWishlist(variantId);
          }

          await syncServerWishlist();
        } else {
          const exists = wishlist.some(item => item.product_variant?.id === variantId);
          let updated;

          if (exists) {
            updated = wishlist.filter(item => item.product_variant?.id !== variantId);
          } else {
            if (!variant) return console.warn("Нет данных о варианте для localStorage");
            updated = [...wishlist, { product_variant: variant }];
          }

          setWishlist(updated);
          localStorage.setItem("wishlist", JSON.stringify(updated));
          window.dispatchEvent(new Event("storage"));
        }
      } finally {
        setPendingRequests(prev => {
          const newSet = new Set(prev);
          newSet.delete(variantId);
          return newSet;
        });
      }
    } catch (err) {
      console.error("Ошибка toggleWishlist:", err.response?.data || err.message);
    }
  }, 300);

  const clearWishlist = async () => {
    try {
      if (user?.pk) {
        await service.clearWishlist();
      }

      setWishlist([]);
      localStorage.setItem("wishlist", JSON.stringify([]));
      window.dispatchEvent(new Event("storage"));
    } catch (err) {
      console.error("Ошибка clearWishlist:", err);
    }
  };

  return (
    <WishlistContext.Provider value={{ wishlist, toggleWishlist, clearWishlist }}>
      {children}
    </WishlistContext.Provider>
  );
};

export const useWishlist = () => useContext(WishlistContext);