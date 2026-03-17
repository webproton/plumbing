import React, {Component} from "react";
import ProductsService from "../services/ProductService";
import { Link } from 'react-router-dom';
import Navigation from "./Navigation";
import { toggleCompareItem } from '../utils/compare';
import { addToCart, syncCart } from "../utils/cartUtils";
import { Helmet } from "react-helmet";
import Slider from "react-slick";

import { WishlistContext, WishlistProvider, useWishlist } from '../context/WishlistContext';


class ProductDetail extends Component {
  // This component not finished

  static contextType = WishlistContext;

  constructor (props) {
	super(props);
	this.state = {
		data: {},
    product: null,
		loaded: false,
		placeholder: "Loading",
		productSlug:  "",
		categoryData: {},
		currentPhotoIndex: 0,
		activeTab: "Description", // Add activeTab state
    quantity: 1, // Количество товара
    selectedVariant: null, // Добавим новое состояние для выбранного варианта
    // wishlist: JSON.parse(localStorage.getItem("wishlist")) || [],

    isDesktop: window.innerWidth > 768,
        addedCart: null,
      addedWishlist: null,
      addedCompare: null,
		

	};
	this.productsService = new ProductsService();

  }

componentDidMount() {
  const { productSlug, variantSlug } = this.props.match.params;
  window.addEventListener("storage",  this.syncCart);
  window.addEventListener("resize", this.handleResize);

  // Запрос данных продукта
  this.fetchProductDetails(productSlug, variantSlug);

  // Добавляем обработчик wheel для контейнера миниатюр
  const container = document.querySelector('#product-imgs');
  if (container) {
    container.addEventListener('wheel', this.handleWheel, { passive: false });
  }
}

 componentDidUpdate(prevProps) {
  const { productSlug, variantSlug } = this.props.match.params;
  if (
    prevProps.match.params.productSlug !== productSlug ||
    prevProps.match.params.variantSlug !== variantSlug
  ) {
    this.fetchProductDetails(productSlug, variantSlug);
  }
}

componentWillUnmount() {
  window.removeEventListener("storage", this.syncCart);
  // window.removeEventListener("storage", this.syncWishlist);
    window.removeEventListener("resize", this.handleResize);

  const container = document.querySelector('#product-imgs');
  if (container) {
    container.removeEventListener('wheel', this.handleWheel);
  }
}

handleResize = () => {
  this.setState({ isDesktop: window.innerWidth > 768});
}

handleWheel = (e) => {
  e.preventDefault();
  if (!this.thumbSlider) return;
  if (e.deltaY > 0) {
    this.thumbSlider.slickNext();
  } else {
    this.thumbSlider.slickPrev();
  }
};


// Функция для изменения выбранного варианта
handleVariantChange = (variantSlug) => {
  const { product } = this.state;
  const variant = product.variants.find(v => v.id.toString() === variantSlug.toString());
  if (variant) {
    this.setState(
      { 
        selectedVariant: variant,
        currentPhotoIndex: 0, // Сбрасываем индекс при смене варианта
      },
      () => {
        // После обновления state принудительно переключаем слайдер
        if (this.mainSlider) {
          this.mainSlider.slickGoTo(0);
        }
      }
    );

    // Также меняем URL, если надо
    this.props.history.replace(`/products/${product.slug}/variant/${variant.slug}`);
  }
};



  // Функция для загрузки данных продукта
  fetchProductDetails(productSlug, variantSlug) {
    this.productsService.getProduct(productSlug)
      .then(data => {
        // Если variantSlug передан в URL, ищем соответствующий вариант, иначе берем первый
        // const selectedVariant = data.variants.find(variant => variant.id === Number(variantSlug)) || data.variants[0];
        const selectedVariant = data.variants.find(v => v.slug === variantSlug) || data.variants[0];
        
        this.setState({
          product: data,
          loaded: true,
          selectedVariant, // Сохраняем выбранный вариант в state
          currentPhotoIndex: 0, // Сбрасываем индекс при загрузке нового варианта
          }, () => {
        // уведомляем react-snap, что данные загружены
        if (window.snapSaveState) window.snapSaveState();
        });
        
        return this.productsService.getCategoryBySlug(data.category.slug);
      })
      .then(categoryData => {
        this.setState({ categoryData });
      })
      .catch(error => {
        console.log('Error fetching product details:', error);
        this.setState({ placeholder: 'Something went wrong!' });
      });
  }


handleThumbnailClick = (index) => {
  this.setState({ currentPhotoIndex: index }, () => {
    if (this.mainSlider) {
      this.mainSlider.slickGoTo(index); // обновляем главное изображение после обновления state
    }
  });
};

