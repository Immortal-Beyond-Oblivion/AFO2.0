# AFO
Autonomous RAG-Powered File Organizer

A small project that helps users select a folder where their unstructred files will be monitored, 
sorted, renamed, moved in appropriately created and named directories as per the content inside it using Agentic AI RAG based LLM reasoning engine.

## ⚙️ Configuration

Before running AFO for the first time, you need to create a configuration file to store your LLM provider's API key. The application is designed to be secure and stores its settings in the standard user application data directory.

AFO supports multiple LLM providers — **Google**, **Anthropic**, **OpenAI**, and **Grok (xAI)** — plus an optional **local/offline model** (e.g. via Ollama), selected via a single `active_provider` field. You only need to fill in the API key for the provider you intend to use.

> **Note:** As of `implementation.md` T009, all five providers listed above (`google`, `anthropic`, `openai`, `grok`, `local`) are fully wired end-to-end through `llm/provider.py` — whichever one you set as `active_provider` is the one the agent actually uses, no fallback to Google.

### First-Time Setup Instructions

1.  **Locate (or Create) the Application Data Directory**

    You will need to create a `settings.json` file in the following location, specific to your operating system. You may need to create the parent folders (`AFODevelopers` and `AFO`) yourself if they don't exist.

    * **Windows:**
        `C:\Users\<YourUsername>\AppData\Local\AFODevelopers\AFO\`
        *(Note: The `AppData` folder is hidden by default.)*

    * **macOS:**
        `~/Library/Application Support/AFO/`
        *(Note: The `~` character represents your home directory. On macOS, the author name is typically not used in the path structure, so the folder is directly under Application Support.)*

    * **Linux:**
        `~/.local/share/AFODevelopers/AFO/`
        *(Note: The `~` character represents your home directory. The `.local` folder is hidden.)*

2.  **Create and Edit `settings.json`**

    Inside the `AFO` directory, create a new file named `settings.json`. Open the file with any text editor and paste the following content:

    ```json
    {
        "monitored_path": null,
        "active_provider": "google",
        "providers": {
            "google":    { "api_key": "YOUR_GEMINI_API_KEY_GOES_HERE" },
            "anthropic": { "api_key": null },
            "openai":    { "api_key": null },
            "grok":      { "api_key": null },
            "local":     { "enabled": false, "model": null }
        }
    }
    ```

3.  **Update the File Contents**

    * **`monitored_path`**: You can leave this as `null`. The application will prompt you to choose a folder via the system tray icon, and it will automatically save your choice here.
    * **`active_provider`**: Set this to the provider you want the agent to use — one of `"google"`, `"anthropic"`, `"openai"`, `"grok"`, or `"local"`. Defaults to `"google"`.
    * **`providers.<name>.api_key`**: Fill in the API key for whichever provider you selected above (e.g. `providers.google.api_key` for a Google AI Studio key). Keys for providers you aren't using can be left as `null`.
    * **`providers.local.enabled`** / **`providers.local.model`**: For a local/offline model instead of a cloud provider, set `enabled` to `true` and `model` to your local model's identifier (e.g. an Ollama tag). See the full schema reference in [`docs/config_schema.md`](docs/config_schema.md) for details.

    If you have an existing `settings.json` from an older version of AFO (using the old flat `google_api_key` field), you don't need to migrate it by hand — the app detects and automatically upgrades it to this new schema the first time it loads.

### Using a Local / Offline Model (Ollama)

If you'd rather not send file contents to any cloud provider, AFO can run entirely against a local model via [Ollama](https://ollama.com):

1.  **Install Ollama** for your OS from [ollama.com/download](https://ollama.com/download) and make sure the Ollama app/service is running (it listens on `http://localhost:11434` by default — AFO's local backend is hard-coded to talk to that address only, so it never reaches out to a remote host).
2.  **Pull a model** that supports tool-calling, e.g.:
    ```bash
    ollama pull llama3.1
    ```
3.  **Update `settings.json`**:
    ```json
    {
        "active_provider": "local",
        "providers": {
            "local": { "enabled": true, "model": "llama3.1" }
        }
    }
    ```
    Both `enabled: true` and a matching `model` tag are required — if either is missing, AFO treats the agent as unconfigured rather than guessing.
4.  **Install the local-model dependency** (included in `requirements.txt` as of T009):
    ```bash
    uv pip install -r requirements.txt
    ```
5.  Run AFO as usual (`python main.py`). All reasoning now happens against your local Ollama server — no API key required, and no file content leaves your machine.

---

## 🚶 Walkthrough

Follow these steps to get AFO up and running on your machine.

1.  **Set Up Your Environment**
    Create and activate a Python virtual environment, then install the necessary packages:
    ```bash
    uv pip install -r requirements.txt
    ```

2.  **Configure the Application**
    Before your first launch, ensure you have created your `settings.json` file with your chosen provider's API key (or local-model settings) as described in the Configuration section.

3.  **Launch and Use**
    Run the `main.py` script from your terminal to start the application.
    ```bash
    python main.py
    ```
    * A AFO icon will appear in your system tray (Windows) or menu bar (macOS).
    * Click the icon and select **"Choose Monitored Folder..."** to tell the agent which directory to watch.
    * Drop a file into the folder you selected and watch the terminal for the agent's activity!

---

## ⚠️ Important Notes

Please be aware of the following points when using the current version of AFO:

* **First Run Delay:** Your first run will be noticeably slower. The application needs to download the local sentence-transformer model (approx. 90MB) that powers the RAG memory system. This is a **one-time download**, and all subsequent launches will be fast.

* **Current Status:** The current version of AFO supports a variety of file types:
    * **Text-based files** (`.txt`, text-heavy `.pdf`)
    * **Common image formats** (`.png`, `.jpg`, `.jpeg`)
    * **Scanned (image-based) PDFs**.
    * Please note that full support for scanned PDFs is currently configured for **macOS only** due to the bundled `poppler` dependency.

* **🎯 Next Steps:** Our immediate development priorities are:
    * Bundling the necessary dependencies to enable full image and scanned PDF support on **Windows and Linux**.
    * Exploring support for new file types, such as **video files (`.mp4`, `.mov`)**, by analyzing their metadata and content.

