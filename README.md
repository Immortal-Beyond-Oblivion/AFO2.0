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
---

## 🚶 Walkthrough

Follow these steps to get MILFO up and running on your machine.

1.  **Set Up Your Environment**
    Create and activate a Python virtual environment, then install the necessary packages:
    ```bash
    uv pip install -r requirements.txt
    ```

2.  **Configure the Application**
    Before your first launch, ensure you have created your `settings.json` file with your Google Gemini API key as described in the Configuration section.

3.  **Launch and Use**
    Run the `main.py` script from your terminal to start the application.
    ```bash
    python main.py
    ```
    * A MILFO icon will appear in your system tray (Windows) or menu bar (macOS).
    * Click the icon and select **"Choose Monitored Folder..."** to tell the agent which directory to watch.
    * Drop a file into the folder you selected and watch the terminal for the agent's activity!

---

## ⚠️ Important Notes

Please be aware of the following points when using the current version of MILFO:

* **First Run Delay:** Your first run will be noticeably slower. The application needs to download the local sentence-transformer model (approx. 90MB) that powers the RAG memory system. This is a **one-time download**, and all subsequent launches will be fast.

* **Current Status:** The current version of MILFO is optimized for processing **text-based PDF (`.pdf`) and plain text (`.txt`) files**. It relies on extracting textual content to make its organizational decisions.

* **🎯 Next Steps:** Our immediate development priority is to expand support to include **image files (`.png`, `.jpg`)** and to handle **scanned (image-based) PDFs**.
