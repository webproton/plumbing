import React, { Component } from "react";
import { Link } from "react-router-dom";
import ProductsService from "../services/ProductService";
import CategoryNameLinkToProducts from "./CategoryNameLinkToProducts";
import Navigation from "./Navigation";
import NewProducts from "./NewProducts";
import HomeHelmet from "./HomeHelmet"; // импортируем новый компонент
import { useLocation } from "react-router-dom";
import OrdersReturns from "../pages/OrdersReturns"; // путь к компоненту
import Delivery from "../pages/Delivery"; // путь к компоненту
import AboutCompany from "../pages/AboutCompany";
import Contacts from "../pages/Contacts";
import HomeBanner from "../components/HomeBanner";
import { getSiteSettings } from "../services/siteSettingsService";
import { FaTelegramPlane, FaPhone, FaEnvelope, FaClock ,FaCalendarAlt} from "react-icons/fa";



function useQuery() {
  return new URLSearchParams(useLocation().search);
}

class Home extends Component {
  constructor(props) {
    super(props);
    this.state = {
      products_data: [],
      categories: [],
      loaded: false,
      placeholder: "Loading...",
      isMobile: window.innerWidth < 768,
      isSidebarOpen: false, // 👈 sidebar toggle
        siteSettings: null, // 👈 новые данные
    };
    this.productsService = new ProductsService();
  }

  componentDidMount() {
    Promise.all([
      this.productsService.getCategory(),
      this.productsService.getProducts(),
      getSiteSettings(), // 👈 добавили
    ])
      .then(([categories, products_data, siteSettings]) => {
        const productsArray = products_data.results || [];
        this.setState({
          categories,
          products_data:  productsArray,
          siteSettings, // 👈 сохранили
          loaded: true,
        });
      })
      .catch((error) => {
        console.error("Error fetching data:", error);
        this.setState({
          placeholder: "Something went wrong!",
          loaded: true,
        });
      });
    window.addEventListener("resize", this.handleResize);


  }


componentWillUnmount() {
    window.removeEventListener("resize", this.handleResize);
  }

  handleResize = () => {
    const isMobile = window.innerWidth < 768;
    if (isMobile !== this.state.isMobile) {
      this.setState({ isMobile });
      if (isMobile) {
        this.setState({ isSidebarOpen: false }); // при переходе на мобилку — закрываем сайдбар
      }
    }
  };
  toggleSidebar = () => {
    this.setState((prevState) => ({
      isSidebarOpen: !prevState.isSidebarOpen,
    }));
  };

