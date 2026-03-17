

import axiosInstance from './axiosInstance';



export default class ProductsService{
  // this router service with django

  async getWishlist() {
    try {
      const response = await axiosInstance.get('/api/wishlist/');
      return response.data;
    } catch (error) {
      console.error("Ошибка загрузки wishlist:", error.response?.data || error.message);
      console.error("Status:", error.response?.status);
      throw new Error('Ошибка загрузки wishlist');
    }
  }

  // Добавить товар в wishlist
  async addToWishlist(variantId) {
      try {

        const response = await axiosInstance.post("/api/wishlist/", {
          product_variant_id: variantId,
        });

        return response.data;
      } catch (error) {
        console.error("Ошибка при добавлении в wishlist:", error.response?.data || error.message);
        console.error("Status:", error.response?.status);
        console.error("Ошибка при добавлении в wishlist", error);
        throw error;
      }
    }

  // Удалить товар из wishlist
  async removeFromWishlist(wishlistId) {
        try {
          const response = await axiosInstance.delete(`/api/wishlist/${wishlistId}/`);

          // await axiosInstance.delete(`/api/wishlist/${wishlistId}/`);
          return response.data;

        } catch (error) {
          console.error("Ошибка при удалении из wishlist:", error);
          throw error;
        }
      }

  async clearWishlist() {
    try {
      const response = await axiosInstance.post('/api/wishlist/clear/');
      return response.data;
    } catch (error) {
      console.error("Ошибка при очистке wishlist на сервере:", error);
      throw error;
    }
  }

  async mergeWishlist(items) {
    try {
      const response = await axiosInstance.post("/api/wishlist/merge/", items);
      return response.data;
    } catch (error) {
      console.error("Ошибка при merge wishlist:", error);
      throw error;
    }
  }

  async saveWishlist(wishlist) {
    try {
      const response = await axiosInstance.put('/api/wishlist/bulk-update/', wishlist);
      return response.data;
    } catch (error) {
      console.error("Ошибка при сохранении wishlist:", error);
      throw new Error('Ошибка сохранения wishlist');
    }
  }

	
  async getProducts() {
    //get list products
    try {

      const response = await axiosInstance.get('/api/products/');
      return response.data;
    } catch (error) {
      console.error('Error fetching products:', error);
      throw error;
    }
  }

  async getNewProducts() {
    try {
      const response = await axiosInstance.get('/api/new_products/');
      return response.data;
    } catch (error) {
      console.error('Error fetching new products:', error);
      throw error;
    }
  }

  async getAllCategories() {
  try {
    const response = await axiosInstance.get('/api/category/');
    return response.data;
  } catch (error) {
    console.error('Ошибка загрузки категорий:', error);
    return [];
  }
}
  
  async getCategory() {
    try {
      const response = await axiosInstance.get('/api/category/');
      return response.data;
    } catch (error) {
      console.error('Error fetching categories:', error);
      throw error;
    }
  }

  async searchProducts(query) {
        try {
          const response = await axiosInstance.get('/api/products/', {
            params: { search: query }
          });
          return response.data.results || response.data; // в зависимости от пагинации
        } catch (error) {
          console.error('Ошибка поиска:', error);
          throw error;
        }
      }
  
async getProductsByCategory(categorySlug, minPrice, maxPrice, sort, fetchAll = false) {
  try {
    const params = new URLSearchParams({ 
      category: categorySlug,
      o: sort,
      min_price: minPrice,
      max_price: maxPrice,
    });

    let url = `/api/products/?${params.toString()}`;
    let allResults = [];

    while (url) {
      const response = await axiosInstance.get(url);
      const data = response.data;

      if (fetchAll) {
        allResults = allResults.concat(data.results || []);
        url = data.next; // пока есть следующая страница — качаем
      } else {
        return data; // если fetchAll = false — выходим сразу
      }
    }

    return allResults;

  } catch (error) {
    console.error('Error fetching category:', error);
    throw error;
  }
}



  async getCategoryBySlug(slug, productNameFilter) {
   
    try {
      const params = new URLSearchParams({ 
        }); // Include search term in params
      const config = {
        // headers: {
        //   'Cache-Control': 'no-cache'
        // },
        params,
      };


      const response = await axiosInstance.get(`/api/category/${slug}/`,config)
      return response.data;
      
    } catch (error) {
      console.error('Error fetching category:', error);
      throw error;
    }
  }

  async fetchNextPage(pageUrl) {
    try {
      const config = {
        // headers: {
        //   'Cache-Control': 'no-cache',
        // },
      };

      const response = await axiosInstance.get(pageUrl, config);
      return response.data;

    } catch (error) {
      console.error('Error fetching next page:', error);
      throw error;
    }
  }

  async fetchPreviousPage(pageUrl) {
    try {
      const config = {
        // headers: {
        //   'Cache-Control': 'no-cache',
        // },
      };

      const response = await axiosInstance.get(pageUrl, config);
      return response.data;

    } catch (error) {
      console.error('Error fetching previous page:', error);
      throw error;
    }
  }

  async getProductsByURL(link){

    
		return axiosInstance.get(link).then(response => response.data);
	}

  async getProduct(productSlug) {
    try {
      const response = await axiosInstance.get(`/api/products/${productSlug}/`);
      return response.data;
    } catch (error) {
      console.error('Error fetching product:', error.response || error.message || error);
      throw error;
    }
  }
  


  async fetchData(endpoint, config = {}) {

      try {
        const response = await axiosInstance.get(endpoint, {
          // headers: {
          //   'Cache-Control': 'no-cache',
          // },
          ...config,
        });

        return response.data;
      } catch (error) {
        console.error('Error fetching data:', error);
        throw error; // Можно добавить уведомление об ошибке
      }
    }
  }

