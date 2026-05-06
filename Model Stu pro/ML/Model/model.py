import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load KB
with open("Dataset/data.json", "r", encoding="utf-8") as f:
    KB = json.load(f)

class ChatbotModel:
    def __init__(self):
        self.sentences = []
        self.intent_map = []

        for intent, data in KB.items():
            for tag in data["tags"]:
                self.sentences.append(tag)
                self.intent_map.append(intent)

        self.vectorizer = TfidfVectorizer()
        self.vectors = self.vectorizer.fit_transform(self.sentences)

    def predict_intent(self, user_input):
        user_vec = self.vectorizer.transform([user_input])
        similarity = cosine_similarity(user_vec, self.vectors)

        best_index = similarity.argmax()
        score = similarity[0][best_index]

        if score < 0.2:
            return None

        return self.intent_map[best_index]

    def get_response(self, user_input):
        intent = self.predict_intent(user_input.lower())

        if not intent:
            return "❌ Sorry, I didn't understand. Try asking about fees, admissions, timetable..."

        return KB[intent]["html"]


chatbot = ChatbotModel()