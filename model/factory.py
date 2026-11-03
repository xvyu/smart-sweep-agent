from abc import ABC, abstractmethod
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain.chat_models import BaseChatModel
from langchain_ollama import OllamaEmbeddings
from langchain.chat_models import init_chat_model
from Agent.utils.config_handler import rag_conf



class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self)-> Optional[Embeddings | BaseChatModel]:
        pass

class ChatModelFactory(BaseModelFactory):
    def generator(self)-> Optional[Embeddings | BaseChatModel]:
        return init_chat_model(model=rag_conf['chat_model'])

class EmbeddingsFactory(BaseModelFactory):
    def generator(self)-> Optional[Embeddings | BaseChatModel]:
        return OllamaEmbeddings(model=rag_conf['embedding_model'])

chat_model = ChatModelFactory().generator()
embed_model = EmbeddingsFactory().generator()
