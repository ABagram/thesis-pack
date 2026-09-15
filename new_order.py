import time, json, os

# Define your base root directory where orders are stored (adjust as needed for your project)
ORDERS_BASE_DIRECTORY = os.path.abspath("orders") 

def create_new_order(self):
    """Generates a unique order ID and creates its directory structure and manifest."""
    if not os.path.exists(ORDERS_BASE_DIRECTORY):
        os.makedirs(ORDERS_BASE_DIRECTORY)

    # Generate a unique order ID based on timestamp (e.g., order_20260607_143022)
    order_id = f"order_{time.strftime('%Y%m%d_%H%M%S')}"
    order_path = os.path.join(ORDERS_BASE_DIRECTORY, order_id)
    
    try:
        os.makedirs(order_path, exist_ok=True)
        
        # Initialize the order manifest with the starting stage
        manifest_data = {
            "order_id": order_id,
            "stage": "snapshot_pending"
        }
        manifest_path = os.path.join(order_path, "order_manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=4)
            
        print(f"New order directory created: {order_path}")
        
        # Switch the UI view to the pipeline page and load this order into view
        self.show_view("pipeline")
        self.update_display_details(order_id, ORDERS_BASE_DIRECTORY)
        
        return order_id, ORDERS_BASE_DIRECTORY
    except Exception as e:
        print(f"Failed to create order directory: {e}")
        return None, None

def handle_hardware_order_triggered(self):
        """Triggered when the physical button on the ESP is pressed."""
        print("Physical order button pressed on ESP! Creating new order...")
        
        # 1. Create the order folder and manifest on the PC
        order_id, base_dir = self.create_new_order()
        
        if order_id:
            # 2. Optionally start tracking or notify connected slaves/pipeline
            print(f"Active order initialized: {order_id}")
            
            # If you want it to immediately start your camera capture pipeline simulation:
            # self.start_mock_pipeline_animation()