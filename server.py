import json
import os
from flask import Flask, jsonify, request
from new_order import OrderManager

app = Flask(__name__)
order_manager = OrderManager()

@app.route("/upload", methods=["POST"])
def upload_photo():
    role = request.args.get("role", "unknown")
    order_id = request.args.get("order_id")
    image_data = request.data

    if not order_id:
        return jsonify({"error": "order_id is required"}), 400

    if role not in {"back", "side", "top"}:
        return jsonify({"error": "Invalid camera role"}), 400

    if not image_data:
        return jsonify({"error": "Empty image data"}), 400

    # Resolve the actual order directory instead of assuming
    # the order belongs to today's batch directory.
    order_path = order_manager.get_order_path(order_id)

    if order_path is None:
        return jsonify({"error": "Unknown order_id"}), 404

    file_name = f"{role}.jpg"
    file_path = os.path.join(order_path, file_name)

    try:
        with open(file_path, "wb") as f:
            f.write(image_data)

        print(
            f"Saved [{role}] snapshot to: "
            f"{file_path} ({len(image_data)} bytes)"
        )

        manifest_path = os.path.join(
            order_path,
            "order_manifest.json"
        )

        if os.path.exists(manifest_path):
            with open(manifest_path, "r+") as f:
                data = json.load(f)

                data.setdefault("photos", [])

                if file_name not in data["photos"]:
                    data["photos"].append(file_name)

                if len(data["photos"]) >= 3:
                    data["stage"] = "snapshot_complete"

                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()

        return jsonify({
            "status": "success",
            "saved_path": file_path,
            "order_id": order_id,
            "role": role
        }), 200

    except OSError as error:
        print(f"Failed to save [{role}] snapshot: {error}")

        return jsonify({
            "error": "Failed to save image"
        }), 500

    except json.JSONDecodeError:
        print(f"Invalid manifest JSON for order: {order_id}")

        return jsonify({
            "error": "Invalid order manifest"
        }), 500

def run_server():
    app.run(
        host="0.0.0.0", # makes Flask accessible not just to PC but also to the slaves
        port=5000,
        debug=False,
        use_reloader=False
    )