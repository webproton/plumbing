import { Helmet } from "react-helmet";

const HomeHelmet = ({ categories }) => {
    // Генерируем динамическое описание из первых 5 категорий
    const categoryList = categories.slice(0, 5).map(c => c.name).join(", ");
    const description = `Купить мебель для дома и офиса: диваны, кресла, столы, стулья, шкафы, кровати, комоды, тумбы, полки и аксессуары. Новинки, акции, доставка по всей стране. ${categoryList}.`;

    return (
        <Helmet>
            <title>Мебельный магазин – купить диваны, кресла, столы, шкафы и кровати</title>
            <meta name="description" content={description} />
            <meta property="og:title" content="Мебельный магазин – стиль, комфорт и качество для вашего дома" />
            <meta property="og:description" content={description} />
            <meta property="og:image" content="https://example.com/preview-furniture.jpg" />
            <meta property="og:type" content="website" />
            <meta property="og:url" content="https://example.com" />
        </Helmet>
    );
};

export default HomeHelmet;
