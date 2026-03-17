import React, {Component  } from "react";
import ProductsService from "../services/ProductService";
import Navigation from "./Navigation";
import { Link } from 'react-router-dom';
import debounce from 'lodash.debounce';
import { toggleCompareItem } from '../utils/compare';
import { addToCart, syncCart } from "../utils/cartUtils";
import { WishlistContext } from "../context/WishlistContext";
import { Helmet } from "react-helmet";


  // 🟢 Функция возвращает дефолтные значения фильтров
  const getInitialFiltersState = () => ({
  // selectedBrands: [],
  minPrice: "",
  maxPrice: "",
  selectedThreadType: [],
  selectedSizeThread: [],
  selectedManufacturer: [],
  selectedBall: [],
  selectedMaterialProduct: [],
  selectedMechanisms: [],
  selectedUpholstery: [],
  selectedMattressBase: [],
  selectedArmrests: [],
  selectedFilling: [],
  selectedBedTypeForm: [],
  selectedBedType: [],
  selectedPattern: [],
  selectedBodyMaterial: [],
  selectedIncludedItems: [],
  storageNiche: null,
  productNameFilter: "",
  

  // 🔹 Новые фильтры с бэка
  selectedTypeOfProduct: [],  // type_of_product
  minWidth: "",               // min_width
  maxWidth: "",               // max_width
  minHeight: "",              // min_height
  maxHeight: "",              // max_height
  minDepth: "",               // min_depth
  maxDepth: "",               // max_depth
  minBedWidth: "",            // min_bed_width
  maxBedWidth: "",            // max_bed_width
  minBedLength: "",           // min_bed_length
  maxBedLength: "",           // max_bed_length
  sleepingPlaces: "",          // sleeping_places

  expandedFilters: {
        // Brand: false,
        Ball: false,
        Material: false,
        Manufacturer:false,
        'Product Thread Type':false,
        'Thread Size': false,
        Mechanism: false,
        Upholstery: false,
        'Mattress Base': false,
        Armrests: false,
        Filling: false,
        'Bed Type Form': false,
        'Bed Type': false,
        Pattern: false,
        'Body Material': false,
        'Included Items': false,
        'Storage Niche': false,
        'Type of Product': false, // новый
        Dimensions: false, // габариты
        'Bed Parameters': false, // параметры кровати
      },
});


class CategoryProducts extends  Component {

  // This component return  all products list of current category
  static contextType = WishlistContext;
  constructor(props) {
    super(props);
this.state = {
  ...getInitialFiltersState(),
  data: [],
  products: [],
  filteredProducts: [],
  totalProducts: 0,
  nextPageUrl: null,
  prevPageUrl: null,
  loaded: false,
  placeholder: "Loading",
  categoryID: null,
  category: {},
  // allBrands: {},
  selectedSort: '',
  currentPage: 1,
  itemsPerPage: 12,
  cart: [],
  filtersOpen: false,
      // wishlist: JSON.parse(localStorage.getItem("wishlist")) || [],



    };
    
    this.productsService = new ProductsService();
    this.filterProducts = this.filterProducts.bind(this);
    this.handlePageChange = this.handlePageChange.bind(this);
    // this.handleBrandFilter = this.handleBrandFilter.bind(this);
    this.handleResetFilter = this.handleResetFilter.bind(this);
    this.handleBallFilter = this.handleBallFilter.bind(this); // добавлен новый обработчик
    this.handleMaterialFilter = this.handleMaterialFilter.bind(this); // добавлен новый обработчик
    this.handleManufacturerFilter = this.handleManufacturerFilter.bind(this); // добавлен новый обработчик
    this.handleThreadTypeFilter = this.handleThreadTypeFilter.bind(this); // добавлен новый обработчик
    this.handleThreadSizeFilter = this.handleThreadSizeFilter.bind(this); // добавлен новый обработчик
    this.toggleFilter = this.toggleFilter.bind(this);


        // биндим хендлеры
    this.handleMechanismFilter = this.handleMechanismFilter.bind(this);
    this.handleUpholsteryFilter = this.handleUpholsteryFilter.bind(this);
    this.handleMattressBaseFilter = this.handleMattressBaseFilter.bind(this);


    this.handleArmrestsFilter = this.handleArmrestFilter.bind(this);
    
    this.handleFillingFilter = this.handleFillingFilter.bind(this);
    this.handleBedTypeFormFilter = this.handleBedTypeFormFilter.bind(this);
    this.handleBedTypeFilter = this.handleBedTypeFilter.bind(this);
    this.handlePatternFilter = this.handlePatternFilter.bind(this);
    this.handleBodyMaterialFilter = this.handleBodyMaterialFilter.bind(this);
    this.handleIncludedItemsFilter = this.handleIncludedItemsFilter.bind(this);
    this.handleStorageNicheFilter = this.handleStorageNicheFilter.bind(this);

    this.handleMinWidthChange = this.handleMinWidthChange.bind(this);
    this.handleMaxWidthChange = this.handleMaxWidthChange.bind(this);
    this.handleMinHeightChange = this.handleMinHeightChange.bind(this);
    this.handleMaxHeightChange = this.handleMaxHeightChange.bind(this);
    this.handleMinDepthChange = this.handleMinDepthChange.bind(this);
    this.handleMaxDepthChange = this.handleMaxDepthChange.bind(this);

    this.handleMinBedWidthChange = this.handleMinBedWidthChange.bind(this);
    this.handleMaxBedWidthChange = this.handleMaxBedWidthChange.bind(this);
    this.handleMinBedLengthChange = this.handleMinBedLengthChange.bind(this);
    this.handleMaxBedLengthChange = this.handleMaxBedLengthChange.bind(this);
    this.handleSleepingPlacesChange = this.handleSleepingPlacesChange.bind(this);
    this.handleTypeOfProductFilter = this.handleTypeOfProductFilter.bind(this);

  }




    // ========= 🔹 Хендлеры для мультивыбора =========
  handleMechanismFilter(id) {
    this.toggleMultiSelect("selectedMechanisms", id);
  }

  handleUpholsteryFilter(id) {
    this.toggleMultiSelect("selectedUpholstery", id);
  }

  handleMattressBaseFilter(id) {
    this.toggleMultiSelect("selectedMattressBase", id);
  }

