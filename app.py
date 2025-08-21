import os
import time
from flask import Flask, render_template, request, send_file, jsonify, abort
from werkzeug.utils import secure_filename
from PIL import Image
from stegano import lsb

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload cap
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXT = {"png", "jpg", "jpeg"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

@app.route("/")
def index():
    return render_template("index.html")

@app.errorhandler(413)
def too_large(e):
    return "File too large. Max 16 MB.", 413

@app.route("/encode", methods=["POST"])
def encode():
    if "image" not in request.files:
        return abort(400, "No file provided")
    if "message" not in request.form:
        return abort(400, "No message provided")

    file = request.files["image"]
    message = request.form["message"].strip()

    if file.filename == "":
        return abort(400, "Empty filename")
    if not allowed_file(file.filename):
        return abort(400, "Only PNG/JPG/JPEG allowed")

    # Save original upload
    safe = secure_filename(file.filename)
    stamp = int(time.time() * 1000)
    src_path = os.path.join(UPLOAD_FOLDER, f"{stamp}_{safe}")
    file.save(src_path)

    # Ensure image is loadable
    try:
        _ = Image.open(src_path).convert("RGBA")
    except Exception:
        try:
            os.remove(src_path)
        except Exception:
            pass
        return abort(400, "Invalid image")

    # Hide message
    out_path = os.path.join(UPLOAD_FOLDER, f"secret_{stamp}.png")
    try:
        secret = lsb.hide(src_path, message)
        secret.save(out_path)
    except Exception as e:
        return abort(500, f"Encoding failed: {e}")
    finally:
        # Optional cleanup of the original upload
        try:
            os.remove(src_path)
        except Exception:
            pass

    # Return the stego image as download
    return send_file(out_path, as_attachment=True, download_name="secret.png", mimetype="image/png")

@app.route("/decode", methods=["POST"])
def decode():
    if "image" not in request.files:
        return abort(400, "No file provided")

    file = request.files["image"]
    if file.filename == "":
        return abort(400, "Empty filename")
    if not allowed_file(file.filename):
        return abort(400, "Only PNG/JPG/JPEG allowed")

    safe = secure_filename(file.filename)
    stamp = int(time.time() * 1000)
    src_path = os.path.join(UPLOAD_FOLDER, f"{stamp}_{safe}")
    file.save(src_path)

    try:
        msg = lsb.reveal(src_path)
        if msg is None:
            # Graceful response instead of exception
            return jsonify({"error": "No hidden message found"}), 200
        return jsonify({"message": msg}), 200
    except Exception as e:
        return jsonify({"error": f"Decoding failed: {e}"}), 500
    finally:
        try:
            os.remove(src_path)
        except Exception:
            pass

if __name__ == "__main__":
    # For production, run with a WSGI server (gunicorn) and debug=False
    app.run(host="0.0.0.0", port=5000, debug=True)
