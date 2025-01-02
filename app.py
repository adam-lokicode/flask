import os
import json
from flask import Flask, request, abort
from flask_cors import CORS

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

# Configure Sentry SDK with enhanced features
sentry_sdk.init(
    dsn="https://b4516fa78e87840d988dc07f799f9cae@o4505281038319616.ingest.us.sentry.io/4508560575758336",
    integrations=[
        FlaskIntegration(),
        LoggingIntegration(level=None, event_level="ERROR")  # Automatically capture logging errors
    ],
    release=os.environ.get("VERSION", "development"),
    environment=os.environ.get("ENVIRONMENT", "local"),
    traces_sample_rate=1.0,  # Enable performance monitoring (100% of traces)
    profiles_sample_rate=1.0,  # Enable profiling (100% sampling rate)
    send_default_pii=True  # Send user PII data (e.g., user email)
)

app = Flask(__name__)
CORS(app)

# Inventory for the store
Inventory = {
    "wrench": 1,
    "nails": 1,
    "hammer": 1
}

@app.route('/handled', methods=['GET'])
def handled_exception():
    """Example of a handled exception."""
    try:
        '2' + 2  # This will cause a TypeError
    except Exception as err:
        sentry_sdk.capture_exception(err)  # Send the exception to Sentry
        abort(500)  # Return a 500 response

    return 'Success'

@app.route('/unhandled', methods=['GET'])
def unhandled_exception():
    """Example of an unhandled exception."""
    obj = {}
    # This will raise a KeyError
    return obj['keyDoesntExist']

def process_order(cart):
    """Process an order and update inventory."""
    global Inventory
    temp_inventory = Inventory.copy()
    for item in cart:
        item_id = item['id']
        if temp_inventory.get(item_id, 0) <= 0:
            raise Exception(f"Not enough inventory for {item_id}")
        else:
            temp_inventory[item_id] -= 1
            print(f"Success: {item_id} was purchased, remaining stock is {temp_inventory[item_id]}")
    Inventory = temp_inventory

@app.before_request
def sentry_event_context():
    """Add context to Sentry events."""
    global Inventory

    # Add request-level tags and extra data to the Sentry scope
    with sentry_sdk.configure_scope() as scope:
        # Attach user info if available
        if request.data:
            try:
                order = json.loads(request.data)
                scope.set_user({"email": order.get("email")})
            except (ValueError, KeyError):
                pass  # Ignore if request data cannot be parsed

        # Add custom tags
        transaction_id = request.headers.get("X-Transaction-ID", "unknown")
        session_id = request.headers.get("X-Session-ID", "unknown")
        scope.set_tag("transaction_id", transaction_id)
        scope.set_tag("session_id", session_id)

        # Add custom extra data
        scope.set_extra("inventory", Inventory)

@app.route('/checkout', methods=['POST'])
def checkout():
    """Handle the checkout process."""
    try:
        order = json.loads(request.data)
        print(f"Processing order for: {order['email']}")

        cart = order.get("cart", [])
        process_order(cart)

        return "Success"
    except Exception as err:
        # Capture the exception and include additional context
        with sentry_sdk.push_scope() as scope:
            scope.set_extra("request_data", request.data.decode("utf-8"))
            sentry_sdk.capture_exception(err)
        abort(500)

if __name__ == "__main__":
    # Run the Flask app in development mode
    app.run(debug=True, host="0.0.0.0", port=5000)