  handleArmrestFilter(id) {
    this.toggleMultiSelect("selectedArmrests", id);
  }

  handleFillingFilter(id) {
    this.toggleMultiSelect("selectedFilling", id);
  }

  handleBedTypeFormFilter(id) {
    this.toggleMultiSelect("selectedBedTypeForm", id);
  }

  handleBedTypeFilter(id) {
    this.toggleMultiSelect("selectedBedType", id);
  }

  handlePatternFilter(id) {
    this.toggleMultiSelect("selectedPattern", id);
  }

  handleBodyMaterialFilter(id) {
    this.toggleMultiSelect("selectedBodyMaterial", id);
  }

  handleIncludedItemsFilter(id) {
    this.toggleMultiSelect("selectedIncludedItems", id);
  }

  // ========= 🔹 Хендлер для Boolean =========
  handleStorageNicheFilter(value) {
    this.setState({ storageNiche: value }, this.filterProducts);
  }

  handleTypeOfProductFilter = (typeId) => {
  this.toggleMultiSelect("selectedTypeOfProduct", typeId);
};

// Для габаритов и кровати
handleMinWidthChange = (e) => this.setState({ minWidth: e.target.value }, this.debouncedFilterProducts);
handleMaxWidthChange = (e) => this.setState({ maxWidth: e.target.value }, this.debouncedFilterProducts);
handleMinHeightChange = (e) => this.setState({ minHeight: e.target.value }, this.debouncedFilterProducts);
handleMaxHeightChange = (e) => this.setState({ maxHeight: e.target.value }, this.debouncedFilterProducts);
handleMinDepthChange = (e) => this.setState({ minDepth: e.target.value }, this.debouncedFilterProducts);
handleMaxDepthChange = (e) => this.setState({ maxDepth: e.target.value }, this.debouncedFilterProducts);

handleMinBedWidthChange = (e) => this.setState({ minBedWidth: e.target.value }, this.debouncedFilterProducts);
handleMaxBedWidthChange = (e) => this.setState({ maxBedWidth: e.target.value }, this.debouncedFilterProducts);
handleMinBedLengthChange = (e) => this.setState({ minBedLength: e.target.value }, this.debouncedFilterProducts);
handleMaxBedLengthChange = (e) => this.setState({ maxBedLength: e.target.value }, this.debouncedFilterProducts);
handleSleepingPlacesChange = (e) => this.setState({ sleepingPlaces: e.target.value }, this.debouncedFilterProducts);


  // ========= 🔹 Вспомогательная функция для мультивыбора =========
  toggleMultiSelect(stateKey, id) {
    this.setState(prevState => {
      const updated = prevState[stateKey].includes(id)
        ? prevState[stateKey].filter(item => item !== id)
        : [...prevState[stateKey], id];
      return { [stateKey]: updated };
    }, this.filterProducts);
  }

  


  // ========= 🔹 Жизненный цикл =========
async componentDidMount() {
  window.addEventListener("storage", this.syncCart);

  const savedCart = JSON.parse(localStorage.getItem("cart")) || [];
  const savedWishlist = JSON.parse(localStorage.getItem("wishlist")) || [];
  this.setState({ cart: savedCart, wishlist: savedWishlist });

  const queryParams = new URLSearchParams(this.props.location.search);
  const categoryID = queryParams.get("category");
  const currentPage = parseInt(queryParams.get("page")) || 1;
  this.setState({ currentPage });

  if (categoryID) {
    this.setState({ ...getInitialFiltersState(), categoryID, category: {} }, async () => {
      const data = await this.fetchCategoryData(categoryID, true); // все продукты
      // const data = await this.fetchCategoryData(categoryID);
      const products = data.results || data;

      if (products.length > 0) {
        const categoryData = products[0].category || {};
        this.setState({
          category: {
            slug: categoryData.slug || categoryID,
            name: categoryData.name || categoryID,
          },
        });
      } else {
        this.setState({
          category: { slug: categoryID, name: categoryID },
        });
      }
    });
  } else {
    this.setState({ error: "Category ID is missing." });
  }
}

  async componentDidUpdate(prevProps) {
    const prevCategoryID = new URLSearchParams(prevProps.location.search).get(
      "category"
    );
    const currentCategoryID = new URLSearchParams(
      this.props.location.search
    ).get("category");

    // Если категория изменилась
    if (prevCategoryID !== currentCategoryID && currentCategoryID) {
      const initialFilters = getInitialFiltersState() || {};
      const initialExpanded = initialFilters.expandedFilters || {};

      this.setState(
        {
          ...initialFilters,
          filtersOpen: false,
          expandedFilters: Object.keys(initialExpanded).reduce(
            (acc, key) => ({ ...acc, [key]: false }),
            {}
          ),
          categoryID: currentCategoryID,
          category: { slug: currentCategoryID, name: "" },
          products: [],
          data: [],
          filteredProducts: [],
          loaded: false,
        },
        async () => {
          const data = await this.fetchCategoryData(currentCategoryID);
          if (data.length > 0) {
            const categoryData = data.results[0].category || {};
            this.setState({
              category: {
                slug: categoryData.slug || currentCategoryID,
                name: categoryData.name || currentCategoryID,
              },
              loaded: true,
            });
          } else {
            this.setState({
              category: { slug: currentCategoryID, name: currentCategoryID },
              loaded: true,
            });
          }
        }
      );
    }

    // Синхронизация корзины
    if (JSON.stringify(prevProps.cart) !== JSON.stringify(this.state.cart)) {
      localStorage.setItem("cart", JSON.stringify(this.state.cart));
    }
  }

  
 
