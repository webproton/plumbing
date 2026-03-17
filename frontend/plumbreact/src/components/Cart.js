import React, { Component } from "react";
import CartService from "../services/CartService";
import { withRouter, Link } from "react-router-dom";
import { syncCart ,removeFromCart, updateCartItemQuantity,} from "../utils/cartUtils";




class Cart extends Component {
  constructor(props) {
    super(props);
    this.state = {
      cartItems: [], // Корзина товаров
      subtotal: 0, // Промежуточная сумма
      loading: false,
      error: null,
      selectedItems: [], // <== добавили
      
    };
    
  }

  // Утилита для формирования уникального ключа
  getItemKey = (item) => {
    // Возвращаем уникальный ключ для товара с вариантом или без
    return item.variantId ? `${item.productId}-${item.variantId}` : `${item.productId}`;
  };

  async componentDidMount() {
    window.addEventListener("storage", this.syncCart);
    this.loadCartFromLocalStorage();

  }

  componentWillUnmount() {
    window.removeEventListener("storage", this.syncCart);
  }

  syncCart = () => {
    syncCart(this); // Используем утилиту
    this.setState(prevState => ({
      selectedItems: prevState.cartItems.map(this.getItemKey),
      subtotal: this.calculateSubtotal(prevState.cartItems, prevState.cartItems.map(this.getItemKey)),
    }));
  };

 
  // Метод для загрузки корзины из localStorage
  loadCartFromLocalStorage = () => {
    
    const cartItems = JSON.parse(localStorage.getItem("cart")) || []; // Чтение данных из localStorage
    const selectedItems = cartItems.map(this.getItemKey);
    const subtotal = this.calculateSubtotal(cartItems, selectedItems);
    this.setState({ cartItems, selectedItems, subtotal }); // Сохраняем в state и пересчитываем сумму

  };
  // Пересчёт суммы с учётом выбранных вариантов
  calculateSubtotal = (cartItems, selectedItems) => {
    return cartItems
      .filter(item => selectedItems.includes(this.getItemKey(item)))
      .reduce((sum, item) => sum + item.price * item.quantity, 0);
  };

  handleCheckboxChange = (itemKey) => {
    this.setState((prevState) => {
      const alreadySelected = prevState.selectedItems.includes(itemKey);
      const selectedItems = alreadySelected
        ? prevState.selectedItems.filter((key) => key !== itemKey)
        : [...prevState.selectedItems, itemKey];
      const subtotal = this.calculateSubtotal(prevState.cartItems, selectedItems);
      return { selectedItems, subtotal };
    });
  };


  handleQuantityChange = (itemKey, newQuantity) => {
    if (newQuantity < 1) return;

    const [productId, variantId] = itemKey.split("-").map(Number);
    updateCartItemQuantity(productId, Number(variantId) || null, newQuantity);

    this.setState(
      prevState => {
        const updatedCartItems = prevState.cartItems.map(item => {
          if (this.getItemKey(item) === itemKey) {
            return { ...item, quantity: newQuantity };
          }
          return item;
        });
        const subtotal = this.calculateSubtotal(updatedCartItems, prevState.selectedItems);
        return { cartItems: updatedCartItems, subtotal };
      }
    );
  };


  handleRemoveItem = (itemKey) => {
    const [productId, variantId] = itemKey.split("-").map(Number);
    removeFromCart(productId, Number(variantId) || null);

    this.setState(prevState => {
      const updatedCartItems = prevState.cartItems.filter(
        item => this.getItemKey(item) !== itemKey
      );
      const updatedSelectedItems = prevState.selectedItems.filter(key => key !== itemKey);
      const subtotal = this.calculateSubtotal(updatedCartItems, updatedSelectedItems);
      return {
        cartItems: updatedCartItems,
        selectedItems: updatedSelectedItems,
        subtotal,
      };
    });
  };


 // Обновление локальной корзины и синхронизация с сервером

  handleCartChange = async (updatedCartItems) => {
    this.setState({ cartItems: updatedCartItems, loading: true });
    const cartUUID = localStorage.getItem("cart_uuid");

    try {
      const response = await CartService.createCart(updatedCartItems, cartUUID);
      const { cart_uuid: newCartUUID } = response;

      if (newCartUUID) {
        localStorage.setItem("cart_uuid", newCartUUID);
      }

      const updatedServerItems = response.cart_items.map(item => ({
        productId: item.product,
        variantId: item.variant || null,
        quantity: item.quantity,
        price: item.price,
        name: item.product_name,
        photo: item.photo,

        productSlug: item.product_slug,   // <-- добавить
        variantSlug: item.variant_slug,   // <-- добавить
      }));
      this.setState({
        cartItems: updatedServerItems,
        subtotal: this.calculateSubtotal(updatedServerItems, this.state.selectedItems),
      });
    } catch (error) {
      console.error("Error syncing cart:", error.message);
      this.setState({ error: error.message });
    } finally {
      this.setState({ loading: false });
    }
  };

// handleCartChange = async (updatedCartItems) => {
//   this.setState({ cartItems: updatedCartItems, loading: true });

//   try {
//     const response = await CartService.createCart(updatedCartItems);

//     const updatedServerItems = response.cart_items.map(item => ({
//       productId: item.product,
//       variantId: item.variant || null,
//       quantity: item.quantity,
//       price: item.price,
//       name: item.product_name,
//       photo: item.photo,
//       productSlug: item.product_slug,
//       variantSlug: item.variant_slug,
//     }));

//     this.setState({
//       cartItems: updatedServerItems,
//       subtotal: this.calculateSubtotal(updatedServerItems, this.state.selectedItems),
//     });
//   } catch (error) {
//     this.setState({ error: error.message });
//   } finally {
//     this.setState({ loading: false });
//   }
// };

