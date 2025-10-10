# components/content_extractor.py
import pypdf

def extract_content(file_path: str) -> str | None:
    """Extracts text content from a file based on its extension."""
    file_extension = file_path.split('.')[-1].lower()
    content = ""
    
    try:
        if file_extension == "txt":
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif file_extension == "pdf":
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                content += page.extract_text() or ""
        # TODO: Add more handlers here for .docx, etc.
        else:
            print(f"Unsupported file type: {file_extension}. Skipping.")
            return None
        
        print(f"📄 Extracted content from {file_path}")
        return content
    except Exception as e:
        print(f"Error extracting content from {file_path}: {e}")
        return None