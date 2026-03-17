import React, { useState } from "react";
import { Link } from 'react-router-dom';
import AccountService from "../services/AccountService";


const OrderCard = ({ order }) => {

  const [isExpanded, setIsExpanded] = useState(false);
  const [orderDetails, setOrderDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

    const toggleExpand = async () => {
    if (!isExpanded && !orderDetails) {
      setLoadingDetails(true);
      try {
        const detailedOrder = await AccountService.getOrderDetails(order.id); // 👈
        setOrderDetails(detailedOrder);
      } catch (error) {
        console.error("Ошибка загрузки деталей заказа:", error);
      } finally {
        setLoadingDetails(false);
      }
    }
    setIsExpanded(!isExpanded);
  };



return (
  <div className="order-card">
    <div className="order-header">
      <div>
        <span className="order-id">Заказ #{order.id}</span>
        <span className={`order-status ${order.status_order.toLowerCase()}`}>{order.status_order_display}</span>
      </div>
      <button className="dropdown-toggle" onClick={toggleExpand}>
        {isExpanded ? "▲" : "▼"}
      </button>
    </div>

    {/* Миниатюры товаров */}
    <div className="order-thumbnails">
      {order.list_of_products?.slice(0, 5).map((item, index) => (
        <div key={index} className="thumbnail-container">

        <img
          key={index}
          src={item.photo || "/placeholder.jpg"}
          alt={item.name}
          className="thumb-img"
        />

        </div>
      ))}
    </div>
    
    <div className="order-info">
    <div className="order-body">
        <div>
    <strong>Данные о заказе:</strong>
    {/* <pre>{JSON.stringify(order, null, 2)}</pre> Выводим весь объект заказа */}
    </div>

      <div><strong>Оплата:</strong> {order.payment_status_display}</div>
      <div><strong>Дата:</strong> {new Date(order.creation_date).toLocaleDateString()}</div>
      <div><strong>Сумма:</strong> {order.total_price} ₴</div>

    </div>
          {/* Миниатюры товаров до раскрытия */}
      <div className="order-thumbnails">
          {order.list_of_product_images?.map((item, index) => {
            return (
              <div key={index} className="thumbnail-container">
                <Link to={`/products/${item.product_id}/variant/${item.variant_id}`} className="thumbnail-link">
                  <img src={item.photo || "/placeholder.jpg"} alt="Product thumbnail" className="thumb-img" />
                </Link>
              </div>
            );
          })}
                </div>
          </div>
    {isExpanded && (
      <div className="order-details">
        {loadingDetails ? (
          <div>Загрузка деталей...</div>
        ) : orderDetails ? (
          <>
            <div className="order-left">
              <hr />
              <p><strong>Тип доставки:</strong> {orderDetails.delivery_type === "new_post" ? "Новая Почта" : "Самовывоз"}</p>
              {orderDetails.delivery_type === "new_post" ? (
                <>
                  <p><strong>Город:</strong> {orderDetails.city}</p>
                  <p><strong>Отделение:</strong> {orderDetails.department_number}</p>
                </>
              ) : (
                <p><strong>Самовывоз из:</strong> {orderDetails.pickup_location}</p>
              )}
              <p><strong>Город:</strong> {orderDetails.city}</p>
              <p><strong>Адрес(отделения):</strong> {orderDetails.address}</p>
              <p><strong>TTH:</strong> 342353424433</p>
              <hr />
              <p><strong>Получатель:</strong></p>
              <p>{orderDetails.customer_name}</p>
              <p>{orderDetails.phone_number}</p>
              <p>{orderDetails.email}</p>
            </div>

            <div className="order-right">
              <table className="order-items-table">
                <thead>
                  <tr>
                    <th>Фото</th>
                    <th>Товар</th>
                    <th>Цена</th>
                    <th>Кол-во</th>
                    <th>Сумма</th>
                  </tr>
                </thead>
                <tbody>
                  {orderDetails.list_of_products?.map((item, index) => (
                    <tr key={index}>
                      <td data-label="Фото">
                        <Link to={`/products/${item.product_id}/variant/${item.variant?.id}`} className="thumbnail-link">
                          <img
                            src={item.photo || "/placeholder.jpg"}
                            alt={item.name}
                            style={{ width: "60px", height: "60px", objectFit: "cover", borderRadius: "6px" }}
                          />
                        </Link>
                      </td>
                      <td data-label="Товар">{item.name}</td>
                      <td data-label="Цена">{item.price} ₴</td>
                      <td data-label="Кол-во">{item.quantity}</td>
                      <td data-label="Сумма">{(item.price * item.quantity).toFixed(2)} ₴</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="order-summary">
                <p><strong>Оплата(банка наличка гуугл аппле пей тд):</strong> {orderDetails.payment_method || "—"}</p>
                <p><strong>Доставка(расчет за доставку почтой):</strong> {orderDetails.delivery_cost === 0 ? "Бесплатно" : `${orderDetails.delivery_cost} ₴`}</p>
                <p><strong>Всего:</strong> {orderDetails.total_price} ₴</p>

                 <div className="order-buttons">
                <button className="btn-view-receipt">📄 Посмотреть чек</button>

                  {orderDetails.payment_status === "waiting_for_payment" && (
                    <button
                      className="btn-cancel-order"
                      onClick={async () => {
                        if (window.confirm("Вы уверены, что хотите отменить этот заказ?")) {
                          try {
                            await AccountService.cancelOrder(order.id);
                            alert("Заказ успешно отменён");
                            window.location.reload();
                          } catch (error) {
                            alert("Не удалось отменить заказ.");
                          }
                        }
                      }}
                    >
                      ❌ Отменить заказ
                    </button>
                  )}
                </div>
              </div>
            </div>
          </>
        ) : (
          <div>Не удалось загрузить детали заказа.</div>
        )}
      </div>
    )}
  </div>
);
};


export default OrderCard;
