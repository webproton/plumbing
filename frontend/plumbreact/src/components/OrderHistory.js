import React, { useEffect, useState } from "react";
import AccountService from "../services/AccountService";
import OrderCard from "./OrderCard"; // Импорт нового компонента

const OrderHistory = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchOrders() {
      try {
        const data = await AccountService.getUserOrders();
        setOrders(data);
      } catch (err) {
        console.error("Ошибка при загрузке заказов:", err);
        setError("Не удалось загрузить заказы");
      } finally {
        setLoading(false);
      }
    }
    fetchOrders();
  }, []);

  if (loading) return <div>Загрузка заказов...</div>;
  if (error) return <div>{error}</div>;
  if (orders.length === 0) return <div>У вас пока нет заказов.</div>;

  return (
        <div className="order-history">
      <h2>🧾 История заказов</h2>
      <div className="order-list">
        {orders.map(order => (
          <OrderCard key={order.id} order={order} />
        ))}
      </div>
    </div>
  );
};


export default OrderHistory;