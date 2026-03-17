import React, { Component } from "react";
import { Link } from "react-router-dom";
import ProductsService from "../services/ProductService";
import { toggleCompareItem } from '../utils/compare';
import { addToCart, syncCart } from "../utils/cartUtils";

import { useWishlist } from "../context/WishlistContext";

class NewProducts extends Component {
  constructor(props) {
    super(props);
    this.state = {
      new_products_data: [],
      categories: [],
      loaded: false,
      placeholder: "Loading...",
    };
    this.newProducts = new ProductsService();
  }

  componentDidMount() {
    window.addEventListener("storage", this.syncCart);
    Promise.all([
      this.newProducts.getNewProducts(),
      this.newProducts.getCategory(),
    ])
      .then(([products, categories]) => {
        this.setState({
          new_products_data: products,
          categories,
          loaded: true,
        });
      })
      .catch((error) => {
        console.log("Error fetching data:", error);
        this.setState({
          placeholder: "Something went wrong!",
          loaded: true,
        });
      });


  }

  componentWillUnmount() {
    window.removeEventListener("storage", this.syncCart);
  }

// Wishlist
handleToggleWishlist = (product) => {
  const variant = product.first_variant;
  if (!variant?.id) return;

  const { toggleWishlist, wishlist } = this.props;
  toggleWishlist(variant);

  const isInWishlist = wishlist.some(w => w.product_variant.id === variant.id);
  const message = isInWishlist ? "Удалено из избранного" : "В избранное";

  this.showPopup(product.id, "wishlistPopup", message);
};

// Compare
handleAddToCompare = (product) => {
  const added = toggleCompareItem(product); // true = добавлено
  const message = added ? "В сравнение" : "Удалено из сравнения";

  this.showPopup(product.id, "comparePopup", message);
};



handleAddToCart = (product) => {
  if (!product.first_variant) return alert("Нет доступного варианта");

  addToCart(product);

  const productState = this.state.new_products_data.find(p => p.id === product.id);
  const message = productState.cartCount ? "+1" : "Добавлено";

  // Обновляем количество в корзине (для логики, если нужно)
  this.setState((prevState) => ({
    new_products_data: prevState.new_products_data.map((p) =>
      p.id === product.id
        ? { ...p, cartCount: (p.cartCount || 0) + 1 }
        : p
    ),
  }));

  // Показываем popup
  this.showPopup(product.id, "addedCart", message);
};



// универсальный popup
// Универсальный popup
showPopup = (productId, key, message) => {
  this.setState((prevState) => ({
    new_products_data: prevState.new_products_data.map((p) =>
      p.id === productId ? { ...p, [key]: message } : p
    ),
  }));

  setTimeout(() => {
    this.setState((prevState) => ({
      new_products_data: prevState.new_products_data.map((p) =>
        p.id === productId ? { ...p, [key]: null } : p
      ),
    }));
  }, 2000);
};

  syncCart = () => syncCart(this);

  render() {
    const { new_products_data, categories, loaded, placeholder } = this.state;
    const { wishlist } = this.props;

    if (!loaded) {
      return <div>{placeholder}</div>;
    }

    return (
      <div className="section">
        <div className="new-products-wrapper">
          <div className="section-title text-center">
            <h3 className="title">Новые поступления</h3>
            <div className="section-nav">
              <ul className="section-tab-nav tab-nav">
                {categories
                  .filter((category) => [1, 2, 3].includes(category.id))
                  .map((category) => (
                    <li key={category.id} className="active">
                      <Link to={`/products/?category=${category.slug}`} className="cta-btn">
                        {category.name}
                      </Link>
                    </li>
                  ))}
              </ul>
            </div>
          </div>

          <div className="row equal-height">
            {new_products_data.map((product) => (
              <div key={product.id} className="col-md-3 col-xs-6">
                <div className="product">
                  <div className="product-img">
                    <Link to={`/products/${product.slug}/variant/${product.first_variant?.slug}`}>
                      <img
                        src={product.first_variant?.photo}
                        alt={product.name}
                      />
                    </Link>

               <div className="product-label">
                  {product.first_variant?.discount > 0 && (
                    <span className="sale">-{product.first_variant.discount}%</span>
                  )}
                  <span className="new">NEW</span>
                </div>
                  </div>

                  
                  <div className="product-body">
                    <h3 className="product-name">
                      <Link to={`/products/${product.slug}/variant/${product.first_variant?.slug}`}>
                        {product.name}
                      </Link>
               
                    </h3>
                
        <h4 className="product-price">
  ₴ {product.first_variant?.price ?? "-"}
  {product.first_variant?.discount > 0 && (
    <del className="product-old-price">
      ₴ {product.first_variant?.original_price ?? "-"}
    </del>
  )}
</h4>

                      <div className="product-btns">
                        {/* Wishlist */}
                    <div className="btn-wrapper">
                      <button
                        className="product-btn"
                        onClick={() => this.handleToggleWishlist(product)}
                      >
                        <i className={`fa ${
                          wishlist.some(
                            (w) => w.product_variant.id === product.first_variant?.id
                          )
                            ? "fa-heart"
                            : "fa-heart-o"
                        }`} />
                      </button>
                      {product.wishlistPopup && <span className="cart-popup">{product.wishlistPopup}</span>}
                    </div>

                        {/* Compare */}
              <div className="btn-wrapper">
                      <button
                        className="product-btn"
                        onClick={() => this.handleAddToCompare(product)}
                      >
                        <i className="fa fa-exchange" />
                      </button>
                      {product.comparePopup && <span className="cart-popup">{product.comparePopup}</span>}
                    </div>

            
                        {/* Cart */}
                        <div className="btn-wrapper">
                          <button
                            className="product-btn"
                            onClick={() => this.handleAddToCart(product)}
                          >
                            <i className="fa fa-shopping-cart" />
                          </button>
                          {product.addedCart && <span className="cart-popup">{product.addedCart}</span>}
                        </div>

                      </div>

                  </div>

                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
}

// HOC для прокидывания контекста
const NewProductsWithContext = (props) => {
  const { wishlist, toggleWishlist } = useWishlist();
  return <NewProducts {...props} wishlist={wishlist} toggleWishlist={toggleWishlist} />;
};

export default NewProductsWithContext;
