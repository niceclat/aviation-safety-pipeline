"""
NLP package for narrative text analysis.

Three layers of analysis, each modular and independent:
    1. regex_categorizer  — rule-based failure categorization (explainable)
    2. tfidf_analyzer     — term frequency analysis per model (distinguishing)
    3. embedding_analyzer — sentence embeddings + FAISS (semantic clustering)

Each module can run standalone or as part of the silver pipeline.
"""
