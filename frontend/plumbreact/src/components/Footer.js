
import React, { Component } from "react";
import { Link } from "react-router-dom";

import ProductsService from "../services/ProductService";
import { getSiteSettings } from "../services/siteSettingsService"; // импортируем сервис

class Footer extends Component {

    constructor(props) {
    super(props);
    this.state = {
      categories: [],
      loading: true,
      error: null,
            siteSettings: null, // <- добавляем сюда
    };
    this.productsService = new ProductsService();
  }

  async componentDidMount() {
    try {
      const categories = await this.productsService.getCategory();
      this.setState({ categories, loading: false });
    } catch (error) {
      console.error("Ошибка загрузки категорий:", error);
      this.setState({ loading: false, error: "Не удалось загрузить категории" });
    }

        try {
      const settings = await getSiteSettings(); // получаем site settings
      this.setState({ siteSettings: settings });
    } catch (error) {
      console.error("Ошибка загрузки site settings:", error);
    }
  }

  render() {

        const { categories, loading, error , siteSettings } = this.state;
        const { user } = this.context; // user = null, если не авторизован
    return (
      <footer id="footer">
        {/* Верхняя часть футера */}
        <div className="section">
          <div className="container">
            <div className="row">

              {/* О нас */}
              <div className="col-md-3 col-xs-6">
                <div className="footer">
                  <h3 className="footer-title">О нас</h3>
                  <p>
                    Мы предлагаем качественную продукцию и высокий уровень обслуживания. 
                    Ваш комфорт и доверие — наша главная цель.
                  </p>
                  <ul className="footer-links">
                    <li><a href="#"><i className="fa fa-phone"></i>{siteSettings?.phone}</a></li>
                    <li><a href="#"><i className="fa fa-envelope-o"></i>{siteSettings?.email}</a></li>
                  </ul>
                </div>
              </div>


                {/* Категории */}
                <div className="col-md-3 col-xs-6">
                  <div className="footer">
                    <h3 className="footer-title">Категории</h3>
                    <ul className="footer-links">
                      {loading && <li>Загрузка...</li>}
                      {error && <li>{error}</li>}
                      {!loading && !error && categories.length > 0 && categories.slice(0, 5).map(cat => (
                        <li key={cat.id}>
                          <Link to={`/products/?category=${cat.slug}`}>{cat.name}</Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>


              <div className="clearfix visible-xs"></div>

              {/* Информация */}
              <div className="col-md-3 col-xs-6">
                <div className="footer">
                  <h3 className="footer-title">Информация</h3>
                  <ul className="footer-links">
                      <li><Link to="/?page=about-company">О компании</Link></li>

                    <li><Link to="/?page=contacts">Контакты</Link></li>
                  <li>  <a 
                              href="/policy.pdf" 
                              target="_blank" 
                              rel="noopener noreferrer"
                            >
                              Политика конфиденциальности
                            </a></li>
                    <li><Link to="/?page=orders-returns">Заказы и возвраты</Link></li>
                    <li><Link to="/?page=delivery">Доставка</Link></li>
                  </ul>
                </div>
              </div>

                  {/* Сервис */}
                <div className="col-md-3 col-xs-6">
                  <div className="footer">
                    <h3 className="footer-title">Сервис</h3>
                    <ul className="footer-links">
                        <li>
                    <Link to={user ? "/account" : "/login"}>Мой аккаунт</Link>
                  </li>
                      <li><Link to="/cart">Корзина</Link></li>
                      <li><Link to="/wishlist">Избранное</Link></li>
                      <li><Link to="/account/orders">Отслеживание заказа</Link></li>
                    </ul>
                  </div>
                </div>

            </div>
          </div>
        </div>

        {/* Нижняя часть футера */}
        <div id="bottom-footer" className="section">
          <div className="container">
            <div className="row">
              <div className="col-md-12 text-center">
                {/* <ul className="footer-payments">
                  <li><a href="#"><i className="fa fa-cc-visa"></i></a></li>
                  <li><a href="#"><i className="fa fa-credit-card"></i></a></li>
                  <li><a href="#"><i className="fa fa-cc-paypal"></i></a></li>
                  <li><a href="#"><i className="fa fa-cc-mastercard"></i></a></li>
                  <li><a href="#"><i className="fa fa-cc-discover"></i></a></li>
                  <li><a href="#"><i className="fa fa-cc-amex"></i></a></li>
                </ul> */}
                <span className="copyright">
                  © {new Date().getFullYear()} Все права защищены. 
                </span>
              </div>
            </div>
          </div>
        </div>
      </footer>
    );
  }
}

export default Footer;
