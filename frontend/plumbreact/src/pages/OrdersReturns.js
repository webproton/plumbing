// OrdersReturns.js
import React from "react";
const OrdersReturns = () => {
  return (
    <div className="orders-returns-page">
      <h2>Заказы и возвраты</h2>
      <p>
        Здесь вы можете узнать всё о правилах оформления заказов и возврата товаров.
      </p>

      <div className="info-blocks">
        <div className="info-block">
          <h4>Оформление заказов</h4>
          <p>
            Вы можете оформить заказ через корзину на сайте или связавшись с нашим менеджером.
          </p>
        </div>

        <div className="info-block">
          <h4>Возврат товаров</h4>
          <p>
            Возврат товара возможен в течение 14 дней с момента покупки при сохранении упаковки и чека.
          </p>
        </div>
      </div>

      {/* Первая таблица */}
      <div className="return-table">
        <h4>Правила возврата:</h4>
   
      </div>

      {/* Вторая таблица */}
      <div className="defect-table">
        <h4>При обнаружении брака:</h4>

      </div>
    </div>
  );
};

export default OrdersReturns;