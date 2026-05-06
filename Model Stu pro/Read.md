###
deep learning model like BERT—it’s a classical NLP model 

###

🧠 Model Used
👉 TF-IDF + Cosine Similarity
🔍 1. TF-IDF (Term Frequency–Inverse Document Frequency)

Used from:

from sklearn.feature_extraction.text import TfidfVectorizer
What it does:
Converts text (your tags + user input) into numerical vectors
Gives importance to meaningful words
Reduces weight of common words like “what”, “is”, “the”

👉 Example:

"fees structure" → [0.2, 0.8, 0.0, ...]
"hostel fees"   → [0.1, 0.7, 0.3, ...]
📐 2. Cosine Similarity

Used from:

from sklearn.metrics.pairwise import cosine_similarity
What it does:
Measures similarity between:
user input vector
stored tag vectors
Output:
0 → no similarity
1 → exact match
⚙️ 3. How the Model Works (Flow)
User Input
   ↓
Convert to vector (TF-IDF)
   ↓
Compare with all tag vectors
   ↓
Pick highest similarity
   ↓
Return corresponding intent
🧪 Example

User:

"what is the fee structure?"

Model compares with tags:

"fee" → 0.82
"fees" → 0.90  ✅ (highest)
"hostel" → 0.10

👉 Predicted intent = fees

📊 Accuracy
Typical: 90%–95%
Depends on:
quality of tags
variety of phrases
⚠️ Important Clarification

This is:
✔️ Machine Learning model (lightweight NLP)
❌ Not a deep learning / neural network model

🆚 Comparison
Model	Used Here?	Accuracy	Complexity
Keyword Matching	❌	80–90%	Very Easy
TF-IDF + Cosine	✅	90–95%	Easy
BERT / Transformers	❌	95–99%	Hard
🚀 If You Want a Better Model

You can upgrade to:

🔥 Sentence Transformers
from sentence_transformers import SentenceTransformer
Understands meaning (not just keywords)
Handles:
"cost of college"
"how much should I pay"

👉 Accuracy: 95–99%

✅ Final Answer

👉 Your chatbot uses:

TF-IDF Vectorizer + Cosine Similarity (from scikit-learn)

If you want, I can upgrade your project to:

🤖 AI-powered chatbot (ChatGPT + your KB)
🧠 Deep learning model (BERT)
📊 Accuracy evaluation system

Just tell me 👍