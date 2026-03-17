		
    import React, { Component } from "react";


    
    
    class Newsletter extends Component {
      // This component not finished
      render() {
        return (
          <>
        
    {/* <!-- NEWSLETTER --> */}
		<div id="newsletter" className="section">
			{/* <!-- container --> */}
			<div className="container">
				{/* <!-- row --> */}
				<div className="row">
					<div className="col-md-12">
						<div className="newsletter">
							<p>Sign Up for the <strong>NEWSLETTER</strong></p>
							<form>
								<input className="input" type="email" placeholder="Enter Your Email" />
								<button className="newsletter-btn"><i className="fa fa-envelope"></i> Subscribe</button>
							</form>
							<ul className="newsletter-follow">
								<li>
									<a href="#"><i className="fa fa-facebook"></i></a>
								</li>
								<li>
									<a href="#"><i className="fa fa-twitter"></i></a>
								</li>
								<li>
									<a href="#"><i className="fa fa-instagram"></i></a>
								</li>
								<li>
									<a href="#"><i className="fa fa-pinterest"></i></a>
								</li>
							</ul>
						</div>
					</div>
				</div>
				{/* <!-- /row --> */}
			</div>
			{/* <!-- /container --> */}
		</div>
		{/* <!-- /NEWSLETTER --> */}

          </>
        );
      }
    }
    
    
    export default Newsletter;
    