    // Function to handle tab change
	handleTabChange = (tabName) => {
		this.setState({
		  activeTab: tabName
		});
	  };


  // syncWishlist = () => syncWishlist(wishlist => this.setState({ wishlist }), this.context.user);

  
  syncCart = () => syncCart(this); // Используем утилиту

  // Увеличение количества
  increaseQuantity = () => {
    this.setState((prevState) => ({
      quantity: prevState.quantity + 1,
    }));
  };

  // Уменьшение количества
  decreaseQuantity = () => {
    this.setState((prevState) => ({
      quantity: Math.max(1, prevState.quantity - 1),
    }));
  };






handleAddToCart = () => {
  const { product, quantity, selectedVariant } = this.state;
  if (!product || !selectedVariant) return;

  const variantId = selectedVariant.id;

  // Получаем текущее количество в корзине
  const cart = JSON.parse(localStorage.getItem("cart") || "{}");
  const currentCount = cart[variantId] || 0;

  // Добавляем товар в корзину через утилиту
  addToCart({ ...product, selectedVariant }, quantity);

  // Определяем текст popup
  let message;
  if (currentCount === 0 && quantity === 1) {
    message = "Добавлено";
  } else {
    message = `+${quantity}`;
  }

  // Показываем popup
  this.showPopup("addedCart", true, message);
};


  handleToggleWishlist = () => {
    const { product, selectedVariant } = this.state;
    const variant = selectedVariant || product?.variants?.[0];
    if (!variant) return;

    const { toggleWishlist, wishlist } = this.context;
    const isInWishlist = wishlist.some(w => w.product_variant.id === variant.id);

    toggleWishlist(variant);
    this.showPopup("addedWishlist", !isInWishlist);
  };

  handleCompare = () => {
    const { product, selectedVariant } = this.state;
    if (!product || !selectedVariant) return;

    const added = toggleCompareItem({
      id: product.id,
      name: product.name,
      price: selectedVariant.price,
      photo: selectedVariant.photo || product.photo,
      first_variant: selectedVariant,
    });
    this.showPopup("addedCompare", added);
  };

  // Универсальный метод показа попапа
  showPopup = (key, added = true, customText) => {
    const popupTextMap = {
      addedCart: customText || "Добавлено",
      addedWishlist: added ? "В избранное" : "Удалено из избранного",
      addedCompare: added ? "В сравнении" : "Удалено из сравнения",
    };

    this.setState({ [key]: popupTextMap[key] });

    setTimeout(() => this.setState({ [key]: null }), 2000);
  };

    // Обработчик изменения количества вручную
  handleQuantityChange = (event) => {
    const value = parseInt(event.target.value, 10);
    this.setState({
      quantity: isNaN(value) || value < 1 ? 1 : value,
    });
  };

getSlickSettings = () => {
    const photosLength = this.state.photos?.length || 4; // Для десктопа, если photos не в state
    return {
      dots: false,
      infinite: false, // Отключаем для десктопа, чтобы не дублировать
      speed: 500,
      slidesToShow: 4, // Вернули фиксированное значение, так как photosLength недоступен
      slidesToScroll: 1,
      vertical: false,
      verticalSwiping: false,
        arrows: true,
      responsive: [
        {
          breakpoint: 768,
          settings: {
            slidesToShow: 3,
            slidesToScroll: 1,
            vertical: false,
            verticalSwiping: false,
            infinite: true, // Включаем бесконечную прокрутку
            centerMode: false, // Отключаем центрирование
            variableWidth: false, // Фиксированная ширина слайдов
          },
        },
        {
          breakpoint: 576,
          settings: {
            slidesToShow: 2,
            slidesToScroll: 1,
            vertical: false,
            verticalSwiping: false,
            infinite: true,
            centerMode: false,
            variableWidth: false,
          },
        },
      ],
    };
  };

