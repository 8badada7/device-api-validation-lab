from flask import Flask, jsonify, request

app = Flask(__name__)
connected = False
registers = {
    100: 1234,
    101: 5678,
}


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/connect")
def connect():
    global connected
    connected = True
    return jsonify({"connected": connected}), 200


@app.post("/disconnect")
def disconnect():
    global connected
    connected = False
    return jsonify({"connected": connected}), 200


@app.get("/read")
def read():
    if not connected:
        return jsonify({"error": "not_connected"}), 409

    address_text = request.args.get("address")
    if (
        not address_text
        or not address_text.isascii()
        or not address_text.isdecimal()
    ):
        return jsonify({"error": "invalid_address"}), 400

    # Compare normalized decimal strings to avoid int conversion length limits.
    normalized_address = address_text.lstrip("0") or "0"
    for address, value in registers.items():
        if str(address) == normalized_address:
            return jsonify({"address": address, "value": value}), 200

    return jsonify({"error": "register_not_found"}), 404


@app.post("/write")
def write():
    if not connected:
        return jsonify({"error": "not_connected"}), 409

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_payload"}), 400

    address = payload.get("address")
    if type(address) is not int or address < 0:
        return jsonify({"error": "invalid_address"}), 400
    if address not in registers:
        return jsonify({"error": "register_not_found"}), 404

    value = payload.get("value")
    if type(value) is not int or not 0 <= value <= 65535:
        return jsonify({"error": "invalid_value"}), 400

    registers[address] = value
    return jsonify({"address": address, "value": registers[address]}), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)
