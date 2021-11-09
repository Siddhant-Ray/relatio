# MIT License

# Copyright (c) 2020-2021 ETH Zurich, Andrei V. Plamada
# Copyright (c) 2020-2021 ETH Zurich, Elliott Ash
# Copyright (c) 2020-2021 University of St.Gallen, Philine Widmer
# Copyright (c) 2020-2021 Ecole Polytechnique, Germain Gauthier

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import spacy
from numpy.linalg import norm

from .utils import count_words


class EmbeddingsBase(ABC):
    @abstractmethod
    def get_vector(self, phrase: str) -> np.ndarray:
        pass

    def get_vectors(self, phrases: List[str]) -> np.array:
        return np.stack([self.get_vector(phrase) for phrase in phrases])


class Embeddings(EmbeddingsBase):
    """

    Examples:
        >>> model = Embeddings("TensorFlow_USE","https://tfhub.dev/google/universal-sentence-encoder/4")
        >>> model.get_vector("Hello world").shape
        (512,)
        >>> model.get_vectors(["Hello world"]).shape
        (1, 512)
        >>> model = Embeddings("spaCy", "en_core_web_md")
        >>> model.get_vector("Hello world").shape
        (300,)
        >>> model.get_vectors(["Hello world"]).shape
        (1, 300)
        >>> model = Embeddings("Gensim_SIF_KeyedVectors", "glove-twitter-25",sentences = ["This is a nice world","Hello world","Hello everybody"])
        >>> model.get_vector("world").shape
        (25,)
        >>> model.get_vectors(["world"]).shape
        (1, 25)

    """

    def __init__(
        self, embeddings_type: str, embeddings_model: Union[Path, str], **kwargs
    ) -> None:
        if embeddings_type == "TensorFlow_USE":
            EmbeddingsClass = TensorFlowUSEEmbeddings
        elif embeddings_type == "Gensim_SIF_Word2Vec":
            EmbeddingsClass = GensimSIFWord2VecEmbeddings
        elif embeddings_type == "Gensim_SIF_KeyedVectors":
            EmbeddingsClass = GensimSIFKeyedVectorsEmbeddings
        elif embeddings_type == "spaCy":
            EmbeddingsClass = spaCyEmbeddings
        else:
            raise ValueError(f"Unknown embeddings_type={embeddings_type}")

        self._embeddings_model = EmbeddingsClass(embeddings_model, **kwargs)

    def get_vector(self, phrase: str) -> np.ndarray:
        return self._embeddings_model.get_vector(phrase)

    def get_vectors(self, phrases: List[str]) -> np.array:
        return self._embeddings_model.get_vectors(phrases)


class spaCyEmbeddings(EmbeddingsBase):
    def __init__(self, model: str) -> None:

        self._nlp = spacy.load(model)

    def get_vector(self, phrase: str) -> np.ndarray:
        return self._nlp(phrase).vector


class TensorFlowUSEEmbeddings(EmbeddingsBase):
    def __init__(self, path: str) -> None:
        try:
            import tensorflow_hub as hub
        except ModuleNotFoundError:
            print("Please install tensorflow_hub package")
            raise
        self._embed = hub.load(path)

    def get_vector(self, phrase: str) -> np.ndarray:
        return self._embed([phrase]).numpy()[0]

    def get_vectors(self, phrases: List[str]) -> np.ndarray:
        return self._embed(phrases).numpy()


class GensimSIFWord2VecEmbeddings:
    def __init__(
        self,
        path: str,
        sentences: List[str],
        alpha: Optional[float] = 0.001,
        normalize: bool = True,
    ):

        self._model = self._load_keyed_vectors(path)
        self._vocab = self._model.vocab

        words_counter = count_words(sentences)
        self._sif_dict = self.compute_sif_weights(words_counter, alpha)

        self._normalize = normalize

    @classmethod
    def compute_sif_weights(cls, words_counter, alpha) -> dict:

        """

        A function that computes smooth inverse frequency (SIF) weights based on word frequencies.
        (See "Arora, S., Liang, Y., & Ma, T. (2016). A simple but tough-to-beat baseline for sentence embeddings.")

        Args:
            words_counter: a dictionary {"word": frequency}
            alpha: regularization parameter

        Returns:
            A dictionary {"word": SIF weight}

        """

        sif_dict = {}

        for word, count in words_counter.items():
            sif_dict[word] = alpha / (alpha + count)

        return sif_dict

    def _load_keyed_vectors(self, path):
        try:
            from gensim.models import Word2Vec

        except ModuleNotFoundError:
            print("Please install gensim package")
            raise

        return Word2Vec.load(path).wv

    def get_vector(self, phrase: str) -> np.ndarray:
        tokens = phrase.split()
        res = np.mean(
            [self._sif_dict[token] * self._model[token] for token in tokens], axis=0
        )
        if self._normalize:
            res = res / norm(res)
        return res

    ## TODO: do we need most_similar? If yes should we do it at embeddings level?!
    def most_similar(self, v):
        return self._model.most_similar(positive=[v], topn=1)[0]


class GensimSIFKeyedVectorsEmbeddings(GensimSIFWord2VecEmbeddings, EmbeddingsBase):

    """

    A class to call a pre-trained embeddings model from gensim's library.

    The embeddings are weighted by the smoothed inverse frequency of each token.
    For further details, see: https://github.com/PrincetonML/SIF

    # The list of pre-trained embeddings may be browsed by typing:

        import gensim.downloader as api
        list(api.info()['models'].keys())

    """

    def __init__(
        self,
        model: str,
        sentences: List[str],
        alpha: Optional[float] = 0.001,
        normalize: bool = True,
    ):

        super().__init__(
            path=model, sentences=sentences, alpha=alpha, normalize=normalize
        )

    def _load_keyed_vectors(self, model):
        try:
            import gensim.downloader as api

        except ModuleNotFoundError:
            print("Please install gensim package")
            raise

        return api.load(model)
