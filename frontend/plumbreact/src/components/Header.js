import React, { Component } from "react";
import { Link, withRouter  } from "react-router-dom";
import ProductsService from "../services/ProductService";
import { AuthContext } from "../context/AuthContext";
import Cart from "./Cart";
import { getSiteSettings } from "../services/siteSettingsService";
import CartService from "../services/CartService";

const service = new ProductsService();


class Header extends Component {
  static contextType = AuthContext;

  constructor(props) {
    super(props);
    this.state = {
      cart: JSON.parse(localStorage.getItem("cart")) || [],
      wishlist: JSON.parse(localStorage.getItem("wishlist")) || [],
      compare: JSON.parse(localStorage.getItem("compare")) || [],
      isCartOpen: false,
      searchQuery: "",
      searchResults: [],
      isDropdownOpen: false,
      showDropdown: false,
      allCategories: [],
      siteSettings: null, // 🔹 новые настройки с бэка
    };
    this.debounceTimer = null;
    this.previousUser = this.context ? this.context.user : null;
  }

  async componentDidMount() {
    window.addEventListener("wishlistUpdated", this.handleWishlistUpdate);
    window.addEventListener("storage", this.handleStorage);
    window.addEventListener("cartUpdated", this.handleStorage); // ✅ Оба ведут к одному методу
    window.addEventListener("localStorageUpdated", this.handleWishlistUpdate); // Додаємо слухач
    window.addEventListener("compareUpdated", this.syncCompare);
    service.getAllCategories().then(categories => {
      this.setState({ allCategories: categories });
    });
    this.loadUserData();
      // 🔹 грузим контакты с Django
    try {
      const settings = await getSiteSettings();
      this.setState({ siteSettings: settings });
    } catch (error) {
      console.error("Ошибка загрузки site settings:", error);
    }
  }

  // / New method
  handleWishlistUpdate = () => {
    this.loadUserData();
  };

  componentWillUnmount() {
    window.removeEventListener("wishlistUpdated", this.handleWishlistUpdate);
    window.removeEventListener("localStorageUpdated", this.handleWishlistUpdate);
      window.removeEventListener("cartUpdated", this.handleStorage);
    window.removeEventListener("storage", this.handleStorage);
    window.removeEventListener("compareUpdated", this.syncCompare);
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
  }

  componentDidUpdate(prevProps, prevState) {
    const currentUser = this.context.user;
    if (currentUser !== this.previousUser) {
      this.previousUser = currentUser;
      this.loadUserData();
    }
  }

  handleStorage = () => {
    const { user } = this.context;
    if (user && user.pk) {
      this.loadUserData();
    } else {
      const localCart = JSON.parse(localStorage.getItem("cart")) || [];
      const localWishlist = JSON.parse(localStorage.getItem("wishlist")) || [];
      const localCompare = JSON.parse(localStorage.getItem("compare")) || [];
      this.setState({ cart: localCart, wishlist: localWishlist, compare: localCompare });
    }
  };
// In loadUserData (small log addition for debug)
  async loadUserData() {
    try {
      const { user } = this.context;
      if (user && user.pk) {
        const serverWishlist = await service.getWishlist();
        const serverCart = JSON.parse(localStorage.getItem("cart")) || []; // можно заменить на await CartService.getCart() если сервер
        this.setState({ wishlist: serverWishlist ,  cart: serverCart});
        // localStorage.setItem("wishlist", JSON.stringify(serverWishlist));
      } else {
        const localWishlist = JSON.parse(localStorage.getItem("wishlist")) || [];
        this.setState({ wishlist: localWishlist });
      }
      // Handle cart/compare similarly if needed
    } catch (error) {
      console.error("Ошибка при загрузке данных в Header:", error);
    }
  }


  syncCompare = () => {
    const compare = JSON.parse(localStorage.getItem("compare")) || [];
    this.setState({ compare });
  };

  handleRemoveItem = (productId) => {
    const updatedCart = this.state.cart.filter(
      (item) => item.productId !== productId
    );
    localStorage.setItem("cart", JSON.stringify(updatedCart));
    this.setState({ cart: updatedCart });
    window.dispatchEvent(new Event("storage"));
  };

  toggleCartModal = () => {
    this.setState((prev) => ({ isCartOpen: !prev.isCartOpen }));
  };

  closeCartModal = () => {
    this.setState({ isCartOpen: false });
  };

  handleSearchInput = (e) => {
    const query = e.target.value;
    this.setState({ searchQuery: query, showDropdown: true });

    if (this.debounceSearch) clearTimeout(this.debounceSearch);

    this.debounceSearch = setTimeout(() => {
      if (query.trim().length === 0) {
        this.setState({ searchResults: [], showDropdown: false });
        return;
      }

      service.searchProducts(query)
        .then(results => {
          this.setState({ searchResults: results || [], showDropdown: true });
        })
        .catch(() => {
          this.setState({ searchResults: [], showDropdown: false });
        });
    }, 300);
  };

