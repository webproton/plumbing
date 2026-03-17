import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

function Carousel({ products = [], onProductClick }) {
  const [currentIndex, setCurrentIndex] = useState(0);

  // Предварительная загрузка всех изображений баннеров
  useEffect(() => {
      // console.log("Carousel products:", products);
    products.forEach(product => {
      const img = new Image();
      img.src = product.banner_url; // Предзагружаем изображение
    });
  }, [products]); // Зависимость от products, чтобы загрузить изображения при изменении списка

  // Интервал для смены слайдов
  useEffect(() => {
    if (!products.length) return;

    const interval = setInterval(() => {
      setCurrentIndex(prev => (prev + 1) % products.length);
    }, 3000);

    return () => clearInterval(interval);
  }, [products.length]);

  if (!products.length) return <div className="carousel-container">No products available</div>;

  const current = products[currentIndex];


  return (
    <div className="carousel-container">
      <div className="carousel-image-wrapper" onClick={() => onProductClick(current)}>
        <Link to={`/products/${current.slug}/variant/${current.first_variant.slug}`}>
        {console.log("Current banner:", current)}
          <img
            src={current.banner_url}
            alt={current.name}
            className="carousel-image"
            loading="eager" // Загружаем изображение сразу
          />
        </Link>
      </div>

    </div>
  );
}

export default Carousel;