  render(){
	const {product, data, loaded, categoryData, placeholder ,activeTab, quantity ,selectedVariant, currentPhotoIndex ,addedCart, addedWishlist, addedCompare} = this.state;
const { wishlist } = this.context;


	if (!loaded) {
	  return <div>{placeholder}</div>;  
	} 

  const photos = [];
  const photoUrls = new Set();


    if (selectedVariant?.photo) {
      photos.push({ photo: selectedVariant.photo });
    }
    if (product?.photos && product.photos.length > 0) {
      photos.push(...product.photos);
    }
    if (selectedVariant?.photos_variant && selectedVariant.photos_variant.length > 0) {
      photos.push(...selectedVariant.photos_variant);
    }
 
  // Если фотографий нет, используем заглушку
  const defaultPhoto = 'defaultPhotoUrl';
  const seoTitle = product ? `${product.name} – Купить мебель онлайн в России` : 'Product';

  const seoDescription = product
    ? `Купить ${product.name} от ${selectedVariant?.brand?.name || 'лучших производителей'}. 
       Доставка по России. Лучшие цены, скидки и акции на мебель.`
    : 'Product description';
  const seoImage = selectedVariant?.photo || product?.photos[0]?.photo || 'https://example.com/default-product.jpg';


  const isInWishlist = wishlist.some(item => item.product_variant?.id === selectedVariant?.id);


  // Если фотографий нет, используем заглушку
    if (photos.length === 0) {
      photos.push({ photo: defaultPhoto, id: "default" });
    }

  
   return (
      <>

            <Helmet>
        <title>{seoTitle}</title>
        <meta name="description" content={seoDescription} />
        <meta property="og:title" content={seoTitle} />
        <meta property="og:description" content={seoDescription} />
        <meta property="og:image" content={seoImage} />
      </Helmet>
        {/* <!-- NAVIGATION --> */}
        <Navigation />
        {/* <!-- /NAVIGATION --> */}

        {/* <!-- BREADCRUMB --> */}
        <div id="breadcrumb" className="section">
          {/* <!-- container --> */}
          <div className="container">
            {/* <!-- row --> */}
            <div className="row">
              <div className="col-md-12">
                <ul className="breadcrumb-tree">
                  <li><Link to="/">Главная</Link></li>
                  <li><Link to="/category/">Все категории</Link></li>
                  <li><Link to={`/products?category=${product.category.slug}`}>{categoryData.name}</Link></li>
                  <li><Link to={`/products/${product.slug}`}>{product.name}</Link></li>
                  <li className="active">{data.name}</li>
                </ul>
              </div>
            </div>
            {/* <!-- /row --> */}
          </div>
          {/* <!-- /container --> */}
        </div>
        {/* <!-- /BREADCRUMB --> */}

        <div className="section">
          <div className="container">
            <div className="row">
              {/* Product main img */}
        <div className="col-md-5 col-md-push-2">
  <div id="product-main-img">
<Slider
  ref={(slider) => (this.mainSlider = slider)}>
      {photos.map((photo, index) => (
        <div key={index} className="product-preview">
          <img
            src={photo.photo}
            alt={`Product Image ${index + 1}`}
            loading="lazy"
          />
        </div>
      ))}
    </Slider>
  </div>
</div>
                {/* <!-- /Product main img --> */}
                    {/* Product thumb imgs */}
<div className={this.state.isDesktop ? "col-md-2 col-md-pull-5" : "col-md-2"}>
  {this.state.isDesktop ? (
    /* Десктоп: обычный scroll */
    <div id="product-imgs">
      {photos.map((photo, index) => (
        <div
          className={`product-preview ${index === currentPhotoIndex ? "selected" : ""}`}
          key={index}
          onClick={() => this.handleThumbnailClick(index)}
        >
          <img 
          src={photo.photo}
          
           alt={`Product Thumbnail ${index + 1}`} loading="lazy" />
        </div>
      ))}
    </div>
  ) : (
    /* Мобильные: Slick слайдер */
    <div id="product-imgs">
      <Slider
        ref={(slider) => (this.thumbSlider = slider)}
        {...this.getSlickSettings()}
      >
        {photos.map((photo, index) => (
          <div
            className={`product-preview ${index === currentPhotoIndex ? "selected" : ""}`}
            key={index}
            onClick={() => this.handleThumbnailClick(index)}
          >
            <img 
            
            src={photo.photo}
            
            alt={`Product Thumbnail ${index + 1}`} loading="lazy" />
          </div>
        ))}
      </Slider>
    </div>
  )}
</div>

{/* Product details */}
<div className="col-md-5">
  <div className="product-details" key={product.id}>
    <h2 className="product-name">{product.name}</h2>

    {/* Варианты продукта в виде миниатюр */}
    {product.variants.length > 1 && (
      <div className="variant-thumbnails">
        <strong className="variant-thumbnails-label">Доступные варианты:</strong>
        <div className="variant-thumbnails-list">
          {product.variants.map((variant) => (
            <button
              key={variant.id}
              onClick={() => this.handleVariantChange(variant.id)}
              className={`variant-thumb-btn ${selectedVariant?.id === variant.id ? 'selected' : ''}`}
            >
              <img
                // src={`${config.apiUrl}${variant.product_photo || variant.photo || ""}`}
                src={`${variant.product_photo || variant.photo || ""}`}
                alt="Variant"
                className="variant-thumb-img"
                loading="lazy"
              />
            </button>
          ))}

        </div>
      </div>
    )}
        {/* Секция с кодами всех вариантов */}
    {/* Код выбранного варианта */}
    {selectedVariant && (
      <div className="selected-variant-code">
        <strong>Код выбранного варианта:</strong> {selectedVariant.code}
      </div>
    )}




    <div>
      <h3 className="product-price">
        {selectedVariant ? selectedVariant.price : product.variants[0].price}
        <span className="currency-icon">₴</span>
        <del className="product-old-price">
          {selectedVariant ? selectedVariant.oldPrice : product.variants[0].oldPrice}
        </del>
      </h3>
    </div>

    <p>{product.description}</p>

    {/* Опции продукта */}
    {product.variants.some(v => v.thread_size || v.product_thread || (v.color_options && v.color_options.length > 0)) && (
      <div className="product-options-row">
        {product.variants.some(v => v.thread_size) && (
          <div className="product-option">
            <label>Size</label>
            <select
              className="input-select"
              value={selectedVariant?.id}
              onChange={(e) => this.handleVariantChange(e.target.value)}
            >
              {product.variants.filter(v => v.thread_size).map(v => (
                <option key={v.id} value={v.id}>{v.thread_size.inches}</option>
              ))}
            </select>
          </div>
        )}

        {product.variants.some(v => v.product_thread) && (
          <div className="product-option">
            <label>Type of thread</label>
            <select
              className="input-select"
              value={selectedVariant?.id}
              onChange={(e) => this.handleVariantChange(e.target.value)}
            >
              {product.variants.filter(v => v.product_thread).map(v => (
                <option key={v.id} value={v.id}>{v.product_thread.thread_type}</option>
              ))}
            </select>
          </div>
        )}

        {product.variants.some(v => v.color) && (
          <div className="product-option">
            <label>Цвет</label>
                <p style={{ fontSize: '14px', color: '#555', margin: '4px 0 0' }}>
               Цвет на выбор — уточняйте у менеджера
              </p>
            {/* <select
              className="input-select"
              value={selectedVariant?.id || product.variants[0].id}
              onChange={(e) => this.handleVariantChange(e.target.value)}
            >
              {product.variants.filter(v => v.color).map(v => (
                <option key={v.id} value={v.id}>{v.color?.name || 'Без цвета'}</option>
              ))}
            </select> */}
          </div>
        )}
      </div>
    )}


              {/* Количество + корзина */}
              <div className="add-to-cart">
                <div className="add-to-cart-row">
                  <div className="qty-label">
                    <label>Количество:</label>
                    <div className="input-number">
                      <input
                        type="number"
                        value={quantity}
                        onChange={this.handleQuantityChange}
                        min="1"
                      />
                      <span className="qty-up" onClick={this.increaseQuantity}>+</span>
                      <span className="qty-down" onClick={this.decreaseQuantity}>-</span>
                    </div>
                  </div>

                  <div className="add-to-cart-btn-wrapper" style={{ position: 'relative', display: 'inline-block' }}>
                    <button
                      className="add-to-cart-btn"
                      onClick={this.handleAddToCart}
                    >
                      <i className="fa fa-shopping-cart"></i> В корзину
                    </button>

                    {addedCart && (
                      <div className="popup" style={{ position: 'absolute', top: '-30px', left: '50%', transform: 'translateX(-50%)' }}>
                        {addedCart}
                      </div>
                    )}
                  </div>
                </div>
              </div>

    {/* Wishlist и Compare */}
    <div className="product-btns">
      <li>
        <button
          className="wishlist-btn"
          onClick={this.handleToggleWishlist}
        >
          <i className={`fa ${isInWishlist ? "fa-heart" : "fa-heart-o"}`} style={{ marginRight: "5px" }} />
          В избранное
        </button>
        {this.state.addedWishlist && <div className="popup">{this.state.addedWishlist}</div>}
      </li>

      <li>
        <button
          className="compare-btn"
          onClick={this.handleCompare}
        >
          <i className="fa fa-exchange" style={{ marginRight: "5px" }} />
          Сравнить
        </button>
        {this.state.addedCompare && <div className="popup">{this.state.addedCompare}</div>}
      </li>
    </div>

    {/* Категория */}
    <ul className="product-links">
      <li>Категория:</li>
      <li><Link to={`/products?category=${product.category.slug}`}>{this.state.categoryData.name}</Link></li>
    </ul>
  </div>
</div>

              {/* <!-- /Product details --> */}
            </div>

            {/* Product tab */}

              <div id="product-tab">
                {/* Product tab nav */}
                <ul className="tab-nav">
                  <li className={activeTab === "Description" ? "active" : ""}>
                    <a onClick={() => this.handleTabChange("Description")}>Описание</a>
                  </li>
                  <li className={activeTab === "Details" ? "active" : ""}>
                    <a onClick={() => this.handleTabChange("Details")}>Подробности</a>
                  </li>
           
                </ul>

                {/* Product tab content */}
                <div className="tab-content">
                  <div id="tab1" className={"tab-pane fade" + (activeTab === "Description" ? " in active" : "")}>
                    <div className="row">
                      <div className="col-md-12">
                        <p>{selectedVariant?.description || product.description}</p>
                      </div>
                    </div>
                  </div>

                  <div id="tab2" className={"tab-pane fade" + (activeTab === "Details" ? " in active" : "")}>
                    <div className="row">
                      <div className="col-md-12">
                        {/* Details content */}
                        <table className="table">
                          <tbody>
  {[
    { label: 'Шар', value: selectedVariant?.ball?.ball_material_type?.name },
    // { label: 'Бренд', value: selectedVariant?.brand?.name },
    { label: 'ID товара', value: product?.id },
    { label: 'Код варианта (SKU)', value: selectedVariant?.id },
    { label: 'Производитель', value: selectedVariant?.manufacturer?.country },
    { label: 'Материал', value: selectedVariant?.material?.name },
    { label: 'Ширина', value: selectedVariant?.dimensions_width, unit: 'мм' },
    { label: 'Высота', value: selectedVariant?.dimensions_height, unit: 'мм' },
    { label: 'Вес', value: selectedVariant?.dimensions_weight, unit: 'г' },
    { label: 'Глубина', value: selectedVariant?.dimensions_depth, unit: 'мм' },
    { label: 'Цвет', value: selectedVariant?.color?.name },
    { label: 'Варианты цвета', value: selectedVariant?.color_options?.name },
    { label: 'Основание матраса', value: selectedVariant?.mattress_base?.name },
    { label: 'Материалы обивки', value: selectedVariant?.upholstery_materials?.name },
    { label: 'Подлокотники', value: selectedVariant?.armrests?.name },
    { label: 'Высота сиденья', value: selectedVariant?.seat_height, unit: 'мм' },
    { label: 'Глубина сиденья', value: selectedVariant?.seat_depth, unit: 'мм' },
    { label: 'Спальных мест', value: selectedVariant?.sleeping_places },
    { label: 'Ширина спального места', value: selectedVariant?.bed_width, unit: 'мм' },
    { label: 'Длина спального места', value: selectedVariant?.bed_length, unit: 'мм' },
    { 
      label: 'Доступен нестандартный размер', 
      value: selectedVariant?.custom_size_available != null 
        ? selectedVariant.custom_size_available ? 'Да' : 'Нет' 
        : null 
    },
    { label: 'Тип товара', value: selectedVariant?.type_of_product?.name },
    { label: 'Особенности', value: selectedVariant?.features },
    { label: 'Наполнение', value: selectedVariant?.filling?.name },
    { label: 'Форма', value: selectedVariant?.bed_type_form?.name },
    { 
      label: 'Тип кровати', 
      value: product.category?.name === 'Кровати' ? (selectedVariant?.bed_type?.name || 'Не указано') : null 
    },
    { label: 'Узор', value: selectedVariant?.pattern?.name },
    { label: 'Материал корпуса', value: selectedVariant?.body_material?.name },
    { label: 'Комплектация', value: selectedVariant?.included_items?.name },
  ]
                            .filter(attr => attr.value != null && attr.value !== '') // <-- фильтр null/undefined/пустых строк
                            .map(({ label, value, unit }) => value && (
                              <tr key={label}>
                                <td>{label}</td>
                                <td>{value}{unit ? ` ${unit}` : ''}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>

                      
                      </div>
                    </div>
                  </div>

                  <div id="tab3" className={"tab-pane fade" + (activeTab === "Reviews" ? " in active" : "")}>
                    <div className="row">
                      <div className="col-md-12">
                        {/* Reviews content */}
                        <p>Reviews will be here.</p>
                      </div>
                    </div>
                    
                  </div>
                </div>
              </div>
          </div>
        </div>
        {/* <!-- /SECTION --> */}
      </>
    );
  }
}


export default ProductDetail;
