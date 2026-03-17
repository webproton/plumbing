import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const Breadcrumb = () => {
  const location = useLocation();
  const pathnames = location.pathname.split('/').filter(x => x);

  const breadcrumbs = [
    { name: 'Home', to: '/' },
    { name: 'Cart', to: '/cart' },
    ...pathnames.map((value, index) => {
      const to = `/${pathnames.slice(0, index + 1).join('/')}`;
      return { name: decodeURIComponent(value), to };
    }),
    { name: 'Checkout', to: '/checkout' },
  ];

  return (
    <div id="breadcrumb" className="section">
      <div className="container">
        <div className="row">
          <div className="col-md-12">
            <ul className="breadcrumb-tree">
              {breadcrumbs.map((breadcrumb, index) => (
                <li key={index} className={index === breadcrumbs.length - 1 ? 'active' : ''}>
                  {index === breadcrumbs.length - 1 ? (
                    breadcrumb.name
                  ) : (
                    <Link to={breadcrumb.to}>{breadcrumb.name}</Link>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Breadcrumb;
