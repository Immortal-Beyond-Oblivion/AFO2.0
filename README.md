# MILFO
Most Intelligent Local File Organizer

A small project that helps users select a folder where their unstructred files will be monitored, 
sorted, renamed, moved in appropriately created and named directories as per the content inside it using Agentic AI RAG based LLM reasoning engine.

## ⚙️ Configuration

Before running MILFO for the first time, you need to create a configuration file to store your Google Gemini API key. The application is designed to be secure and stores its settings in the standard user application data directory.

### First-Time Setup Instructions

1.  **Locate (or Create) the Application Data Directory**

    You will need to create a `settings.json` file in the following location, specific to your operating system. You may need to create the parent folders (`MILFODevelopers` and `MILFO`) yourself if they don't exist.

    * **Windows:**
        `C:\Users\<YourUsername>\AppData\Local\MILFODevelopers\MILFO\`
        *(Note: The `AppData` folder is hidden by default.)*

    * **macOS:**
        `~/Library/Application Support/MILFO/`
        *(Note: The `~` character represents your home directory. On macOS, the author name is typically not used in the path structure, so the folder is directly under Application Support.)*

    * **Linux:**
        `~/.local/share/MILFODevelopers/MILFO/`
        *(Note: The `~` character represents your home directory. The `.local` folder is hidden.)*

2.  **Create and Edit `settings.json`**

    Inside the `MILFO` directory, create a new file named `settings.json`. Open the file with any text editor and paste the following content:

    ```json
    {
        "monitored_path": null,
        "google_api_key": "YOUR_GEMINI_API_KEY_GOES_HERE"
    }
    ```

3.  **Update the File Contents**

    * **`monitored_path`**: You can leave this as `null`. The application will prompt you to choose a folder via the system tray icon, and it will automatically save your choice here.
    * **`google_api_key`**: **This is required.** Replace `"YOUR_GEMINI_API_KEY_GOES_HERE"` with your actual API key from Google AI Studio. The agent will not work without a valid key.

🚶 Walkthrough

Follow these steps to get MILFO up and running on your machine.

    Set Up Environment:
    Create a Python virtual environment and activate it. Then, install the necessary packages using the requirements.txt file:

    uv pip install -r requirements.txt

    Launch the Application:
    Run the main.py script from your terminal:

    python main.py

