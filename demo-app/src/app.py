from flask import Flask, jsonify
import os, socket

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({
        "app": "demo-app",
        "version": os.getenv("APP_VERSION", "v1"),
        "hostname": socket.gethostname(),
        "message": "GitOps pipeline: Kubero Build → Harbor → ArgoCD → Kubernetes + Istio"
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
