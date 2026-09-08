# components/retriever.py
import os
import chromadb
from sentence_transformers import SentenceTransformer
import platformdirs
from constants import APP_NAME, APP_AUTHOR
from .chunking import chunk_text

# Setup persistent storage for ChromaDB using constants
DATA_DIR = platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)
DB_PATH = os.path.join(DATA_DIR, "afo_vectordb")


class Retriever:
    """
    T019: this class now owns two Chroma collections instead of one:

    - `folder_memory` (unchanged, pre-T019 behavior): short folder-category
      name strings, used for few-shot folder-naming consistency when the
      agent is deciding where to file a new item. Kept exactly as it was —
      per implementation.md's T019 wording, this stays "one signal among
      several rather than the only one," not something to remove.
    - `file_content` (new, T019): real per-file content, chunked (via
      components/chunking.py) and embedded, with `file_id`/`filename`/
      `category`/`chunk_index` attached to every chunk as metadata so a hit
      can be rolled back up to a file-level result later (architecture.md
      §2.2, §4.1's "semantic candidate generator"). This is the piece that
      turns the vector store from "a cache of folder names" into an actual
      semantic index over file content, closing the gap state.md §3 called
      out ("the system cannot answer a single question about the files it
      has already organized").

    Nothing yet *queries* `file_content` as part of a real search feature —
    building the semantic candidate generator that consumes it is T026
    (Phase 2). This class only provides indexing (`index_file_content`) and
    a basic query method (`search_file_content`) so that work has something
    real to call into, instead of each future task re-deriving its own
    Chroma wiring.
    """

    def __init__(self):
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.collection = self.client.get_or_create_collection(name="folder_memory")
        self.content_collection = self.client.get_or_create_collection(name="file_content")
        print(f"✅ Retriever initialized. Memory loaded from: {DB_PATH}")

    # --- Folder-naming consistency signal (pre-T019, unchanged) ---

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

    # --- Real per-file content indexing (T019, new) ---

    def index_file_content(self, file_id: str, filename: str, category: str, text: str) -> int:
        """
        Chunk `text` (via chunk_text) and (re-)index it into the
        `file_content` collection under `file_id`.

        Any existing chunks for this file_id are deleted first, so calling
        this again for the same file_id (e.g. the file was re-categorized,
        or a future re-index pass runs) replaces its content rather than
        accumulating stale duplicate chunks alongside fresh ones. This is a
        delete-then-insert, not an update-in-place, mirroring the same
        trade-off T018's files_fts triggers already made for the same
        reason (simplicity over micro-optimization; this is not a hot path).

        Returns the number of chunks actually indexed (0 if `text` was
        empty/whitespace-only — callers can treat that as "nothing to
        index" rather than an error).
        """
        # Clear any prior chunks for this file before adding fresh ones.
        # Safe to call even if none exist yet (Chroma's delete-by-where is a
        # no-op in that case).
        try:
            self.content_collection.delete(where={"file_id": file_id})
        except Exception as e:
            print(f"⚠️ Could not clear prior chunks for file_id '{file_id}': {e}")

        chunks = chunk_text(text)
        if not chunks:
            return 0

        ids = [f"{file_id}::chunk::{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "file_id": file_id,
                "filename": filename,
                "category": category,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]

        self.content_collection.add(documents=chunks, ids=ids, metadatas=metadatas)
        print(f"🧠 Indexed {len(chunks)} content chunk(s) for '{filename}' (file_id={file_id[:8]}...).")
        return len(chunks)

    def search_file_content(self, query_text: str, n_results: int = 10) -> list[dict]:
        """
        Semantic search over real file content (as opposed to
        find_similar_folders, which searches folder-name strings).

        Returns a list of chunk-level hits, each a dict with `file_id`,
        `filename`, `category`, `chunk_index`, `document` (the chunk text),
        and `distance` (lower = more similar, Chroma's default metric).
        Multiple chunks from the same file may appear — rolling these up
        into one ranked-by-file result list (per architecture.md §4.1's
        "dedup by file_id") is the semantic candidate generator's job
        (T026), not this method's; this stays a thin, direct wrapper over
        Chroma so that future caller has full chunk-level detail to work
        with rather than a pre-collapsed result.
        """
        if self.content_collection.count() == 0:
            return []

        results = self.content_collection.query(query_texts=[query_text], n_results=n_results)
        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        hits = []
        for i, chunk_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
            document = results["documents"][0][i] if results.get("documents") else ""
            distance = results["distances"][0][i] if results.get("distances") else None
            hits.append({
                "chunk_id": chunk_id,
                "file_id": metadata.get("file_id"),
                "filename": metadata.get("filename"),
                "category": metadata.get("category"),
                "chunk_index": metadata.get("chunk_index"),
                "document": document,
                "distance": distance,
            })
        return hits


retriever_instance = Retriever()
