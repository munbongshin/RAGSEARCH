# db_manager.py

from abc import ABC, abstractmethod

class DatabaseManager(ABC):
    @abstractmethod
    def get_persist_directory(self):
        pass
    
    @abstractmethod
    def search_collection(self, collection_name, query, n_results):
        pass
    
    @abstractmethod
    def get_documents_by_source(self, collection_name, sources):
        pass