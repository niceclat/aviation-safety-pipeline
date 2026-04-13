"""
Sentence embedding + FAISS clustering for narrative analysis.

Generates dense vector embeddings using sentence-transformers, indexes them
with FAISS for fast similarity search, then clusters narratives to discover
failure patterns and detect anomalies.

Outputs:
    - cluster_id: semantic group assignment
    - anomaly_score: distance from nearest cluster centroid
    - embedding: dense vector (stored in pgvector for SQL-level search)
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Model loaded lazily on first use (heavy import)
_model = None
_faiss_index = None

# Default model — small, fast, good quality
DEFAULT_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # dimension for all-MiniLM-L6-v2


def _get_model(model_name: str = DEFAULT_MODEL):
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {model_name}")
            _model = SentenceTransformer(model_name)
            logger.info(f"Model loaded (dim={EMBEDDING_DIM})")
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
    return _model


@dataclass
class EmbeddingResult:
    """Result of embedding analysis for a batch of narratives."""
    embeddings: np.ndarray          # (n, dim) float32
    cluster_ids: np.ndarray         # (n,) int32
    anomaly_scores: np.ndarray      # (n,) float32
    n_clusters: int
    centroids: np.ndarray           # (k, dim) float32


def generate_embeddings(texts: list[str],
                        model_name: str = DEFAULT_MODEL,
                        batch_size: int = 64) -> np.ndarray:
    """Generate sentence embeddings for a list of texts.

    Args:
        texts: List of narrative strings.
        model_name: Sentence transformer model name.
        batch_size: Encoding batch size (tune for memory/speed).

    Returns:
        numpy array of shape (len(texts), EMBEDDING_DIM).
    """
    model = _get_model(model_name)

    # Replace empty/None with placeholder
    clean_texts = [t if t and t.strip() else "no narrative available" for t in texts]

    logger.info(f"Generating embeddings for {len(clean_texts):,} texts (batch_size={batch_size})")
    embeddings = model.encode(
        clean_texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,  # L2 normalize for cosine similarity
    )
    logger.info(f"Embeddings generated: shape={embeddings.shape}")
    return embeddings.astype(np.float32)


def cluster_embeddings(embeddings: np.ndarray,
                       n_clusters: Optional[int] = None,
                       min_cluster_size: int = 10) -> EmbeddingResult:
    """Cluster embeddings using FAISS k-means.

    Args:
        embeddings: (n, dim) float32 array.
        n_clusters: Number of clusters. Auto-computed if None.
        min_cluster_size: Minimum cluster size for auto k selection.

    Returns:
        EmbeddingResult with cluster assignments and anomaly scores.
    """
    try:
        import faiss
    except ImportError:
        raise ImportError("faiss-cpu not installed. Run: pip install faiss-cpu")

    n_samples, dim = embeddings.shape

    # Auto-select k: sqrt(n) capped at reasonable range
    if n_clusters is None:
        n_clusters = max(5, min(50, int(np.sqrt(n_samples))))
    n_clusters = min(n_clusters, n_samples)

    logger.info(f"Clustering {n_samples:,} embeddings into {n_clusters} clusters")

    # FAISS k-means
    kmeans = faiss.Kmeans(dim, n_clusters, niter=20, verbose=False, gpu=False)
    kmeans.train(embeddings)

    # Assign clusters and compute distances
    distances, cluster_ids = kmeans.index.search(embeddings, 1)
    distances = distances.flatten()
    cluster_ids = cluster_ids.flatten()

    # Anomaly score = distance to nearest centroid (higher = more anomalous)
    # Normalize to 0-1 range
    max_dist = distances.max() if distances.max() > 0 else 1.0
    anomaly_scores = (distances / max_dist).astype(np.float32)

    logger.info(
        f"Clustering complete: {n_clusters} clusters, "
        f"anomaly range [{anomaly_scores.min():.3f}, {anomaly_scores.max():.3f}]"
    )

    return EmbeddingResult(
        embeddings=embeddings,
        cluster_ids=cluster_ids.astype(np.int32),
        anomaly_scores=anomaly_scores,
        n_clusters=n_clusters,
        centroids=kmeans.centroids,
    )


def build_faiss_index(embeddings: np.ndarray) -> "faiss.IndexFlatIP":
    """Build a FAISS index for similarity search.

    Args:
        embeddings: (n, dim) L2-normalized float32 array.

    Returns:
        FAISS index ready for search.
    """
    import faiss

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # Inner product = cosine similarity (normalized)
    index.add(embeddings)
    logger.info(f"FAISS index built: {index.ntotal} vectors, dim={dim}")
    return index


def search_similar(index, query_embedding: np.ndarray,
                   k: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Find k most similar narratives to a query.

    Args:
        index: FAISS index.
        query_embedding: (1, dim) or (dim,) query vector.
        k: Number of results.

    Returns:
        (scores, indices) — similarity scores and row indices.
    """
    if query_embedding.ndim == 1:
        query_embedding = query_embedding.reshape(1, -1)
    scores, indices = index.search(query_embedding, k)
    return scores.flatten(), indices.flatten()
