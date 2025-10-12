# components/content_extractor.py (Multimodal Version)

import os
import pypdf
from pdf2image import convert_from_path
from PIL import Image
import platform
import io
import base64



def get_poppler_path():
    """Determines the correct bundled poppler path based on the OS."""
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'vendor'))
    
    if platform.system() == "Windows":
        return os.path.join(base_path, 'windows', 'bin') # currently i haven't bundled poppler for Windows
    elif platform.system() == "Darwin": # macOS
        return os.path.join(base_path, 'macos')
    else: # Linux
        # Again I will get to Linux systems later
        return None

def extract_content(file_path: str) -> dict | None:
    """
    Extracts content from a file, handling text, images, and scanned PDFs.
    Returns a dictionary with 'type' and 'data'.
    """
    file_extension = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_extension == ".txt":
            print("📄 Detected Text File.")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return {"type": "text", "data": content}
        # --- Handle Image Files ---
        elif file_extension in ['.png', '.jpg', '.jpeg', '.webp']:
            print("📄 Detected Image File.")
            with open(file_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return {"type": "image", "data": encoded_string, "extension": file_extension[1:]}

        # --- Handle PDF Files ---
        elif file_extension == ".pdf":
            print("📄 Detected PDF File. Attempting text extraction...")
            text_content = ""
            try:
                reader = pypdf.PdfReader(file_path)
                for page in reader.pages:
                    text_content += page.extract_text() or ""
            except Exception as e:
                print(f"pypdf failed to read text: {e}")

            # --- Heuristic: If text is short, treat as scanned ---
            if len(text_content.strip()) < 100:
                print("📝 Text content is minimal. Treating as a scanned/image-based PDF.")
                poppler_path = get_poppler_path()
                images = convert_from_path(file_path, poppler_path=poppler_path)
                
                image_data_list = []
                for image in images:
                    with io.BytesIO() as output:
                        image.save(output, format="JPEG")
                        encoded_string = base64.b64encode(output.getvalue()).decode('utf-8')
                        image_data_list.append(encoded_string)
                
                return {"type": "image_list", "data": image_data_list}
            else:
                print("📝 Found sufficient text content.")
                return {"type": "text", "data": text_content}

        else:
            print(f"Unsupported file type: {file_extension}. Skipping.")
            return None
            
    except Exception as e:
        print(f"❌ Error extracting content from {file_path}: {e}")
        return None