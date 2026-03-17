import React, { useState, useEffect } from "react";


const BannerSlider = ({ slides = [], autoPlay = true, autoPlayTime = 5000 }) => {
  const [currentIndex, setCurrentIndex] = useState(0);

  // Автопрокрутка слайдов
  useEffect(() => {
    if (!autoPlay || slides.length <= 1) return;

    const interval = setInterval(() => {
      setCurrentIndex((prevIndex) => (prevIndex + 1) % slides.length);
    }, autoPlayTime);

    return () => clearInterval(interval);
  }, [slides, autoPlay, autoPlayTime]);

  const goToSlide = (index) => {
    setCurrentIndex(index);
  };

  if (!slides.length) return null;

  const currentSlide = slides[currentIndex];

  // console.log(currentSlide,"slider")

  return (
    <div className="banner-slider">
      <div className="banner-slide" style={{ backgroundImage: `url(${currentSlide.img})` }}>
        <div className="banner-content">
          <h2>{currentSlide.title}</h2>
          <p>{currentSlide.subtitle}</p>
          {currentSlide.link && (
            <a href={currentSlide.link} className="banner-cta">
              Подробнее
            </a>
          )}
        </div>
      </div>

      {/* Навигация по слайдам */}
      <div className="banner-dots">
        {slides.map((_, index) => (
          <span
            key={index}
            className={`dot ${index === currentIndex ? "active" : ""}`}
            onClick={() => goToSlide(index)}
          />
        ))}
      </div>
    </div>
  );
};

export default BannerSlider;
