import React, { Component } from "react";
import { Link } from "react-router-dom";
import ProductsService from "../services/ProductService";
import CategoryNameLinkToProducts from "./CategoryNameLinkToProducts";
import { FaHome, FaThList, FaTruck, FaClipboardList } from "react-icons/fa";






class Navigation extends Component {
  constructor(props) {
    super(props);
    this.state = {
      categories: [],
      loaded: false,
      placeholder: "Loading",
      isOpen: false,
      isMobile: window.innerWidth < 768, // состояние для мобильного режима
    };
    this.productsService = new ProductsService();
    this.toggleMenu = this.toggleMenu.bind(this);
    this.handleResize = this.handleResize.bind(this);
    this.handleClickOutside = this.handleClickOutside.bind(this);
    this.menuRef = React.createRef();
  }

  componentDidMount() {
    this.productsService.getCategory()
      .then((data) => this.setState({ categories: data, loaded: true }))
      .catch(() => this.setState({ placeholder: "Something went wrong!", loaded: true }));

    document.addEventListener("click", this.handleClickOutside);
    window.addEventListener("resize", this.handleResize);
  }

  componentWillUnmount() {
    document.removeEventListener("click", this.handleClickOutside);
    window.removeEventListener("resize", this.handleResize);
  }

  handleResize() {
    const isMobile = window.innerWidth < 768;
    if (isMobile !== this.state.isMobile) {
      this.setState({ isMobile });
    }
  }

  toggleMenu() {
    this.setState((prevState) => ({ isOpen: !prevState.isOpen }));
  }

  handleClickOutside(event) {
    if (
      this.state.isOpen &&
      this.menuRef.current &&
      !this.menuRef.current.contains(event.target) &&
      !event.target.closest(".menu-toggle")
    ) {
      this.setState({ isOpen: false });
    }
  }

  render() {
    const { categories, loaded, placeholder, isOpen, isMobile } = this.state;
    const categoriesFromProps = this.props.categories || categories;
    const { isAuthenticated } = this.props; // Получаем пропс, например

    if (!loaded) {
      return <div>{placeholder}</div>;
    }
    return (
      <nav id="navigation">
        <div className="container">
          <div className="header-ctn">
            <div className="menu-toggle" onClick={this.toggleMenu}>
              <i className="fa fa-bars"></i>
              <span>Меню</span>
            </div>
          </div>

          <div id="responsive-nav" className={isOpen ? "active" : ""} ref={this.menuRef}>
 <ul className="main-nav nav navbar-nav">
  {/* На мобильных скрываем Главная, Заказы и возвраты и Доставка */}
  {!isMobile && (
    <>
      <li className="active">
        <Link to="/">
          <FaHome style={{ marginRight: "6px", color: "#ff5722" }} />
          Главная
        </Link>
      </li>
      <li>
        <Link to="/?page=orders-returns">
          <FaClipboardList style={{ marginRight: "6px", color: "#4caf50" }} />
          Заказы и возвраты
        </Link>
      </li>
      <li>
        <Link to="/?page=delivery">
          <FaTruck style={{ marginRight: "6px", color: "#9c27b0" }} />
          Доставка
        </Link>
      </li>
    </>
  )}

  {/* Категории всегда видимы */}
  <li>
    <Link to="/category">
      <FaThList style={{ marginRight: "6px", color: "#2196f3" }} />
      Категории
    </Link>
  </li>
</ul>


            {/* --- Блок информации — показываем всегда в мобильном меню --- */}
            <div className="sidebar-section sidebar-info-section" style={{ padding: '15px', color: '#fff' }}>
              <CategoryNameLinkToProducts categories={categoriesFromProps} />

              <div className="info-blocks" style={{ marginTop: '15px' }}>
                <div className="info-block" style={{ marginBottom: '10px' }}>
                  <h4>Мы в Telegram</h4>
                  <p>
                    Подписывайтесь на наш{' '}
                    <a href="https://t.me/your_channel" target="_blank" rel="noreferrer" style={{ color: '#00bfff' }}>
                      Telegram-канал
                    </a>{' '}
                    для акций и новостей!
                  </p>
                </div>

                <div className="info-block" style={{ marginBottom: '10px' }}>
                  <h4>Наш адрес</h4>
                  <p>г. Х, ул. Примерная, 10</p>
                  <p>Пн-Пт: 9:00 - 18:00</p>
                  <p>Сб-Вс: выходной</p>
                </div>

                <div className="info-block">
                  <h4>Связаться с нами</h4>
                  <p>+3хххххххххххх</p>
                  <p>info@example.com</p>
                </div>
              </div>

              {/* --- Если аноним — показываем Логин и Регистрацию --- */}
              {!isAuthenticated && (
                <div className="auth-links" style={{ marginTop: '20px' }}>
                  <Link to="/login" style={{ color: '#00bfff', display: 'block', marginBottom: '10px' }}>Войти</Link>
                  <Link to="/register" style={{ color: '#00bfff', display: 'block' }}>Регистрация</Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>
    );
  }
}


export default Navigation;
