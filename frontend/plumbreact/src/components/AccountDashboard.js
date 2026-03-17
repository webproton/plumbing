import React, { useEffect, useState } from "react";
import { Link, Route, Switch, useRouteMatch, NavLink } from "react-router-dom";
import AccountService from "../services/AccountService";
import AuthService from "../services/AuthService";

import OrderHistory from "./OrderHistory";
import Wishlist from "./Wishlist";
import Cart from "./Cart";
import Profile from "./Profile";
import Navigation from "./Navigation";

const AccountDashboard = () => {
  const { path, url } = useRouteMatch();
  const [user, setUser] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isProfileOpen, setProfileOpen] = useState(false);
  const [isCartOpen, setCartOpen] = useState(false);
  const [isSidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const currentUser = await AuthService.getCurrentUser();
        const userOrders = await AccountService.getUserOrders();
        setUser(currentUser);
        setOrders(userOrders);
      } catch (err) {
        console.error("Ошибка загрузки данных:", err);
        setError("Ошибка при загрузке данных");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  if (loading) return <div>Загрузка...</div>;
  if (error) return <div>{error}</div>;
  if (!user) return <div>Пользователь не найден</div>;

  return (
    <>
      <Navigation />

      {!isSidebarOpen && (
      <div className="sidebar-toggle-wrapper">
      {/* Кнопка-бургер для открытия сайдбара на мобилках */}
      <button
        className="sidebar-toggle-btn"
        onClick={() => setSidebarOpen(!isSidebarOpen)}
        aria-label="Открыть меню"
      >
        ☰
      </button>
        </div>
        )}
      {/* Затемнение под сайдбаром */}
      {isSidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}

      <div className="container account-container">
        {/* Sidebar с переключением класса для показа/скрытия */}
        <div
          className={`account-sidebar ${isSidebarOpen ? "open" : "closed"}`}
          onClick={() => setSidebarOpen(false)} // закрытие по клику вне контента
        >
          <div className="sidebar-content" onClick={(e) => e.stopPropagation()}>
            <h3>👤 Личный кабинет</h3>
            <ul>
              <li>
                <NavLink exact to={`${url}`} activeClassName="active-link" onClick={() => setSidebarOpen(false)}>
                  <i className="fa fa-history"></i> История заказов
                </NavLink>
              </li>
              <li>
                <NavLink to={`${url.replace(/\/$/, "")}/wishlist`} activeClassName="active-link" onClick={() => setSidebarOpen(false)}>
                  <i className="fa fa-heart"></i> Избранные
                </NavLink>
              </li>
              <li>
                <button
                  onClick={() => {
                    setCartOpen(true);
                    setSidebarOpen(false);
                  }}
                  className="link-btn"
                >
                  <i className="fa fa-shopping-cart"></i> Корзина
                </button>
              </li>
              <li>
                <button
                  onClick={() => {
                    setProfileOpen(true);
                    setSidebarOpen(false);
                  }}
                  className="link-btn"
                >
                  <i className="fa fa-user-circle"></i> Редактировать профиль
                </button>
              </li>
              <li>
                <Link to="/compare" onClick={() => setSidebarOpen(false)}>
                  <i className="fa fa-balance-scale"></i> Сравнения
                </Link>
              </li>
              <li>
                <Link to="/logout" onClick={() => setSidebarOpen(false)}>
                  <i className="fa fa-sign-out"></i> Выйти
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Модальные окна */}
        {isCartOpen && (
          <div className="modal-overlay" onClick={() => setCartOpen(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <button onClick={() => setCartOpen(false)} className="close-btn">
                ×
              </button>
              <Cart />
            </div>
          </div>
        )}

        {isProfileOpen && (
          <div className="modal-overlay" onClick={() => setProfileOpen(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <button onClick={() => setProfileOpen(false)} className="close-btn">
                ×
              </button>
              <Profile user={user} />
            </div>
          </div>
        )}

        {/* Main Content */}
        <div className="account-content">
          <Switch>
            <Route exact path={path}>
              <OrderHistory orders={orders} />
            </Route>
            <Route path={`${path}/wishlist`}>
              <Wishlist />
            </Route>
          </Switch>
        </div>
      </div>
    </>
  );
};

export default AccountDashboard;
