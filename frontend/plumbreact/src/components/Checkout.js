import React, { Component } from "react";
import Navigation from "./Navigation";

import CartService from "../services/CartService";
import { Link } from "react-router-dom";

class Checkout extends Component {
  constructor(props) {
    super(props);
    this.state = {
      cart: [], // Данные корзины
      loaded: false, // Флаг загрузки
      placeholder: "Loading...", // Текст ожидания
      error: null, // Ошибки
      formErrors: {}, // ошибки по каждому полю
      shippingDetails: {
        firstName: "",
        lastName: "",
        middleName: "",
        email: "",
        address: "",
        city: "",
        tel: "",
        telegram: "",
        whatsapp: "",
        paymentType: "full",  // ✅ значение по умолчанию
      },
    };

    this.inputRefs = {
      shippingDetails: {},
    };
  }

  componentDidMount() {
    this.loadCartFromLocalStorage();
      window.addEventListener("storage", this.syncCartAcrossTabs);
  }

  componentWillUnmount() {
  window.removeEventListener("storage", this.syncCartAcrossTabs);
}

  syncCartAcrossTabs = (e) => {
    if (e.key === "cart") {
      this.loadCartFromLocalStorage();
    }
  };

  loadCartFromLocalStorage = () => {
    try {
      const cartData = localStorage.getItem("cart");
      if (cartData) {
        this.setState({ cart: JSON.parse(cartData), loaded: true });
      } else {
        this.setState({ placeholder: "Your cart is empty.", loaded: true });
      }
    } catch (error) {
      this.setState({
        placeholder: "Failed to load cart. Please try again.",
        loaded: false,
        error,
      });
      console.error("Error loading cart:", error);
    }
  };

  // Проверка и синхронизация перед Checkout
  // Метод для создания корзины
  handleCreateCart = async () => {
    const cartItems = this.state.cart.map((item) => ({
      product: item.productId,
      variant: item.variantId || null,
      quantity: item.quantity,
    }));

    try {
      const cartUUID = localStorage.getItem("cart_uuid");

      if (!cartUUID) {
        // Если cart_uuid отсутствует, создаём новую корзину
        const response = await CartService.createCart(cartItems);

        // Сохраняем новый cart_uuid
        const { cart_uuid: newCartUUID } = response;
        if (newCartUUID) {
          localStorage.setItem("cart_uuid", newCartUUID);
        }
      } else {
        // Если cart_uuid есть, отправляем текущие товары
        await CartService.createCart(cartItems);
      }
    } catch (error) {
      console.error("Error creating cart:", error);
      this.setState({ error: "Error creating cart. Please try again." });
    }
  };

// Изменяем validateForm:

// validateForm с подсказками
validateForm = () => {
  const { shippingDetails } = this.state;
  const errors = {};
  const optionalFields = ["telegram", "whatsapp"];

  for (let key in shippingDetails) {
    const val = shippingDetails[key].trim();
    if (!val && !optionalFields.includes(key)) {
      errors[key] = "Это поле обязательно";
      continue;
    }

    // Проверки по типу поля
    if (key === "firstName" || key === "middleName" || key === "lastName") {
      if (val && !/^[А-Яа-яA-Za-z\s\-]+$/.test(val)) {
        errors[key] = "Только буквы и пробелы допустимы";
      }
    }
    if (key === "email") {
      if (val && !/^\S+@\S+\.\S+$/.test(val)) {
        errors[key] = "Введите корректный email (например, name@mail.com)";
      }
    }
    if (key === "tel") {
      // Пример для РФ: +7 999 999-99-99 или без пробелов
   const digits = val.replace(/\D/g, ""); // только цифры
  if (!/^7\d{10}$/.test(digits)) {
    errors[key] = "Введите телефон в формате +7XXXXXXXXXX";
      }
    }
 
  }

  this.setState({ formErrors: errors });

  // Фокус на первое поле с ошибкой
  const firstErrorKey = Object.keys(errors)[0];
  if (firstErrorKey) {
    const ref = this.inputRefs.shippingDetails[firstErrorKey];
    if (ref) ref.focus();
  }

  return Object.keys(errors).length === 0;
};


