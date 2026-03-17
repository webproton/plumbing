import 'bootstrap/dist/css/bootstrap.min.css';
// import './css/slick.css';
// import './css/slick-theme.css';
// import './css/nouislider.min.css';
// import './css/font-awesome.min.css';
import './css/style.css';
import React, { Component, Fragment } from "react";
import ComparePage from "./components/ComparePage";
import { BrowserRouter as Router, Route } from 'react-router-dom';


import { WishlistProvider } from "../src/context/WishlistContext";
import { AuthProvider } from "../src/context/AuthContext";
import Home from "./components/Home";
import Header from "./components/Header";
import Footer from "./components/Footer";
import CategoryProducts from "./components/CategoryProducts";
import ProductDetail from "./components/ProductDetail";
import AllCategories from "./components/AllCategories"
import Cart from "./components/Cart";
import Checkout from "./components/Checkout";
import AccountDashboard  from "./components/AccountDashboard";
import OrderHistory from "./components/OrderHistory";
import Profile from "./components/Profile";
import Wishlist from "./components/Wishlist";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Logout from "./pages/Logout";
import ResetPassword from "./pages/ResetPassword";
import PasswordResetConfirm from "./pages/PasswordResetConfirm";
import EmailConfirm from "./pages/EmailConfirm";
import CallbackButton from "./components/CallbackButton";
// import { useTelemetry } from "./hooks/useTelemetry";


// 👇 функциональный компонент для сбора телеметрии
// function TelemetryCollector() {
//   useTelemetry();
//   return null; // ничего не рендерим, только собираем телеметрию
// }

class  App  extends  Component {

  
 
handleCartUpdate = (newCart) => {
  // Обнови localStorage
  localStorage.setItem("cart", JSON.stringify(newCart));
  // Принудительно вызови событие для Header
  window.dispatchEvent(new Event("storage"));
};

  componentDidMount() {
    // Если react-snap выполняется, уведомляем его о полной загрузке
    if (window.snapSaveState) {
      window.snapSaveState();
    }
  }
  render() {
    return (
      <>
    <AuthProvider>
      <WishlistProvider>
      <Fragment>
       {/* <TelemetryCollector />  */}
      <Router>
        <Header />
       <Route exact path="/" component={Home} /> 
        <Route exact path="/category/" component={AllCategories} />
        <Route exact path="/products/" component={CategoryProducts} />
        <Route exact path="/products.:format" component={CategoryProducts} />
        <Route exact path="/products/:productSlug" component={ProductDetail} />
        <Route path="/products/:productSlug/variant/:variantSlug" component={ProductDetail} />

        <Route exact path="/cart/" component={Cart} />
        <Route
            exact
            path="/checkout/"
            render={(props) => <Checkout {...props} onCartUpdate={this.handleCartUpdate} />}
          />

       {/* Главная страница личного кабинета пользователя. */}
        <Route path="/account">
          <AccountDashboard />
        </Route>
        <Route exact path="/account/orders" component={OrderHistory} />
        {/* Страница профиля пользователя (редактирование информации). */}
        <Route exact path="/account/profile" component={Profile} />

          <Route path="/compare" component={ComparePage} />
        <Route exact path="/wishlist" component={Wishlist} />


        <Route exact path="/login" component={Login} />
        <Route exact path="/register" component={Register} />
        <Route exact path="/logout" component={Logout} />
        <Route exact path="/reset-password" component={ResetPassword} />
        <Route exact path="/reset-password/confirm" component={PasswordResetConfirm} />
        <Route path="/confirm-email/:key" component={EmailConfirm} />
      <Footer />
      <CallbackButton />
    </Router> 
  
    
    </Fragment>
    </WishlistProvider>
    </AuthProvider>
    </>
    );

  }
  }
  export  default  App;