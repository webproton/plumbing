// // src/api/wishlistService.js
// import axiosInstance from "./axiosInstance";

// export const getWishlist = () => axiosInstance.get("/api/wishlist/");
// export const addToWishlist = (variantId) => axiosInstance.post("/api/wishlist/", { product_variant: variantId });
// export const removeFromWishlist = (wishlistId) => axiosInstance.delete(`/api/wishlist/${wishlistId}/`);
// export const clearWishlist = () => axiosInstance.post("/api/wishlist/clear/");
// // export const mergeWishlist = (variantIds) => axiosInstance.post("/api/wishlist/merge/", variantIds);

// export const mergeWishlist = (items) => {
//   // items — массив объектов { product_variant_id: number }
//   return axiosInstance.post("/api/wishlist/merge/", items);
// };