  handleCreateOrder = async () => {
    if (!this.validateForm()) return;
    try {
      // Создаём корзину
      await this.handleCreateCart();
  
      const cart_uuid = localStorage.getItem("cart_uuid");
  
      if (!cart_uuid) {
        this.setState({ error: "Ошибка: корзина не была создана." });
        return;
      }
  
      const { shippingDetails } = this.state;
      const orderData = {
        customer_name: `${shippingDetails.firstName} ${shippingDetails.lastName} ${shippingDetails.middleName}`,
        email: shippingDetails.email,
        phone_number: shippingDetails.tel,
        address: shippingDetails.address,
        city: shippingDetails.city,
        telegram: shippingDetails.telegram,
        whatsapp: shippingDetails.whatsapp,
        payment_type: shippingDetails.paymentType || "full",
        cart_uuid: cart_uuid, // Здесь отправляем только cart_uuid (ID корзины), а не её объект
        // cart: cart,
      };

      // Отправляем заказ на сервер
      const response = await CartService.createOrder(orderData);

      if (response && (response.status === 201 || response.data?.orderId)) {
        // Очистка корзины и редирект
        localStorage.removeItem("cart");
        localStorage.removeItem("cart_uuid");
        localStorage.removeItem("orderItems");
        // 👉 Сообщаем родителю, что корзина теперь пуста (для хедера)
        if (this.props.onCartUpdate) {
          this.props.onCartUpdate([]); // передаём пустой массив
        }


        this.setState({ cart: [], successMessage: "Order created successfully!" }, () => {
          // После очистки редирект на главную
          this.props.history.push("/");
        });
      } else {
        console.error("Failed to create order.", response);
        this.setState({ error: "Failed to create order. Please check your details." });
      }
    } catch (error) {
    if (error.response) {
      console.error("Server error:", error.response.data);
      this.setState({ error: `Ошибка сервера: ${JSON.stringify(error.response.data)}` });
    } else {
      console.error("Error creating order:", error.message);
      this.setState({ error: "Error creating order. Please try again." });
    }
  }
};

handleRemoveItem = (indexToRemove) => {
  this.setState(
    (prevState) => {
      const updatedCart = prevState.cart.filter((_, index) => index !== indexToRemove);
      localStorage.setItem("cart", JSON.stringify(updatedCart));
      return { cart: updatedCart };
    },
    () => {
      if (this.props.onCartUpdate) {
        this.props.onCartUpdate(this.state.cart);
      }
    }
  );
};


handleQuantityChange = (index, newQuantity) => {
  if (newQuantity < 1) return; // Не допускаем меньше 1

  this.setState((prevState) => {
    const updatedCart = [...prevState.cart];
    updatedCart[index].quantity = newQuantity;
    localStorage.setItem("cart", JSON.stringify(updatedCart));
    return { cart: updatedCart };
  });
};
  
  
  
// Изменяем handleInputChange:
handleInputChange = (event, section) => {
  const { name, value } = event.target;

  this.setState((prevState) => ({
    ...prevState,
    [section]: {
      ...prevState[section],
      [name]: value,
    },
    formErrors: {
      ...prevState.formErrors,
      [name]: undefined, // убираем ошибку при редактировании
    },
  }));
};

render() {
  const { cart, loaded, placeholder, shippingDetails } = this.state;

  return (
    <>
      <Navigation />
      <div id="breadcrumb" className="section">
        {/* Добавляем прямо под breadcrumb */}



        <div className="container">
          <div className="row">
            <div className="col-md-12">
              <ul className="breadcrumb-tree">
                <li><Link to="/">Домой</Link></li>
                <li><Link to="/cart">Корзина</Link></li>
                <li className="active">Заказ</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
      <div className="checkout-cards" style={{ 
  display: 'flex', 
  flexWrap: 'wrap', 
  gap: '16px', 
  justifyContent: 'center', // центрируем карточки

}}>
  <div className="checkout-card" style={{ 
    maxWidth: '250px',  
    padding: '12px', 
    border: '1px solid #ddd', 
    borderRadius: '8px', 
    boxSizing: 'border-box',
    flex: '0 0 auto',
    textAlign: 'center', // текст внутри карточки по центру

  }}>
    
    <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
      Гарантия на товар
      <img 
        src={require('../assets/guarantee1.png')} 
        alt="Гарантия" 
        style={{ width: '50px', height: '50px' }}
      />
    </h4>

    <p style={{ fontSize: '14px' }}>
      Если товар окажется повреждённым, мы компенсируем потраченное время и расходы.
    </p>
  </div>

  <div className="checkout-card" style={{ 
    maxWidth: '250px', 
    padding: '12px', 
    border: '1px solid #ddd', 
    borderRadius: '8px',
    boxSizing: 'border-box',
    flex: '0 0 auto',
    textAlign: 'center',

  }}>
    <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
      Доставка
      <img 
        src={require('../assets/delivery_logo1.png')} 
        alt="Доставка" 
        style={{ width: '50px', height: '50px' }}
      />
    </h4>
    <p style={{ fontSize: '14px' }}>
      Доставка до двери нашими силами или любым перевозчиком на ваш выбор.
    </p>
  </div>
</div>


      <div className="container">
        <div className="checkout-wrapper">
          {/* === Shipping Only Section === */}
          <div className="shipping-section">
            <div className="shipping-details">
              <h3 className="title">Контактные данные</h3>

              {
            [
              { key: "firstName",   type: "text",  placeholder: "Имя" },
              { key: "middleName",  type: "text",  placeholder: "Отчество" },
              { key: "lastName",    type: "text",  placeholder: "Фамилия" },
              { key: "email",       type: "email", placeholder: "Электронная почта" },
              { key: "tel",         type: "tel",   placeholder: "Телефон" },
              // { key: "address",     type: "text",  placeholder: "Адрес доставки" },
              // { key: "city",        type: "text",  placeholder: "Город" },
              { key: "telegram",    type: "text",  placeholder: "Telegram (необязательно)" },
              { key: "whatsapp",    type: "text",  placeholder: "WhatsApp (необязательно)" },
            ]

              .map(({ key, type, placeholder }) => (
                <div className="form-group" key={key}>
                  <input
                    ref={(el) => (this.inputRefs.shippingDetails[key] = el)}
                    className={`input ${this.state.formErrors[key] ? 'input-error' : ''}`}
                    type={type}
                    name={key}
                    placeholder={placeholder}
                    value={shippingDetails[key]}
                    onChange={(e) => this.handleInputChange(e, "shippingDetails")}
                  />
                     {/* Показываем подсказку, если есть ошибка */}
                    {this.state.formErrors[key] && (
                      <span className="error-msg">{this.state.formErrors[key]}</span>
                    )}
                </div>
              ))}


  {/* отдельный заголовок для адреса */}
  <h3 className="title">Адрес доставки</h3>

  {[
    { key: "address", type: "text", placeholder: "Адрес доставки" },
    { key: "city",    type: "text", placeholder: "Город" },
  ].map(({ key, type, placeholder }) => (
    <div className="form-group" key={key}>
      <input
        ref={(el) => (this.inputRefs.shippingDetails[key] = el)}
        className={`input ${this.state.formErrors[key] ? 'input-error' : ''}`}
        type={type}
        name={key}
        placeholder={placeholder}
        value={shippingDetails[key]}
        onChange={(e) => this.handleInputChange(e, "shippingDetails")}
      />
      {this.state.formErrors[key] && (
        <span className="error-msg">{this.state.formErrors[key]}</span>
      )}
    </div>
  ))}

              {/* заметки к заказу (необязательно) */}
              <textarea
                className="input"
                placeholder="Комментарий к заказу (необязательно)"
                onChange={(e) => this.setState({
                  shippingDetails: { ...shippingDetails, comment: e.target.value }
                })}
              />
            </div>
          </div>

          {/* === Order Summary Section === */}
          <div className="order-details">
            <h3 className="order-title">Ваш заказ</h3>

            {!loaded ? (
              <p>{placeholder}</p>
            ) : cart.length === 0 ? (
              <p>Корзина пуста.</p>
            ) : (
              <>
                <div className="order-items">
                  {cart.map((item, index) => (
                    <div className="order-item" key={index}>

                      <Link to={`/products/${item.productSlug}/variant/${item.variantSlug}`} className="order-item-image">
                        <img src={item.photo} alt={item.name} />
                      </Link>

                      <div className="order-item-info">
                        <div className="order-item-header">
                          <Link to={`/products/${item.productSlug}/variant/${item.variantSlug}`}  className="order-item-name">
                            {item.name}
                          </Link>
                          <button
                            className="remove-item-btn"
                            onClick={() => this.handleRemoveItem(index)}
                          >
                            &times;
                          </button>
                        </div>

                        <div className="order-item-controls">
                          <span>Цена: {item.price} ₴</span>
                          <input
                            type="number"
                            min="1"
                            value={item.quantity}
                            onChange={(e) =>
                              this.handleQuantityChange(index, parseInt(e.target.value))
                            }
                            className="input quantity-input"
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                  {/* === Order Total === */}
                  <div className="order-total">
                    <span>
                      Итого ({cart.reduce((total, item) => total + item.quantity, 0)} шт.):
                    </span>
                    <span>
                      {(() => {
                        const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
                        const isPartial = shippingDetails.paymentType === "partial";
                        const displayTotal = isPartial ? total / 2 : total;

                        return `${displayTotal.toFixed(2)} ₴${isPartial ? " (50% предоплата)" : ""}`;
                      })()}
                    </span>
                  </div>



{/* === Выбор способа оплаты === */}
<div className="payment-type">
  <label>Способ оплаты:</label>

  <label className="option">
    <input
      type="radio"
      name="paymentType"
      value="full"
      checked={this.state.shippingDetails.paymentType === "full"}
      onChange={(e) =>
        this.setState({
          shippingDetails: {
            ...shippingDetails,
            paymentType: e.target.value,
          },
        })
      }
    />
    Полная оплата
  </label>

  <label className="option">
    <input
      type="radio"
      name="paymentType"
      value="partial"
      checked={this.state.shippingDetails.paymentType === "partial"}
      onChange={(e) =>
        this.setState({
          shippingDetails: {
            ...shippingDetails,
            paymentType: e.target.value,
          },
        })
      }
    />
    50% предоплата
  </label>
</div>

                <button
                  onClick={this.handleCreateOrder}
                  className="order-submit-btn"
                >
                  Оформить заказ
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}


}

export default Checkout;
