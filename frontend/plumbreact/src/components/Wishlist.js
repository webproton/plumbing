import React, { useEffect, useState } from "react";
import ProductsService from "../services/ProductService";
import { Link } from "react-router-dom";
import { addToCart } from "../utils/cartUtils";
import { useWishlist } from "../context/WishlistContext";
import { toggleCompareItem } from "../utils/compare"; // импортируем compare

const service = new ProductsService();

const Wishlist = () => {
  const [isLoading, setIsLoading] = useState(true);
  const { wishlist, toggleWishlist, clearWishlist } = useWishlist();
  const [footerHeight, setFooterHeight] = useState(0);

  useEffect(() => {
    setIsLoading(false);
  }, [wishlist]);

  useEffect(() => {
    const footer = document.querySelector("footer");
    if (!footer) return setFooterHeight(0);

    const update = () => setFooterHeight(footer.offsetHeight || 0);

    update();

    let ro;
    if (window.ResizeObserver) {
      ro = new ResizeObserver(update);
      ro.observe(footer);
    } else {
      window.addEventListener("resize", update);
    }

    const prevPadding = document.body.style.paddingBottom || "";
    document.body.style.paddingBottom = `${footer.offsetHeight + 16}px`;

    const applyPadding = () =>
      (document.body.style.paddingBottom = `${footer.offsetHeight + 16}px`);
    window.addEventListener("resize", applyPadding);

    return () => {
      if (ro) ro.disconnect();
      else window.removeEventListener("resize", update);
      window.removeEventListener("resize", applyPadding);
      document.body.style.paddingBottom = prevPadding;
    };
  }, []);

  if (isLoading) return <p>Загрузка избранного...</p>;
  if (wishlist.length === 0) return <p>Wishlist is empty</p>;

  return (
<div className="wishlist-page">
  <div className="wishlist-clear-btn-container">
    <button
      onClick={clearWishlist}
      className="wishlist-clear-btn"
      disabled={wishlist.length === 0}
      title="Удалить все избранные"
    >
      Удалить все избранные
    </button>
  </div>

  <div className="wishlist-grid">
    {wishlist.map((item) => {
      const variant = item.product_variant;
      return (
        <div className="product-card" key={variant.id}>
          <div className="product-img">
            <Link
              to={`/products/${variant.product.slug}/variant/${variant.slug}`}
            >
              <img
                src={variant.product_photo || variant.photo || ""}
                alt={variant.product_name || variant.name || "Product image"}
              />
            </Link>
          </div>
          <div className="product-body">
            <h4 className="product-name">
              <Link
                to={`/products/${variant.product.slug}/variant/${variant.slug}`}
              >
                {variant.product_name}
              </Link>
            </h4>
            <p className="product-price">${variant.price}</p>
<div className="product-btns">
  <button
    className="icon-btn"
    onClick={() => toggleWishlist(variant.id)}
  >
    <i className="fa fa-heart" />
  </button>

  <button
    className="icon-btn"
    onClick={() =>
      toggleCompareItem({
        id: variant.product.id,
        slug: variant.product.slug,
        name: variant.product_name,
        price: variant.price,
        photo: variant.product_photo || variant.photo,
        first_variant: variant,
      })
    }
  >
    <i className="fa fa-exchange" />
  </button>

  <button
    className="icon-btn"
    onClick={() => addToCart(item)}
  >
    <i className="fa fa-shopping-cart" />
  </button>
</div>

          </div>
        </div>
      );
    })}
  </div>
</div>

  );
};

export default Wishlist;
