# REPLACE contents of new_order.py WITH:
import os
import json
import time
from datetime import datetime

class OrderManager:
    _instance = None
    orders_root: str
    active_batch_directory: str
    active_order_id: str | None
    active_order_path: str | None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OrderManager, cls).__new__(cls)
            cls._instance.active_order_id = None
            cls._instance.active_order_path = None
            cls._instance.orders_root = os.path.join(
                os.path.expanduser("~"), "Desktop", "Orders_Root", "orders"
            )
            cls._instance.active_batch_directory = cls._instance.get_current_batch_directory()
        return cls._instance

    def set_batch_directory(self, path):
        if path and os.path.exists(path):
            self.active_batch_directory = path

    def get_current_batch_directory(self, current_time=None):
        current_time = current_time or datetime.now()
        month_directory = current_time.strftime("%m-%Y")
        day_directory = current_time.strftime("%m-%d-%Y")
        return os.path.join(self.orders_root, str(current_time.year), month_directory, day_directory)

    def create_new_order(self, order_id=None, current_time=None):
        current_time = current_time or datetime.now()
        self.active_batch_directory = self.get_current_batch_directory(current_time)
        os.makedirs(self.active_batch_directory, exist_ok=True)
        order_id = order_id or f"order_{current_time.strftime('%Y%m%d_%H%M%S')}"
        order_path = os.path.join(self.active_batch_directory, order_id)

        try:
            os.makedirs(order_path, exist_ok=True)
            self.active_order_id = order_id
            self.active_order_path = order_path

            manifest_data = {
                "order_id": order_id,
                "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "stage": "order_capture",
                "photos": [],
                "expected_photos": ["back.jpg", "side.jpg", "top.jpg"],
            }
            manifest_path = os.path.join(order_path, "order_manifest.json")
            with open(manifest_path, "w") as f:
                json.dump(manifest_data, f, indent=4)

            print(f"New order directory created: {order_path}")
            return order_id, order_path
        except Exception as e:
            print(f"Failed to create order directory: {e}")
            return None, None
    
    def get_order_path(self, order_id):
        """
        Find an existing order directory by order ID.

        First checks the currently active order, then the current batch
        directory, then searches the entire orders root.
        """
        if not order_id:
            return None

        # Fast path: this is the order currently being created/processed.
        if (
            self.active_order_id == order_id
            and self.active_order_path
            and os.path.isdir(self.active_order_path)
        ):
            return self.active_order_path

        # Second: check the current batch directory.
        batch_directory = self.active_batch_directory

        if os.path.isdir(batch_directory):
            order_path = os.path.join(batch_directory, order_id)

            if os.path.isdir(order_path):
                return order_path

        # Final fallback: search all year/month/day directories.
        if not os.path.isdir(self.orders_root):
            return None

        for root, dirs, files in os.walk(self.orders_root):
            if order_id in dirs:
                order_path = os.path.join(root, order_id)

                if os.path.isdir(order_path):
                    return order_path

        return None

    def delete_order(self, order_id):
        """
        Delete an order directory by order ID.

        Returns True if the order was deleted successfully,
        otherwise False.
        """
        if not order_id:
            return False

        order_path = self.get_order_path(order_id)

        if order_path is None:
            print(f"Cannot delete order. Unknown order ID: {order_id}")
            return False

        try:
            import shutil

            shutil.rmtree(order_path)

            print(f"Deleted cancelled order: {order_path}")

            # Clear active-order information if this was the active order.
            if self.active_order_id == order_id:
                self.active_order_id = None
                self.active_order_path = None

            return True

        except OSError as error:
            print(
                f"Failed to delete order "
                f"{order_id}: {error}"
            )
            return False
        
# Shared singleton instance
order_manager = OrderManager()