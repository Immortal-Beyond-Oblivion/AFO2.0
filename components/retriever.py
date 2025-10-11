# components/retriever.py
import os
import chromadb
from sentence_transformers import SentenceTransformer
import platformdirs
from constants import APP_NAME, APP_AUTHOR

# Setup persistent storage for ChromaDB using constants
DATA_DIR = platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)
DB_PATH = os.path.join(DATA_DIR, "milfo_vectordb")

class Retriever:
    def __init__(self):
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.collection = self.client.get_or_create_collection(name="folder_memory")
        print(f"✅ Retriever initialized. Memory loaded from: {DB_PATH}")

    def add_folder_to_memory(self, folder_category: str):
        try:
            self.collection.add(documents=[folder_category], ids=[folder_category])
            print(f"🧠 Memorized new category: {folder_category}")
        except Exception as e:
            print(f"⚠️ Could not memorize category '{folder_category}'. It might already exist.")

    def find_similar_folders(self, query_text: str, n_results: int = 5) -> list[str]:
        if self.collection.count() == 0:
            return []
        results = self.collection.query(query_texts=[query_text], n_results=n_results)
        return results['documents'][0] if results and results['documents'] else []
    
retriever_instance = Retriever()