  componentWillUnmount() {
    window.removeEventListener("storage", this.syncCart);
    // window.removeEventListener("storage", this.syncWishlist);
  }

// Добавление в корзину
handleAddToCart = (product) => {
  if (!product.first_variant) return alert("Нет доступного варианта");

  addToCart(product); // добавляем через утилиту

  let message = "Добавлено";

  this.setState(prevState => {
    const updatedProducts = prevState.products.map(p => {
      if (p.id === product.id) {
        const cartCount = (p.cartCount || 0) + 1;
        if (cartCount > 1) message = "+1";
        return { ...p, cartCount };
      }
      return p;
    });
    return { products: updatedProducts };
  }, () => {
    // После обновления состояния показываем popup
    this.showPopup(product.id, "addedCart", message);
  });
};

// Wishlist
handleToggleWishlist = (product) => {
  const { toggleWishlist, wishlist } = this.context;
  const variantId = product.first_variant?.id;
  if (!variantId) return;

  const isInWishlist = wishlist.some(w => w.product_variant.id === variantId);
  toggleWishlist(product.first_variant);

  const message = isInWishlist ? "Удалено из избранного" : "В избранное";
  this.showPopup(product.id, "addedWishlist", message);
};

// Compare
handleCompare = (product) => {
  const added = toggleCompareItem(product); // true = добавлено
  const message = added ? "В сравнении" : "Удалено из сравнения";

  this.showPopup(product.id, "addedCompare", message);
};

// Универсальный popup
showPopup = (productId, key, message) => {
  this.setState(prevState => ({
    products: prevState.products.map(p =>
      p.id === productId ? { ...p, [key]: message } : p
    )
  }));

  // Через 2 секунды убираем popup
  setTimeout(() => {
    this.setState(prevState => ({
      products: prevState.products.map(p =>
        p.id === productId ? { ...p, [key]: null } : p
      )
    }));
  }, 2000);
};


syncCart = () => syncCart(this); // Используем утилиту

async fetchCategoryData(categoryId, fetchAll = false) {
  const { minPrice, maxPrice, selectedSort } = this.state;
  let sortQuery = selectedSort === 'price-asc' ? 'price' : selectedSort === 'price-desc' ? '-price' : '';

  try {
    const data = await this.productsService.getProductsByCategory(
      categoryId, 
      minPrice, 
      maxPrice, 
      sortQuery, 
      fetchAll // 👈 выбираем режим
    );

    // Если fetchAll=true → вернётся массив, иначе объект с results
    const products = Array.isArray(data) ? data : (data.results || data);

    // console.log('Fetched products length:', products.length);

    // const allBrands = {};
    // products.forEach(product => {
    //   if (product.first_variant?.brand) {
    //     allBrands[product.first_variant.brand.id] = product.first_variant.brand.name;
    //   }
    // });

    this.setState({
      data: products,
      products: products,
      filteredProducts: products,
      // allBrands,
      loaded: true
    });

    return data;

  } catch (error) {
    console.error('Error fetching category products:', error);
    this.setState({ error: 'Failed to load products.' });
    return [];
  }
}



  handlePageChange = (page) => {
  this.setState({ currentPage: page }, () => {
    // Сохраняем страницу и scroll
    const scrollPos = window.scrollY || window.pageYOffset;
    sessionStorage.setItem('productsPage', page);
    sessionStorage.setItem('productsScroll', scrollPos);
  });

  // Меняем URL (опционально)
  const queryParams = new URLSearchParams(this.props.location.search);
  queryParams.set("page", page);
  this.props.history.replace({ search: queryParams.toString() });
}
sortProducts = (products, sortType) => {
  if (Array.isArray(products)) {
    return [...products].sort((a, b) => {
      if (sortType === 'price-asc') {
        return a.first_variant.price - b.first_variant.price;
      } else if (sortType === 'price-desc') {
        return b.first_variant.price - a.first_variant.price;
      }
      return 0;
    });
  }
  return products;
};

handleSortChange = (event) => {
  const sortType = event.target.value;
  const { products } = this.state;

  const sortedProducts = this.sortProducts(products, sortType);

  this.setState({ products: sortedProducts, filteredProducts: sortedProducts });
};



toggleFilters = () => {
  this.setState(prev => ({ filtersOpen: !prev.filtersOpen }));
};

toggleFilter = (filterName) => {
  this.setState(prevState => ({
    expandedFilters: {
      ...prevState.expandedFilters,
      [filterName]: !prevState.expandedFilters[filterName],
    }
  }));
}

loadMoreProducts = () => {
  //this not working right now 18 May
  const { products, allProducts, itemsPerPage, currentPage } = this.state;

  // Если продукты закончились, не загружать больше
  if (products.length >= allProducts.length) {
    return;
  }

  // Увеличиваем текущую страницу на 1
  const newPage = currentPage + 1;

  // Загружаем новые продукты на основе текущей страницы и лимита продуктов на страницу
  const nextProducts = allProducts.slice(newPage * itemsPerPage - itemsPerPage, newPage * itemsPerPage);

  // Обновляем состояние
  this.setState({
    products: [...products, ...nextProducts],
    currentPage: newPage,
  });
};


  handleProductNameFilter = ( e) => {
    this.setState({ productNameFilter: e.target.value }, this.filterProducts);
  }
  
  // handleBrandFilter = (brandId) => {
  //   const { selectedBrands } = this.state;
  //   const updatedBrands = selectedBrands.includes(brandId)
  //     ? selectedBrands.filter((id) => id !== brandId)
  //     : [...selectedBrands, brandId];
  
  //     this.setState({ selectedBrands: updatedBrands }, this.filterProducts);
  //   }
  
  handleMaterialFilter = (materialId) => {
    const { selectedMaterialProduct } = this.state;
    const updatedMaterial = selectedMaterialProduct.includes(materialId)
      ? selectedMaterialProduct.filter((id) => id !== materialId)
      : [...selectedMaterialProduct, materialId];
    this.setState({ selectedMaterialProduct: updatedMaterial }, this.filterProducts);
  };

  handleBallFilter = (ballId) => {
    const { selectedBall } = this.state;
    const updatedBall = selectedBall.includes(ballId)
      ? selectedBall.filter((id) => id !== ballId)
      : [...selectedBall, ballId];
    this.setState({ selectedBall: updatedBall }, this.filterProducts);
  };

  handleThreadTypeFilter = (product_threadId) => {
    const { selectedThreadType } = this.state;
    const updatedProduct_thread = selectedThreadType.includes(product_threadId)
      ? selectedThreadType.filter((id) => id !== product_threadId)
      : [...selectedThreadType, product_threadId];

    this.setState({ selectedThreadType: updatedProduct_thread }, this.filterProducts);

  };

