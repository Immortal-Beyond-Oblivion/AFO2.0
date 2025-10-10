# components/file_tools.py
import os
import shutil
from langchain.tools import tool

@tool
def move_and_rename_file(source_path: str, destination_folder: str, new_filename: str):
    """
    Moves a file to a specified destination folder and renames it.
    It will create the destination folder if it does not exist.
    The destination_folder should be a simple category like 'Invoices' or 'Resumes', not a full path.
    """
    if not os.path.exists(source_path):
        return f"Error: Source file not found at {source_path}"
    
    try:
        # We will organize files into a dedicated folder in the user's Documents directory.
        monitored_folder = os.path.dirname(source_path)
        full_destination_folder = os.path.join(monitored_folder, destination_folder)

        os.makedirs(full_destination_folder, exist_ok=True)
        
        destination_path = os.path.join(full_destination_folder, new_filename)
        
        shutil.move(source_path, destination_path)
        
        return f"Success: File moved and renamed to {destination_path}"
    except Exception as e:
        return f"Error moving file: {e}"