

import React, { Component } from "react";
import ProductsService from "../services/ProductService";
import { Link } from 'react-router-dom';



class AllCategories extends Component {
//Апи категорий 
// компонент который выводит все категории
  // This component not finished
  constructor(props) {
    super(props);
    this.state = {
      categories: [],
      loaded: false,
      placeholder: 'Loading',
    };
    this.productsService = new ProductsService();
  }

  componentDidMount() {
    this.productsService.getCategory()
      .then(data => {
        this.setState(() => {
          return {
            categories: data,
            loaded: true,
          };
        });
      })
      .catch(error => {
        console.log('Error fetching category:', error);
        this.setState(() => {
          return {
            placeholder: 'Something went wrong!',
          };
        });
      });
  }
  
  render(){
    const { categories, loaded, placeholder } = this.state;
  
    if (!loaded) {
      return <div>{placeholder}</div>;
    }
    if (categories.length === 0) {
      return <div>No categories available</div>;
    }
    return (
      <>
      

						{/* <!-- store products --> */}
            <div className="container all-categories-wrapper mt-7 mb-4">
                <div className="all-categories-grid pt-3 pb-5">
                  {categories.map(category => (
                    <div className="all-categories-item" key={category.slug}>
                      <Link to={`/products/?category=${category.slug}`}>
                        <img src={category.photo} alt={category.name} />
                      </Link>
                      <h5 className="card-title mt-2">{category.name}</h5>
                    </div>
                  ))}
                </div>
              </div>

      </>
    )
  }
}

export default AllCategories;
