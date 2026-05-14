from flask import Flask, jsonify
import os, socket, datetime

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({
        "app": "demo-app",
        "version": os.getenv("APP_VERSION", "v3"),
        "hostname": socket.gethostname(),
        "build": "Tekton CI → Harbor → ArgoCD GitOps → Kubernetes + Istio",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": os.getenv("APP_VERSION", "v3")})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