  handleThreadSizeFilter = (threadId) => {
    const { selectedSizeThread } = this.state;
    const updatedThread = selectedSizeThread.includes(threadId)

      ? selectedSizeThread.filter((id) => id !== threadId)
      : [...selectedSizeThread, threadId];

    this.setState({ selectedSizeThread: updatedThread }, this.filterProducts);
  };

  handleManufacturerFilter = (manufacturerId) => {
    const { selectedManufacturer } = this.state;
    const updatedManufacturer = selectedManufacturer.includes(manufacturerId)

      ? selectedManufacturer.filter((id) => id !== manufacturerId)
      : [...selectedManufacturer, manufacturerId];

    this.setState({ selectedManufacturer: updatedManufacturer }, this.filterProducts);
  };

  handleResetFilter = () => {
  this.setState(getInitialFiltersState(), () => {
    this.filterProducts();
  });
};


  

  handleMinPriceChange = (e) => {
    this.setState({ minPrice: e.target.value }, this.debouncedFilterProducts);
  };
  
  handleMaxPriceChange = (e) => {
    this.setState({ maxPrice: e.target.value }, this.debouncedFilterProducts);
  };



  // Создаем версию filterProducts с задержкой в 300 мс
  debouncedFilterProducts = debounce(() => {
  this.filterProducts();
    }, 300);

filterProducts() {
  const {
    data,
    products,
    ...filters // берём все фильтры одной переменной
  } = this.state;

  const {
  //  selectedBrands,
    selectedBall,
    selectedSizeThread,
    selectedManufacturer,
    selectedMaterialProduct,
    selectedThreadType,
    selectedMechanisms,
    selectedUpholstery,
    selectedMattressBase,
    selectedArmrests,
    selectedFilling,
    selectedBedTypeForm,
    selectedBedType,
    selectedPattern,
    selectedBodyMaterial,
    selectedIncludedItems,
    selectedTypeOfProduct,
    storageNiche,
    minPrice,
    maxPrice,
    minWidth,
    maxWidth,
    minHeight,
    maxHeight,
    minDepth,
    maxDepth,
    minBedWidth,
    maxBedWidth,
    minBedLength,
    maxBedLength,
    sleepingPlaces,
    productNameFilter
  } = filters;

  let filteredResults = data;

  // 🔹 Хелпер для простых one-to-one фильтров
  const applySingleFilter = (items, selected, getter) => {
    if (!selected || selected.length === 0) return items;
    return items.filter(product => {
      const id = getter(product);
      return id && selected.includes(String(id));
    });
  };

  // 🔹 Хелпер для many-to-many фильтров
  const applyMultiFilter = (items, selected, getter) => {
    if (!selected || selected.length === 0) return items;
    return items.filter(product => {
      const values = getter(product) || [];
      return values.some(v => selected.includes(String(v)));
    });
  };

  // ================== НОВЫЕ ФИЛЬТРЫ ==================
  filteredResults = applySingleFilter(filteredResults, selectedMechanisms, p => p.first_variant?.mechanism?.id);
  filteredResults = applyMultiFilter(filteredResults, selectedUpholstery, p => p.first_variant?.upholstery_materials?.map(m => m.id));
  filteredResults = applySingleFilter(filteredResults, selectedMattressBase, p => p.first_variant?.mattress_base?.id);
  filteredResults = applySingleFilter(filteredResults, selectedArmrests, p => p.first_variant?.armrests?.id);
  filteredResults = applySingleFilter(filteredResults, selectedFilling, p => p.first_variant?.filling?.id);
  filteredResults = applySingleFilter(filteredResults, selectedBedTypeForm, p => p.first_variant?.bed_type_form?.id);
  filteredResults = applySingleFilter(filteredResults, selectedBedType, p => p.first_variant?.bed_type?.id);
  filteredResults = applySingleFilter(filteredResults, selectedPattern, p => p.first_variant?.pattern?.id);
  filteredResults = applySingleFilter(filteredResults, selectedBodyMaterial, p => p.first_variant?.body_material?.id);
  filteredResults = applyMultiFilter(filteredResults, selectedIncludedItems, p => p.first_variant?.included_items?.map(i => i.id));

    // 🔹 Тип продукта


    filteredResults = applySingleFilter(
      filteredResults,
      selectedTypeOfProduct,
      p => p.first_variant?.type_of_product?.id
    );


  // Boolean-фильтр (ниша для хранения)
  if (storageNiche !== null) {
    filteredResults = filteredResults.filter(product =>
      product.first_variant?.storage_niche === storageNiche
    );
  }

  // ================== СТАРЫЕ ФИЛЬТРЫ ==================
  // filteredResults = applySingleFilter(filteredResults, selectedBrands, p => p.first_variant?.brand?.id);
  filteredResults = applySingleFilter(filteredResults, selectedBall, p => p.first_variant?.ball?.ball_material_type?.id);
  filteredResults = applySingleFilter(filteredResults, selectedSizeThread, p => p.first_variant?.thread_size?.id);
  filteredResults = applySingleFilter(filteredResults, selectedManufacturer, p => p.first_variant?.manufacturer?.id);
  filteredResults = applySingleFilter(filteredResults, selectedMaterialProduct, p => p.first_variant?.material?.id);
  filteredResults = applySingleFilter(filteredResults, selectedThreadType, p => p.first_variant?.product_thread?.id);

  // ================== Числовые диапазоны ==================
  // 🔹 Габариты
  filteredResults = filteredResults.filter(product => {
    const width = product.first_variant?.dimensions_width || 0;
    const height = product.first_variant?.dimensions_height || 0;
    const depth = product.first_variant?.dimensions_depth || 0;

    if (minWidth && width < parseFloat(minWidth)) return false;
    if (maxWidth && width > parseFloat(maxWidth)) return false;
    if (minHeight && height < parseFloat(minHeight)) return false;
    if (maxHeight && height > parseFloat(maxHeight)) return false;
    if (minDepth && depth < parseFloat(minDepth)) return false;
    if (maxDepth && depth > parseFloat(maxDepth)) return false;

    return true;
  });


    // 🔹 Параметры кровати
  filteredResults = filteredResults.filter(product => {
    const bedWidth = product.first_variant?.bed_width || 0;
    const bedLength = product.first_variant?.bed_length || 0;
    const sleeping = product.first_variant?.sleeping_places || 0;

    if (minBedWidth && bedWidth < parseFloat(minBedWidth)) return false;
    if (maxBedWidth && bedWidth > parseFloat(maxBedWidth)) return false;
    if (minBedLength && bedLength < parseFloat(minBedLength)) return false;
    if (maxBedLength && bedLength > parseFloat(maxBedLength)) return false;
    if (sleepingPlaces && sleeping !== parseInt(sleepingPlaces)) return false;

    return true;
  });


  // Фильтр по цене
  if (minPrice !== "" || maxPrice !== "") {
    filteredResults = filteredResults.filter(product => {
      const price = parseFloat(product.first_variant?.price || 0);
      if (minPrice !== "" && price < parseFloat(minPrice)) return false;
      if (maxPrice !== "" && price > parseFloat(maxPrice)) return false;
      return true;
    });
  }

  // Фильтр по имени продукта
  if (productNameFilter) {
    const filterText = productNameFilter.toLowerCase();
    filteredResults = filteredResults.filter(product =>
      product.name.toLowerCase().includes(filterText)
    );
  }

  // Удаление дубликатов по id
  const uniqueProducts = Array.from(
    new Map(filteredResults.map(product => [product.id, product])).values()
  );

  // Сортировка
  const sortedProducts = this.sortProducts(uniqueProducts);

  // Обновляем состояние
  this.setState({
    products: sortedProducts,
    filteredProducts: sortedProducts,
    currentPage: 1,
  });
}

  
  

render() {


  const filtersByCategory = {
    kitchen: [
      // "selectedBrands",
      "selectedBodyMaterial",
      "selectedColor",
      "customSizeAvailable",
      "selectedTypeOfProduct",
      "storageNiche"
    ],

    komplectmebeli: [
      // "selectedBrands",
      "selectedBodyMaterial",
      "selectedColor",
      "customSizeAvailable",
      "selectedTypeOfProduct",
      "storageNiche"
    ],

    pufy: [
      // "selectedBrands",
      "selectedBedTypeForm",
      "selectedBodyMaterial",
      "selectedColor",
      "selectedFilling",
      "selectedMechanism",
      "selectedPattern",
      "selectedTypeOfProduct",
      "selectedUpholsteryMaterials",
      "storageNiche"
    ],

    shkafy: [
      // "selectedBrands",
      "selectedBodyMaterial",
      "selectedTypeOfProduct",
      "storageNiche"
    ],

    stolstyl: [
      // "selectedBrands",
      "selectedBodyMaterial",
      "selectedTypeOfProduct",
      "minSeatDepth",
      "maxSeatDepth",
      "minSeatHeight",
      "maxSeatHeight",
      "storageNiche"
    ],

    ofisnyedivany: [
      // "selectedBrands",
      "selectedBodyMaterial",
      "selectedColor",
      "selectedTypeOfProduct",
      "selectedUpholsteryMaterials",
      "minSeatDepth",
      "maxSeatDepth",
      "minSeatHeight",
      "maxSeatHeight",
      "storageNiche"
    ],

    matrasyortopedicheskie: [
      // "selectedBrands",
      "selectedFilling",
      "selectedTypeOfProduct",
      "storageNiche"
    ],

    gostinye: [
      // "selectedBrands",
      "selectedBodyMaterial",
      "selectedColor",
      "selectedTypeOfProduct",
      "storageNiche"
    ],

    detskayamebel: [
      // "selectedBrands",
      "selectedBedType",
      "selectedMattressBase",
      "selectedFilling",
      "selectedBodyMaterial",
      "selectedTypeOfProduct",
      "minBedWidth",
      "maxBedWidth",
      "minBedLength",
      "maxBedLength",
      "storageNiche"
    ],

    prihozhie: [
      // "selectedBrands",
      "selectedBodyMaterial",
      "selectedColor",
      "selectedTypeOfProduct",
      "storageNiche"
    ],

    kresla: [
      // "selectedBrands",
      "selectedBedTypeForm",
      "selectedBodyMaterial",
      "selectedColor",
      "selectedFilling",
      "selectedMechanism",
      "selectedPattern",
      "selectedTypeOfProduct",
      "selectedUpholsteryMaterials",
      "storageNiche"
    ],

    komodytumby: [
      // "selectedBrands",
      "selectedBodyMaterial",
      "selectedTypeOfProduct",
      "customSizeAvailable",
      "storageNiche"
    ],

    divany: [
      // "selectedBrands",
      "selectedBedTypeForm",
      "selectedBedType",
      "selectedMattressBase",
      "selectedFilling",
      "storageNiche",
      "sleepingPlaces",
      "selectedArmrests",
      "selectedBodyMaterial",
      "selectedMechanism",
      "selectedPattern",
      "selectedTypeOfProduct",
      "selectedUpholsteryMaterials",
      "selectedColor",

      "minBedWidth",
      "maxBedWidth",
      "minBedLength",
      "maxBedLength",
      "sleepingPlaces",
    ],

    krovat: [
      // "selectedBrands",
      "selectedBedTypeForm",
      "selectedBedType",
      "selectedMattressBase",
      "selectedFilling",
      "storageNiche",
      "minBedWidth",
      "maxBedWidth",
      "minBedLength",
      "maxBedLength",
      "sleepingPlaces",
      "selectedBodyMaterial",
      "selectedTypeOfProduct"
    ],

    vsedlyaobustroystvakukhni: [],

    kranu: [
      // "selectedBrands",
      // "selectedThreadType",
      // "selectedSizeThread",
      "selectedManufacturer",
      "selectedMaterialProduct",
      // "selectedBall"
    ],
  };




  const {
    products,
    data,
    loaded,
    placeholder,
    // selectedBrands,
    minPrice,
    maxPrice,
    selectedThreadType,
    selectedSizeThread,
    selectedManufacturer,
    selectedBall,
    selectedMaterialProduct,
    currentPage,
    itemsPerPage,
    productNameFilter,
    selectedMechanisms,
    selectedUpholstery,
    selectedMattressBase,
    selectedArmrests,
    selectedFilling,
    selectedBedTypeForm,
    selectedBedType,
    selectedPattern,
    selectedBodyMaterial,
    selectedIncludedItems,
    storageNiche,
    selectedTypeOfProduct,
  } = this.state;

      // if (!loaded) {
      //   return <div>{placeholder}</div>;
      // }
  if (!loaded || !this.state.category) {
  return <div>{placeholder}</div>;
}


      // Логика для текущих продуктов
      const start = (currentPage - 1) * itemsPerPage;
      const end = start + itemsPerPage;
      const paginatedProducts = products.slice(start, end);
      
      // Инициализация объектов для фильтрации
      // const brands = {};
      const balls = {};
      const materials = {};
      const manufacturers = {};
      const productThreadTypes = {};
      const threadSizes = {};


        // 🔹 Новые фильтры
      const mechanisms = {};
      const upholsteries = {};
      const mattressBases = {};
      const armrests = {};
      const fillings = {};
      const bedTypeForms = {};
      const bedTypes = {};
      const patterns = {};
      const bodyMaterials = {};
      const includedItems = {};

      const typeOfProducts = {};
      

      // Проход по результатам продуктов
      // 🔹 Проход по продуктам
      data.forEach(product => {
        const { first_variant } = product;

        if (!first_variant) return;

          // Тип продукта
        const type = first_variant.type_of_product;
        if (type) typeOfProducts[type.id] = type.name;

        // Старые фильтры
        // if (first_variant.brand) brands[first_variant.brand.id] = first_variant.brand.name;
        if (first_variant.ball?.ball_material_type) balls[first_variant.ball.ball_material_type.id] = first_variant.ball.ball_material_type.name;
        if (first_variant.material) materials[first_variant.material.id] = first_variant.material.name;
        if (first_variant.manufacturer) manufacturers[first_variant.manufacturer.id] = first_variant.manufacturer.country || 'Unknown Country';
        if (first_variant.product_thread) productThreadTypes[first_variant.product_thread.id] = first_variant.product_thread.thread_type;
        if (first_variant.thread_size) threadSizes[first_variant.thread_size.id] = first_variant.thread_size.inches;

        // Новые фильтры
        if (first_variant.mechanism) mechanisms[first_variant.mechanism.id] = first_variant.mechanism.name;
        if (first_variant.upholstery_materials) {
          first_variant.upholstery_materials.forEach(m => {
            upholsteries[m.id] = m.name;
          });
        }
        if (first_variant.mattress_base) mattressBases[first_variant.mattress_base.id] = first_variant.mattress_base.name;
        if (first_variant.armrests) armrests[first_variant.armrests.id] = first_variant.armrests.name;
        if (first_variant.filling) fillings[first_variant.filling.id] = first_variant.filling.name;
        if (first_variant.bed_type_form) bedTypeForms[first_variant.bed_type_form.id] = first_variant.bed_type_form.name;
        if (first_variant.bed_type) bedTypes[first_variant.bed_type.id] = first_variant.bed_type.name;
        if (first_variant.pattern) patterns[first_variant.pattern.id] = first_variant.pattern.name;
        if (first_variant.body_material) bodyMaterials[first_variant.body_material.id] = first_variant.body_material.name;
        if (first_variant.included_items) {
          first_variant.included_items.forEach(item => {
            includedItems[item.id] = item.name;
          });
        }
      });
// Только для кровати
// Только для кровати
const bedParameterFilters = [
  {
    key: "minBedWidth",
    title: "Ширина спального места (Мин)",
    render: () => (
      <div className="aside">
        <label>
          Ширина спального места (Мин):
          <input
            type="number"
            value={this.state.minBedWidth}
            onChange={this.handleMinBedWidthChange}
          />
        </label>
      </div>
    ),
  },
  {
    key: "maxBedWidth",
    title: "Ширина спального места (Макс)",
    render: () => (
      <div className="aside">
        <label>
          Ширина спального места (Макс):
          <input
            type="number"
            value={this.state.maxBedWidth}
            onChange={this.handleMaxBedWidthChange}
          />
        </label>
      </div>
    ),
  },
  {
    key: "minBedLength",
    title: "Длина спального места (Мин)",
    render: () => (
      <div className="aside">
        <label>
          Длина спального места (Мин):
          <input
            type="number"
            value={this.state.minBedLength}
            onChange={this.handleMinBedLengthChange}
          />
        </label>
      </div>
    ),
  },
  {
    key: "maxBedLength",
    title: "Длина спального места (Макс)",
    render: () => (
      <div className="aside">
        <label>
          Длина спального места (Макс):
          <input
            type="number"
            value={this.state.maxBedLength}
            onChange={this.handleMaxBedLengthChange}
          />
        </label>
      </div>
    ),
  },
  {
    key: "sleepingPlaces",
    title: "Количество спальных мест",
    render: () => (
      <div className="aside">
        <label>
          Количество спальных мест:
          <input
            type="number"
            value={this.state.sleepingPlaces}
            onChange={this.handleSleepingPlacesChange}
          />
        </label>
      </div>
    ),
  },
];

 {/* Внутри render() или перед return */}
const categoryFilters = [
  // { key: "selectedBrands", title: "Бренд", items: brands, handler: this.handleBrandFilter, selected: selectedBrands },
  { key: "selectedBall", title: "Мяч", items: balls, handler: this.handleBallFilter, selected: selectedBall },
  { key: "selectedMaterialProduct", title: "Материал", items: materials, handler: this.handleMaterialFilter, selected: selectedMaterialProduct },
  { key: "selectedManufacturer", title: "Производитель", items: manufacturers, handler: this.handleManufacturerFilter, selected: selectedManufacturer },
  { key: "selectedThreadType", title: "Тип резьбы", items: productThreadTypes, handler: this.handleThreadTypeFilter, selected: selectedThreadType },
  { key: "selectedSizeThread", title: "Размер резьбы", items: threadSizes, handler: this.handleThreadSizeFilter, selected: selectedSizeThread },
  { key: "selectedMechanisms", title: "Механизм", items: mechanisms, handler: this.handleMechanismFilter, selected: selectedMechanisms },
  { key: "selectedUpholstery", title: "Обивка", items: upholsteries, handler: this.handleUpholsteryFilter, selected: selectedUpholstery },
  { key: "selectedMattressBase", title: "Основание матраса", items: mattressBases, handler: this.handleMattressBaseFilter, selected: selectedMattressBase },
  { key: "selectedArmrests", title: "Подлокотники", items: armrests, handler: this.handleArmrestsFilter, selected: selectedArmrests },
  { key: "selectedFilling", title: "Наполнитель", items: fillings, handler: this.handleFillingFilter, selected: selectedFilling },
  { key: "selectedBedTypeForm", title: "Форма кровати", items: bedTypeForms, handler: this.handleBedTypeFormFilter, selected: selectedBedTypeForm },
  { key: "selectedBedType", title: "Тип кровати", items: bedTypes, handler: this.handleBedTypeFilter, selected: selectedBedType },
  { key: "selectedPattern", title: "Узор", items: patterns, handler: this.handlePatternFilter, selected: selectedPattern },
];

const globalFilters = [
  { key: "selectedBodyMaterial", title: "Материал корпуса", items: bodyMaterials, handler: this.handleBodyMaterialFilter, selected: selectedBodyMaterial },
  { key: "selectedIncludedItems", title: "В комплекте", items: includedItems, handler: this.handleIncludedItemsFilter, selected: selectedIncludedItems },
  { key: "selectedTypeOfProduct", title: "Тип продукта", items: typeOfProducts, handler: this.handleTypeOfProductFilter, selected: selectedTypeOfProduct },
  { key: "storageNiche", title: "Ниша для хранения", items: { true: "С нишей", false: "Без ниши" }, handler: this.handleStorageNicheFilter, selected: this.state.storageNiche !== null ? [this.state.storageNiche] : [] },
];


// Отфильтровываем категорийные фильтры для текущей категории
const filteredCategoryFilters = categoryFilters.filter(f =>
  filtersByCategory[this.state.category?.slug]?.includes(f.key)
);

// 2️⃣ Если категория — кровать, добавляем Bed Parameters
let bedFilters = [];
if (["krovat", "divany", "detskayamebel"].includes(this.state.category?.slug)) {
  bedFilters = bedParameterFilters; // массив с render функциями
}


// Объединяем глобальные и категорийные фильтры
const allFilters = [...globalFilters, ...filteredCategoryFilters, ...bedFilters];

   
return (
  <>
    <Helmet>
      <title>{this.state.category.name} – Каталог продукции</title>
      <meta
        name="description"
        content={`Купить ${this.state.category.name} от лучших производителей. Большой выбор товаров, акции, скидки и доставка по Украины.`}
      />
      <meta property="og:title" content={`${this.state.category.name} – Каталог продукции`} />
      <meta
        property="og:description"
        content={`Купить ${this.state.category.name} от лучших производителей. Большой выбор товаров, акции, скидки и доставка по Украины.`}
      />
      <meta property="og:image" content="https://example.com/preview-category.jpg" />
    </Helmet>

    <Navigation />

    <div className="section">
      <div className="category-wrapper">
        {/* SIDEBAR */}
        <aside className={`category-sidebar ${this.state.filtersOpen ? "open" : "closed"}`}>

          <div className="aside-filters-wrapper">
            <div className="aside">
              <h3 className="aside-title">Поиск по имени</h3>
              <input
                type="text"
                className="input"
                value={this.state.productNameFilter}
                onChange={this.handleProductNameFilter}
                placeholder="поиск по имени продукта"
              />
            </div>
            <div className="aside">
              <h3 className="aside-title" onClick={() => this.toggleFilter('Dimensions')}>
                Общие размеры {this.state.expandedFilters['Dimensions'] ? '▲' : '▼'}
              </h3>
              {this.state.expandedFilters['Dimensions'] && (
                <div className="dimension-filters">
                  <label>
                    Ширина:
                    <input type="number" placeholder="Min" value={this.state.minWidth} onChange={this.handleMinWidthChange} />
                    <input type="number" placeholder="Max" value={this.state.maxWidth} onChange={this.handleMaxWidthChange} />
                  </label>
                  <label>
                    Высота:
                    <input type="number" placeholder="Min" value={this.state.minHeight} onChange={this.handleMinHeightChange} />
                    <input type="number" placeholder="Max" value={this.state.maxHeight} onChange={this.handleMaxHeightChange} />
                  </label>
                  <label>
                    Глубина:
                    <input type="number" placeholder="Min" value={this.state.minDepth} onChange={this.handleMinDepthChange} />
                    <input type="number" placeholder="Max" value={this.state.maxDepth} onChange={this.handleMaxDepthChange} />
                  </label>
                </div>
              )}
            </div>

   

                    <div className="aside">
                      <h3 className="aside-title">Цена</h3>
                      <div className="price-filter">
                        <div className="input-number price-min">
                          <input type="number" value={minPrice} onChange={this.handleMinPriceChange} />
                          <span className="qty-up">+</span>
                          <span className="qty-down">-</span>
                        </div>
                        <span>-</span>
                        <div className="input-number price-max">
                          <input type="number" value={maxPrice} onChange={this.handleMaxPriceChange} />
                          <span className="qty-up">+</span>
                          <span className="qty-down">-</span>
                        </div>
                      </div>
                    </div>

          
             
                    {/* Фильтры */}
                    {allFilters.map(f => (
                      <div className="aside" key={f.key}>
                        <h3
                          className="aside-title"
                          onClick={() => this.toggleFilter(f.title || f.key)}
                          style={{ cursor: "pointer" }}
                        >
                          {f.title || f.key} {this.state.expandedFilters[f.title || f.key] ? "▲" : "▼"}
                        </h3>

                        {this.state.expandedFilters[f.title || f.key] && (
                          <>
                            {/* Если есть render — это bedFilters */}
                            {f.render ? (
                              f.render()
                            ) : (
                              <div className="checkbox-filter">
                                {Object.entries(f.items).map(([id, name]) => (
                                  <label key={id} className="checkbox-item">
                                    <input
                                      type="checkbox"
                                      value={id}
                                      checked={f.selected.includes(id)}
                                      onChange={() => f.handler(id)}
                                    />
                                    {name}
                                  </label>
                                ))}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    ))}

                  </div>

           
                </aside>

                    {/* Overlay */}
                      {this.state.filtersOpen && (
                        <div
                          className="category-sidebar-overlay"
                          onClick={this.toggleFilters} // закрытие при клике
                        ></div>
                      )}

                        {/* GRID ПРОДУКТОВ С ФИЛЬТРАМИ И СОРТИРОВКОЙ */}
                        <div className="category-products-wrapper">
                             <button
                                className="filters-toggle-btn mobile-only"
                                onClick={this.toggleFilters}
                                aria-expanded={this.state.filtersOpen}
                              >
                                {this.state.filtersOpen ? "Скрыть фильтры ▲" : "Показать фильтры ▼"}
                              </button>


                          {/* Фильтры и сортировка */}
                          <div className="category-products-controls">
                            <div className="sort-show-controls">
                              <label>
                                <select className="input-select" onChange={this.handleSortChange}>
                                  <option value="price-asc">Цена: от Низкой к высокой</option>
                                  <option value="price-desc">Цена: от Высокой к низкой</option>
                                </select>
                              </label>
                              <label>
                                количество на странице:
                                <select className="input-select" onChange={this.handleItemsPerPageChange}>
                                  <option value="20">20</option>
                                  <option value="50">50</option>
                                </select>
                              </label>
                            </div>
                            {/* Активные фильтры */}
                                <div className="active-filters-container">
                                <div className="reset-button-wrapper">
                                  {allFilters.some(f => {
                                    const key = f.key;
                                    return key === "storageNiche"
                                      ? this.state.storageNiche !== null
                                      : Array.isArray(this.state[key]) && this.state[key].length > 0;
                                  }) && (
                                    <button className="filter-chip reset-all" onClick={this.handleResetFilter}>
                                      Сбросить все ✕
                                    </button>
                                  )}
                                </div>
                              <div className="active-filters">
                                {allFilters.flatMap(f => {
                                  const { key, items, handler } = f;

                                  // Если значение в state массив — обычные фильтры
                                  if (Array.isArray(this.state[key])) {
                                    return this.state[key].map(id => (
                                      <button
                                        key={`${key}-${id}`}
                                        className="filter-chip"
                                        onClick={() => handler(id)}
                                      >
                                        {items[id]} ✕
                                      </button>
                                    ));
                                  }

                                  // Отдельно для storageNiche
                                  if (key === "storageNiche" && this.state.storageNiche !== null) {
                                    return (
                                      <button
                                        key={key}
                                        className="filter-chip"
                                        onClick={() => this.handleStorageNicheFilter(null)}
                                      >
                                        {this.state.storageNiche ? "With Storage Niche" : "Without Storage Niche"} ✕
                                      </button>
                                    );
                                  }

                                  return [];
                                })}


                                        {/* Фильтры кровати */}
                                        {bedFilters.flatMap(f => {
                                          const key = f.key;
                                          const value = this.state[key];
                                          if (value !== null && value !== undefined && value !== "") {
                                            return (
                                              <button
                                                key={key}
                                                className="filter-chip"
                                                onClick={() => this.setState({ [key]: "" })} // сброс конкретного bed фильтра
                                              >
                                                {f.key}: {value} ✕
                                              </button>
                                            );
                                          }
                                          return [];
                                        })}

                              </div>

                            </div>
                          </div>

            
                            {/* GRID ПРОДУКТОВ */}
                          <div className="category-products">
                            {paginatedProducts.length > 0 ? (
                              paginatedProducts.map((product) => (
                                <div className="product-card" key={product.id}>
                                  <div className="product-img">
                                    <Link to={`/products/${product.slug}/variant/${product.first_variant?.slug ?? ""}`}>
                                      <img src={product.first_variant?.photo ?? product.photo ?? ""} alt={product.name} />
                                    </Link>
                                    <div className="product-label">
                                      {product.first_variant?.discount > 0 && (
                                        <span className="sale">-{product.first_variant.discount}%</span>
                                      )}
                                    </div>
                                  </div>

                                    <div className="product-body">
                                      <div className="product-info">
                                        <h3 className="product-name">
                                          <Link to={`/products/${product.slug}/variant/${product.first_variant?.slug ?? ""}`}>
                                            {product.name}
                                          </Link>
                                        </h3>
                                        <div className="product-price-wrapper">
                                          <h4 className="product-price">
                                            ₴ {product.first_variant?.price ?? "-"}
                                            {product.first_variant?.discount > 0 && (
                                              <del className="product-old-price">₴ {product.first_variant?.original_price ?? "-"}</del>
                                            )}
                                          </h4>
                                        </div>
                                      </div>

                          <div className="product-btns">
                        <div className="btn-wrapper">
                          <button className="icon-btn" onClick={() => this.handleToggleWishlist(product)}>
                            <i className={`fa ${this.context.wishlist.some(w => w.product_variant.id === product.first_variant?.id) ? "fa-heart" : "fa-heart-o"}`} />
                          </button>
                          {product.addedWishlist && <span className="cart-popup">{product.addedWishlist}</span>}
                        </div>

                        <div className="btn-wrapper">
                          <button className="icon-btn" onClick={() => this.handleCompare(product)}>
                            <i className="fa fa-exchange" />
                          </button>
                          {product.addedCompare && <span className="cart-popup">{product.addedCompare}</span>}
                        </div>


                          <div className="btn-wrapper">
                            <button className="icon-btn" onClick={() => this.handleAddToCart(product)}>
                              <i className="fa fa-shopping-cart" />
                            </button>
                          {product.addedCart && <span className="cart-popup">{product.addedCart}</span>}
                          </div>
                        </div>

                        </div>

                                    </div>
                                ))
                              ) : (
                                <div>No products found for selected filters.</div>
                              )}
                            </div>


                      {/* Пагинация и количество товаров */}
                      <div className="category-products-footer">
                        <span className="store-qty">
                          Страница {start + 1}-{Math.min(end, products.length)} of {products.length} продуктов
                        </span>
                        <div className="store-pagination">
                          <button onClick={() => this.handlePageChange(currentPage - 1)} disabled={currentPage === 1}>
                            Предыдущая
                          </button>
                          <button onClick={() => this.handlePageChange(currentPage + 1)} disabled={end >= products.length}>
                            Вперед
                          </button>
                        </div>
        </div>
      </div>
    </div>
  </div>
</>
);

    }
  }
// export default ProductList;
export default CategoryProducts;