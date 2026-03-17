
import React from "react";
import { Link } from 'react-router-dom';
import { FaCouch, FaBed, FaChair, FaBox, FaDoorClosed, FaChild, FaUtensils, FaThLarge } from "react-icons/fa";

import { ReactComponent as ArmchairIcon } from "../assets/icons/ffffff/transparent/1x1/caro-asercion/armchair.min.svg";
import { ReactComponent as FridgeIcon } from "../assets/icons/ffffff/transparent/1x1/caro-asercion/fridge.min.svg";
import { ReactComponent as SofaIcon } from "../assets/icons/ffffff/transparent/1x1/delapouite/sofa.min.svg";
import { ReactComponent as DeskIcon } from "../assets/icons/ffffff/transparent/1x1/delapouite/lockers.min.svg";
import { ReactComponent as BedIcon } from "../assets/icons/ffffff/transparent/1x1/delapouite/bed.min.svg";
import { ReactComponent as ChairIcon } from "../assets/icons/ffffff/transparent/1x1/lorc/stone-throne.min.svg";
import { ReactComponent as TableIcon } from "../assets/icons/ffffff/transparent/1x1/delapouite/table.min.svg";
import { ReactComponent as ChildIcon } from "../assets/icons/ffffff/transparent/1x1/delapouite/piggy-bank.min.svg";
import { ReactComponent as BookshelfIcon } from "../assets/icons/ffffff/transparent/1x1/delapouite/bookshelf.min.svg";
import { ReactComponent as FireplaceIcon } from "../assets/icons/ffffff/transparent/1x1/delapouite/fireplace.min.svg";
import { ReactComponent as BoxIcon } from "../assets/icons/ffffff/transparent/1x1/delapouite/matchbox.min.svg";
import { ReactComponent as UtensilsIcon } from "../assets/icons/ffffff/transparent/1x1/delapouite/moka-pot.min.svg";

const iconsMap = {
  "Пуфы": ArmchairIcon,
  "Все для кухни": FridgeIcon,
  "Офисные диваны": SofaIcon,
  "Шкафы": DeskIcon,
  "Матрасы": BoxIcon,
  "Прихожие": BookshelfIcon,
  "Детская мебель": ChildIcon,
  "Кровати": BedIcon,
  "Стол Стул": TableIcon,
  "Диваны": SofaIcon,
  "Кресла": ChairIcon,
  "Гостинные": FireplaceIcon,
  "Комоды-Тумбы": BoxIcon,
  "Кухни": UtensilsIcon,
};

const colorsMap = {
  "Пуфы": "#6c63ff",
  "Все для кухни": "#ff9800",
  "Офисные диваны": "#009688",
  "Шкафы": "#795548",
  "Матрасы": "#3f51b5",
  "Прихожие": "#9c27b0",
  "Детская мебель": "#f44336",
  "Кровати": "#2196f3",
  "Стол Стул": "#8bc34a",
  "Диваны": "#ff5722",
  "Кресла": "#607d8b",
  "Гостинные": "#00bcd4",
  "Комоды-Тумбы": "#e91e63",
  "Кухни": "#ffc107",
};
const CategoryNameLinkToProducts = ({ categories }) => {
  return (
    <div className="category-sidebar-container">
      {categories.map((category) => {
        const IconComponent = iconsMap[category.name] || BoxIcon;
        const iconColor = colorsMap[category.name] || "#444";

        return (
          <div className="category-list-products-links" key={category.slug}>
            <Link
              to={`/products/?category=${category.slug}`}
              className="category-link"
              style={{ display: "flex", alignItems: "center", gap: "8px" }}
            >
              <span
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "24px",
                  height: "24px",
                }}
              >
                <IconComponent width={20} height={20} fill={iconColor} />
              </span>
              <span style={{ fontSize: "16px", color: iconColor }}>
                {category.name}
              </span>
            </Link>
          </div>
        );
      })}
    </div>
  );
};

export default CategoryNameLinkToProducts;