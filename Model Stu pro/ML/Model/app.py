from flask import Flask, render_template, request, jsonify
from model import chatbot

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    response = chatbot.get_response(user_message)
    return jsonify({"reply": response})

if __name__ == "__main__":
    app.run(debug=True)