  handleResultClick = (productId, variantId) => {
    this.setState({ searchQuery: "", searchResults: [], showDropdown: false }, () => {
      this.props.history.push(`/products/${productId}/variant/${variantId}`);
    });
  };

  handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      this.handleSearchSubmit(e);
    }
  };

  handleBlur = () => {
    setTimeout(() => {
      this.setState({ isDropdownOpen: false });
    }, 200);
  };

  handleSearchSubmit = (e) => {
    e.preventDefault();
    const { searchQuery, allCategories } = this.state;

    if (!searchQuery.trim()) return;

    const normalizedQuery = searchQuery.trim().toLowerCase();
    const matchedCategory = allCategories.find(cat =>
      cat.name.toLowerCase().includes(normalizedQuery)
    );

    if (matchedCategory) {
      this.props.history.push(`/products?category=${matchedCategory.id}`);
    } else {
      this.props.history.push(`/search?q=${encodeURIComponent(searchQuery)}`);
    }

    this.setState({ showDropdown: false });
  };

  render() {
    const { cart, wishlist, isCartOpen ,compare, siteSettings, searchQuery,
      searchResults,
      isDropdownOpen,} = this.state;
    const { user } = this.context;


        return (
      <>
        <header>
          <div id="top-header">
            <div className="container">
              <ul className="header-links pull-left">
                <li>
                  <a href={`tel:${siteSettings?.phone || ""}`}>
                    <i className="fa fa-phone"></i>{" "}
                    {siteSettings?.phone || "+000-00-00"}
                  </a>
                </li>
                <li>
                  <a href={`mailto:${siteSettings?.email || ""}`}>
                    <i className="fa fa-envelope-o"></i>{" "}
                    {siteSettings?.email || "no-email@example.com"}
                  </a>
                </li>
              </ul>

              <ul className="header-links pull-right">
                {/* <li><a href="#"><i className="fa fa-dollar"></i> USD</a></li> */}
                {user ? (
                  <>
                    <li><Link to="/account/"><i className="fa fa-user-o"></i> Личный кабинет</Link></li>
                    <li><Link to="/logout"><i className="fa fa-sign-out"></i> Выход</Link></li>
                  </>
                ) : (
                  <>
                    <li><Link to="/login"><i className="fa fa-sign-in"></i> Вход</Link></li>
                    <li><Link to="/register"><i className="fa fa-user-plus"></i> Регистрация</Link></li>
                  </>
                )}
              </ul>
            </div>
          </div>

          <div id="header">
            <div className="container">
              <div className="row">
                <div className="col-md-3">
                  <div className="header-logo">
                    <a href="/" className="logo">
                      <img src={process.env.PUBLIC_URL + "/img/logo.png"} width="169" height="70" alt="Лавиан" />
                    </a>
                  </div>
                </div>
                <div className="col-md-6">
                  <div className="header-search" style={{ position: "relative" }}>
                    <form onSubmit={this.handleSearchSubmit}>
                        <input
                          className="input"
                          placeholder="поиск"
                          value={this.state.searchQuery}
                          onChange={this.handleSearchInput}
                          onKeyDown={this.handleKeyDown}
                          onFocus={() => this.setState({ showDropdown: true })}
                          onBlur={() => setTimeout(() => this.setState({ showDropdown: false }), 200)} // чтобы клик успел сработать
                        />
                        <button className="search-btn" type="submit">Поиск</button>
                        {this.state.showDropdown && this.state.searchResults.length > 0 && (
                          <ul className="search-dropdown">
                            {this.state.searchResults.map(product => (
                              <li key={product.id}>
                              <Link to={`/products/${product.slug}/variant/${product.first_variant?.slug || ""}`}>
                                  {product.name}
                                </Link>
                              </li>
                            ))}
                          </ul>
                        )}
                      </form>
                  </div>
                </div>
                <div className="col-md-3 clearfix">
                  {/* Здесь твой остальной Header */}
                  <div className="header-ctn">
                    <div>
                      <a href="/wishlist">
                        <i className="fa fa-heart-o"></i>
                        <span>Избранное</span>
                        <div className="qty">{wishlist.length}</div>
                      </a>
                    </div>
                    <div>
                      <a href="/compare">
                        <i className="fa fa-exchange" />
                        <span>Сравненить</span>
                        <div className="qty">{compare.length}</div>
                      </a>
                    </div>
                    <div>
                      <a onClick={this.toggleCartModal} style={{ cursor: 'pointer' }}>
                        <i className="fa fa-shopping-cart"></i>
                        <span>Your Cart</span>
                        <div className="qty">{cart.length}</div>
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </header>

        {isCartOpen && (
          <div className="modal-overlay" onClick={this.closeCartModal}>
            <div className="cart-modal-content" onClick={(e) => e.stopPropagation()}>
              <button onClick={this.closeCartModal} className="close-btn">×</button>
              <Cart onClose={this.closeCartModal} />
            </div>
          </div>
        )}
      </>
    );
  }
}

export default withRouter(Header);