  handleNavigate = (path) => {
    const { cartItems, selectedItems } = this.state;
    const itemsToOrder = cartItems.filter(item =>
      selectedItems.includes(this.getItemKey(item))
    );
    localStorage.setItem("cart", JSON.stringify(itemsToOrder));
    window.dispatchEvent(new Event("storage")); // Добавляем синхронизацию
    if (this.props.onClose) this.props.onClose();
    this.props.history.push(path);
  };

//   handleClearCart = async () => {
//   try {
//     await CartService.deleteCart(); // удаляем корзину на сервере
//   } catch (e) {
//     console.warn("Не удалось удалить корзину на сервере");
//   }

//   this.setState({ cartItems: [], selectedItems: [], subtotal: 0 });
//   window.dispatchEvent(new Event("storage"));
// };

handleClearCart = () => {
  // Очистка localStorage
  localStorage.removeItem("cart");
  // Очистка cart_uuid если нужно
  localStorage.removeItem("cart_uuid");

  // Очистка состояния
  this.setState({
    cartItems: [],
    selectedItems: [],
    subtotal: 0,
  });

  // Синхронизация с другими вкладками
  window.dispatchEvent(new Event("storage"));
};


  render() {
    const { cartItems, subtotal, loading, error, selectedItems } = this.state;

    return (
        <>

    {/* <Navigation /> Навбар */}
      <div className="cart-container">
        <h1 className="cart-title">Корзина</h1>
  

{cartItems.length > 0 && (
  <div className="cart-selection-summary-wrapper">
    <div className="cart-selection-summary">
      Выбрано {selectedItems.length} из {cartItems.length}
    </div>
    <button
      onClick={this.handleClearCart}
      className="btn-clear-all"
    >
      Удалить все
    </button>
  </div>
)}
 
        {cartItems.length === 0 && <p className="empty-cart">Корзина пуста</p>}

          <div className="cart-items-list">
            {cartItems.map((item) => {
              const itemKey = this.getItemKey(item); // Например "123-45" или "123"
              return (
                <div key={itemKey} className="cart-item-card">
                  <input
                    type="checkbox"
                    checked={selectedItems.includes(itemKey)}
                    onChange={() => this.handleCheckboxChange(itemKey)}
                    className="cart-item-checkbox"
                  />

                  {/* {console.log(item,'<<<<<<<<,item carts')} */}
                  <Link
                    to={`/products/${item.productSlug}/variant/${item.variantSlug || ""}`}
                    onClick={() => {
                      if (this.props.onClose) this.props.onClose(); // закрываем модалку
                    }}
                  >
                    <img src={item.photo} alt={item.name} className="cart-item-image" />
                  </Link>
                  
                  <div className="cart-item-details">
                      <Link
                        to={`/products/${item.productSlug}/variant/${item.variantSlug || ""}`}
                        onClick={() => {
                          if (this.props.onClose) this.props.onClose(); // закрываем модалку
                        }}
                      >
                        {item.name}
                      </Link>
                    <div className="quantity-controls">
                      <button
                        className="quantity-button"
                        onClick={() => this.handleQuantityChange(itemKey, item.quantity - 1)}
                        disabled={item.quantity <= 1}
                      >
                        -
                      </button>
                      <input
                        type="number"
                        value={item.quantity}
                        onChange={(e) =>
                          this.handleQuantityChange(itemKey, parseInt(e.target.value) || 1)
                        }
                        className="quantity-input"
                        min="1"
                      />
                      <button
                        className="quantity-button"
                        onClick={() => this.handleQuantityChange(itemKey, item.quantity + 1)}
                      >
                        +
                      </button>
                    </div>
                  </div>
                  <div className="cart-item-price">{(item.price * item.quantity).toFixed(2)} ₴</div>
                  <button
                    onClick={() => this.handleRemoveItem(itemKey)}
                    className="btn-remove"
                    aria-label="Удалить товар"
                  >
                    ×
                  </button>
                </div>
              );
            })}
          </div>

        <div className="subtotal">
          <h3>Общая сумма: {subtotal.toFixed(2)} ₴</h3>
        </div>


        <div className="cart-actions">
          
          <button onClick={() => this.handleNavigate("/cart/")} 
          disabled={this.state.selectedItems.length === 0}
           className="btn-secondary">
            <i className="fa fa-shopping-cart" />Перейти в корзину
          </button>

          <button onClick={() => this.handleNavigate("/checkout/")} className="btn-primary">
            Оформить заказ <i className="fa fa-arrow-circle-right" />
          </button>
        </div>

        {error && <p className="error-message">{error}</p>}
      </div>
      </>
      
    );
    
  }
}

export default withRouter(Cart);