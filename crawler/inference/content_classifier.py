import re

import joblib
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from gensim.models import KeyedVectors
from gensim.scripts.glove2word2vec import glove2word2vec
from gensim.test.utils import datapath, get_tmpfile


class ContentClassifier:
    """
    A classifier for predicting category based on content, website, and forum type.

    This class handles the loading of a GloVe model, a RandomForestClassifier model, and a OneHotEncoder.
    It provides functionality to preprocess text data and make predictions based on the content, website, and forum type.

    Usage:
    # Create an instance of the class
    classifier = ContentClassifier(glove_path, model_path, encoder_path)

    # Example data
    content = "Latest tech news and updates"
    website = "technews.com"
    forum_type = "Technology Discussions"

    # Make a prediction
    prediction = classifier.predict(content, website, forum_type)
    print("Prediction:", prediction)

    Parameters:
    - glove_path (str): Path to the GloVe model file.
    - model_path (str): Path to the saved RandomForestClassifier model file.
    - encoder_path (str): Path to the saved OneHotEncoder model file.
    """

    def __init__(self, glove_path, model_path, encoder_path):
        # Load models and encoder
        self.glove_model = self._load_glove_model(glove_path)
        self.model = joblib.load(model_path)
        self.encoder = joblib.load(encoder_path)

    def _load_glove_model(self, glove_path):
        # Load the GloVe model
        glove_file = datapath(glove_path)
        word2vec_glove_file = get_tmpfile("glove.6B.50d.word2vec.txt")
        glove2word2vec(glove_file, word2vec_glove_file)
        return KeyedVectors.load_word2vec_format(word2vec_glove_file)

    @staticmethod
    def _clean_text(text):
        # Clean and preprocess the text data
        if isinstance(text, str):
            text = BeautifulSoup(text, "html.parser").get_text()
            text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
            return text.lower()
        return ""

    def _text_to_embedding(self, text):
        # Convert text to embeddings using the GloVe model
        words = text.split()
        word_vectors = [
            self.glove_model[word]
            for word in words
            if word in self.glove_model.key_to_index
        ]
        if len(word_vectors) == 0:
            return np.zeros(self.glove_model.vector_size)
        return np.mean(word_vectors, axis=0)

    def _preprocess_data(self, content, website, forum_type):
        # Preprocess the input data and convert to features
        cleaned_content = self._clean_text(content)
        cleaned_forum_type = self._clean_text(forum_type)

        content_embedding = self._text_to_embedding(cleaned_content)
        forum_type_embedding = self._text_to_embedding(cleaned_forum_type)

        website_encoded = self.encoder.transform([[website]]).toarray()

        X_new = np.hstack(
            [
                website_encoded,
                content_embedding.reshape(1, -1),
                forum_type_embedding.reshape(1, -1),
            ]
        )
        return X_new

    def predict(self, content, website, forum_type):
        # Predict the category based on content, website, and forum type
        X_new = self._preprocess_data(content, website, forum_type)
        prediction = self.model.predict(X_new)
        return prediction[0]
