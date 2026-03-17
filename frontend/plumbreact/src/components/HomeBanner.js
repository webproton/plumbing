// src/components/HomeBanner.js
import React from "react";
import BannerSlider from "./BannerSlider";

const slides = [
  {
    img: `${process.env.PUBLIC_URL}/banners/3.png`,
    title: "Доставка своими силами",
    subtitle: "Отправляем быстро и аккуратно",
  },
  {
    img: `${process.env.PUBLIC_URL}/banners/1.png`,
    title: "Гарантия на продукцию",
    subtitle: "Если товар битый — компенсируем расходы",
  },
  {
    img: `${process.env.PUBLIC_URL}/banners/2.png`,
    title: "Осенняя распродажа",
    subtitle: "Скидки до 30% на выбранные товары",
  },
];

const HomeBanner = () => {
  return <BannerSlider slides={slides} autoPlay={true} autoPlayTime={4000} />;
};

export default HomeBanner;