  render() {

    const { products_data, categories, loaded, placeholder,siteSettings, isSidebarOpen, isMobile  } = this.state;
    const query = new URLSearchParams(this.props.location.search);
    const page = query.get("page"); // тут будет "orders-returns" или null

    if (!loaded) {
      return <div>{placeholder}</div>;
    }


      // Берем категории для рендеринга
  let visibleCategories = categories.filter(cat => [10, 19, 13, 17, 6, 14].includes(cat.id));

  if (window.innerWidth < 1500) {
    // Если экран меньше 1400px, убираем последнюю категорию
    visibleCategories = visibleCategories.slice(0, 5);
  }
    return (
      <>

                  {/* Добавляем Helmet */}
        <HomeHelmet categories={categories} />

        <Navigation categories={categories} />

        {/* Shop Collection Section */}
    <section className="shop-collection-section">
      <div className="shop-collection-wrapper">
        {visibleCategories.map(cat => (
          <div key={cat.id} className="category-card">
            <Link to={`/products/?category=${cat.slug}`} className="shop-img-link">
              <div className="shop-img">
                <img src={cat.photo} alt={cat.name} />
              </div>
            </Link>
            <div className="shop-body">
              <Link to={`/products/?category=${cat.slug}`} className="cta-btn">
                <h3>{cat.name}</h3>
              </Link>
            </div>
          </div>
        ))}
      </div>
    </section>

        {/* Main Content Section */}
        <section className="main-content-section">
          <div className="main-content-wrapper">
            {/* Sidebar */}
            <aside className="sidebar with-side-margin">
              <div className="sidebar-section sidebar-info-section">
                {/* Заголовок с кнопкой-сворачивалкой */}
                <div className="sidebar-toggle-header" onClick={isMobile ? this.toggleSidebar : undefined} style={{ cursor: isMobile ? 'pointer' : 'default' }}>
                  <h3>Информация</h3>
                  {isMobile && <span>{isSidebarOpen ? "▲" : "▼"}</span>}
                </div>

                {/* Вложенный контент */}
                {(isMobile && isSidebarOpen) || !isMobile ? (
                  <div className="sidebar-info-content open">
                    <CategoryNameLinkToProducts categories={categories} />
                    <div className="info-blocks">

                        <div className="info-block">
                          <h4>Мы в Telegram</h4>
                          <p>
                            Подписывайтесь на наш Telegram-канал для акций и новостей!
                            <br />
                            <a
                              href={this.state.siteSettings?.telegram || "#"}
                              target="_blank"
                              rel="noreferrer"
                              className="info-link"
                            >
                              <FaTelegramPlane size={16} />
                              @{this.state.siteSettings?.telegram?.split("/").pop()}
                            </a>
                          </p>
                        </div>

<div className="info-block">
  <h4>Работаем</h4>
  <div className="icon-text-block">
    <div className="icon-text">
      <FaClock size={16} style={{ marginRight: 6 }} />
      <span style={{ color: "#ff6600" }}>Пн-Пт: 9:00 - 18:00</span>
    </div>
    <div className="icon-text">
      <FaCalendarAlt size={16} style={{ marginRight: 6 }} />
      <span style={{ color: "#ff6600" }}>Сб-Вс: выходной</span>
    </div>
  </div>
</div>

<div className="info-block">
  <h4>Связаться с нами</h4>
  <div className="icon-text-block">
    <div className="icon-text">
      <FaPhone size={16} style={{ marginRight: 6 }} />
      <span style={{ color: "#28a745" }}>
        {this.state.siteSettings?.phone || "+38 (050) 999-99-99"}
      </span>
    </div>
    <div className="icon-text">
      <FaEnvelope size={16} style={{ marginRight: 6 }} />
      <span style={{ color: "#28a745" }}>
        {this.state.siteSettings?.email || "luxora@mail.com"}
      </span>
    </div>
  </div>
</div>

                      
                    </div>
                  </div>
                ) : null}
              </div>
            </aside>

            {/* Main Content Area */}
            <main className="main-content-area">

                {page === "orders-returns" ?  (
                    <OrdersReturns />
                ) : page === "delivery" ? (
                  <Delivery />
                ) : page === "about-company" ? (
                  <AboutCompany />
                  ) : page === "contacts" ? (
                    <Contacts />
              ) : (
                <>
              {/* <div className="carousel-container">
                {console.log(products_data,'<<<<products_dataproducts_data')}
                {products_data.length > 0 ? (
                  <Carousel products={products_data} onProductClick={this.handleProductClick} />
                ) : (
                  <div>No products available</div>
                )}
              </div> */}

              {/* Новый React BannerSlider */}

                   
            <div className="banner-slider-wrapper">
              <HomeBanner />
              {/* <BannerSlider
              
              
                slides={products_data
                  .filter(product => product.banner_url) // берем только продукты с баннером
                  .slice(0, 3) // максимум 3 слайда
                  .map(product => ({

                    title: product.name,
                    subtitle: `${product.price} ₴`,
                    // img: `${serverUrl}${product.banner_url}`, // добавляем серверный адрес
                    img: product.banner_url,
                    link: `/products/${product.slug}/variant/${product.first_variant?.slug}`,
                  }))
                  
                }
                autoPlay={true}
                autoPlayTime={4000}
              /> */}
            </div>

              {/* New Products Below Carousel */}
              <div className="new-products-wrapper">
                <NewProducts />
              </div>
              </>
              )}
            </main>
          </div>
        </section>
      </>
    );
  }
}

export default Home;