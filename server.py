import json, os
from flask import Flask, jsonify, request

from new_order import OrderManager

app = Flask(__name__)
order_manager = OrderManager()  # Use or reference your OrderManager instance


@app.route("/upload", methods=["POST"])
def upload_photo():
    role = request.args.get("role", "unknown")
    order_id = request.args.get("order_id")
    image_data = request.data

    if not order_id:
        return jsonify({"error": "order_id is required"}), 400

    order_path = os.path.join(
        order_manager.get_current_batch_directory(), order_id
    )
    if not os.path.isdir(order_path):
        return jsonify({"error": "Unknown order_id"}), 404

    file_name = f"{role}.jpg"
    file_path = os.path.join(order_path, file_name)

    with open(file_path, "wb") as f:
        f.write(image_data)

    print(
        f"Saved [{role}] snapshot to: {file_path} ({len(image_data)} bytes)"
    )

    # Update manifest photo list
    manifest_path = os.path.join(
        order_path, "order_manifest.json"
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

    return jsonify({"status": "success", "saved_path": file_path, "order_id": order_id}), 200