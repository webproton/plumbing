import React, { createContext, useState, useEffect } from "react";
import AuthService from "../services/AuthService";
import ProductsService from "../services/ProductService";
import * as CompareService from "../utils/compare";

const productService = new ProductsService();

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);

  const fetchUser = async () => {
    const token = localStorage.getItem("access");
    if (!token) {
      setUser(null);
      return;
    }

    try {
      const data = await AuthService.getCurrentUser();
      setUser(data || null);
    } catch (error) {
      console.error("fetchUser error:", error.response?.data || error.message);
      setUser(null);
    }
  };

  const fetchUserData = async () => {
    if (!user?.pk) return;

    try {
      // 1. Получаем серверные данные
      let serverWishlist = await productService.getWishlist();
      const serverCompare = await CompareService.getCompareList();
      // const serverCart = await CartService.getCart();

      // 2. Миграция localStorage → сервер (wishlist)
      const localWishlist = JSON.parse(localStorage.getItem("wishlist")) || [];
      const serverIds = new Set(serverWishlist.map(item => item.product_variant?.id));

      for (const item of localWishlist) {
        const variantId = item.product_variant?.id;
        if (variantId && !serverIds.has(variantId)) {
          await productService.addToWishlist(variantId);
        }
      }

      // 3. Повторно получаем wishlist после миграции
      serverWishlist = await productService.getWishlist();

      // 4. Сохраняем всё в localStorage
      // localStorage.setItem("cart", JSON.stringify(serverCart));
      localStorage.setItem("wishlist", JSON.stringify(serverWishlist));
      localStorage.setItem("compare", JSON.stringify(serverCompare));

      // 5. Уведомляем всех подписчиков
      window.dispatchEvent(new CustomEvent("localStorageUpdated", { detail: { key: "all" } }));
    } catch (err) {
      console.error("fetchUserData error:", err.response?.data || err.message);
    }
  };

  useEffect(() => {
    fetchUser();
  }, []);

  useEffect(() => {
    if (user?.pk) {
      fetchUserData();
    }
  }, [user]);

  const login = async (email, password) => {
    try {
      await AuthService.login(email, password);
      await fetchUser();
      await fetchUserData();
    } catch (err) {
      console.error("Login error:", err.response?.data || err.message);
      throw err;
    }
  };

  const register = async (data) => {
    try {
      await AuthService.register(data);
      await fetchUser();
      await fetchUserData();
    } catch (err) {
      console.error("Register error:", err.response?.data || err.message);
      throw err;
    }
  };

  const logout = async () => {
    try {
      await AuthService.logout();
      setUser(null);

      // Очищаем localStorage
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      localStorage.removeItem("cart");
      localStorage.removeItem("wishlist");
      localStorage.removeItem("compare");

      // Чистим куки
      document.cookie.split(";").forEach((c) => {
        document.cookie = c
          .replace(/^ +/, "")
          .replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
      });

      window.dispatchEvent(new CustomEvent("localStorageUpdated", { detail: { key: "logout" } }));
    } catch (err) {
      console.error("Logout error:", err.response?.data || err.message);
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
