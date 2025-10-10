# components/agent_core.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_json_chat_agent

from components.config_manager import load_settings
from components.file_tools import move_and_rename_file
from components.content_extractor import extract_content

# --- 1. Load settings and initialize LLM ---
app_settings = load_settings()
GOOGLE_API_KEY = app_settings.get("GOOGLE_API_KEY")

llm = None
if GOOGLE_API_KEY:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY)
else:
    print("⚠️ WARNING: Google API Key not found. Agent will not work.")

# --- 2. Define the tools the agent can use ---
tools = [move_and_rename_file]

# --- 3. Create the Agent Prompt ---
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a highly intelligent file organization agent.
    Your goal is to analyze the content of a file and move it to an appropriate category folder with a descriptive name.
    You have access to the following tools:
    {tools}
    
    The names of the tools you can use are:
    {tool_names}
    1. First, analyze the content and decide on a category (e.g., 'Invoices', 'Resumes', 'Code', 'Images', 'Assignment', 'Finance', etc.).
    2. Second, decide on a new, descriptive filename for the file, make sure title appropriately matches the file content (e.g., 'Resume_JohnDoe_2025.pdf').
    3. Finally, use the `move_and_rename_file` tool to perform the action."""),
    ("user", "Please organize the file located at `{source_path}` with the following content:\n\n--- CONTENT ---\n{file_content}\n--- END CONTENT ---"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# --- 4. Create the Agent and Executor ---
agent = None
agent_executor = None
if llm:
    agent = create_json_chat_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

def process_file_with_agent(file_path: str):
    """
    The main function for the agent core. It takes a file path,
    extracts its content, and invokes the agent executor to organize it.
    """
    if not agent_executor:
        print("Error: Agent is not configured (check API key). Cannot process file.")
        return

    print(f"🧠 Agent is now processing: {file_path}")
    
    content = extract_content(file_path)
    
    if content:
        try:
            # Invoke the agent. This starts the reasoning loop.
            result = agent_executor.invoke({
                "file_content": content,
                "source_path": file_path 
            })
            print(f"✅ Agent finished processing. Final output: {result.get('output')}")
        except Exception as e:
            print(f"❌ An error occurred during agent execution: {e}")