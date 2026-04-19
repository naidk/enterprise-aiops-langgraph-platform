import logging

def handle_payment_request(request):
    try:
        # Add null check for request data
        if request is None or request.data is None:
            logging.error("Invalid request data")
            return {"error": "Invalid request data"}, 400
        
        # Process payment request
        payment_data = request.data.get("payment_data")
        if payment_data is None:
            logging.error("Payment data is missing")
            return {"error": "Payment data is missing"}, 400
        
        # Add proper error handling for large requests
        if len(payment_data) > 1000000:  # arbitrary large size
            logging.error("Request is too large")
            return {"error": "Request is too large"}, 413
        
        # Continue with payment processing
        # ...
    except Exception as e:
        logging.error(f"Error handling payment request: {str(e)}")
        return {"error": "Internal Server Error"}, 500