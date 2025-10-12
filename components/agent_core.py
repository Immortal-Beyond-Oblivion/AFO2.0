import operator
import os
import base64 
from typing import TypedDict, Annotated, Sequence

# --- CORE V1 IMPORTS ---
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

# --- LANGGRAPH IMPORTS ---
from langgraph.graph import StateGraph, END
from langchain.agents.format_scratchpad.tools import format_to_tool_messages
from langchain.agents.output_parsers.tools import ToolsAgentOutputParser
from langchain.agents import AgentExecutor

# --- LOCAL IMPORTS ---
from .config_manager import load_settings
from .file_tools import move_and_rename_file
from .content_extractor import extract_content
from .retriever import retriever_instance

# --- 1. Load settings and initialize LLM ---
app_settings = load_settings()
GOOGLE_API_KEY = app_settings.get("GOOGLE_API_KEY")
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY, temperature=0) if GOOGLE_API_KEY else None

# --- 2. Define Tools ---
tools = [move_and_rename_file]

# --- 3. Define the State for our Graph ---
class AgentState(TypedDict):
    input: str
    chat_history: Annotated[Sequence[BaseMessage], operator.add]
    agent_outcome: list
    intermediate_steps: Annotated[list[tuple], operator.add]


# --- 4. Define the Agent and Prompt ---
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a highly intelligent file organization agent. Your goal is to analyze the provided file's content, which may be text OR IMAGES, and move the file to the most appropriate category with a short descriptive name that is appropriate for the content found in the file. Do not forget to add the original file extension at last. Here is a list of existing folder categories you have used before: {existing_folders} """,
        ),
        MessagesPlaceholder(variable_name="input"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

# --- 5. Create the Agent ---
if llm:
    llm_with_tools = llm.bind_tools(tools)

    agent = (
        {
            "input": lambda x: x["input"],
            "agent_scratchpad": lambda x: format_to_tool_messages(x["intermediate_steps"]),
            "existing_folders": lambda x: x["existing_folders"], # Pass context to prompt
        }
        | prompt
        | llm_with_tools
        | ToolsAgentOutputParser()
    )
else:
    agent = None

# --- 6. Define Graph Nodes ---
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True) if agent else None


# --- 7. The Main Processing Function ---
def process_file_with_agent(file_path: str):
    if not agent_executor:
        print("Error: Agent is not configured (check API key). Cannot process file.")
        return

    print(f"🧠 RAG Agent is now processing: {file_path}")
    # Use the multimodal content_extractor we designed
    extracted_data = extract_content(file_path)
    
    if not extracted_data:
        return

    try:
        # RAG RETRIEVE STEP
        retrieval_query = extracted_data.get('data', '')[:500] if extracted_data.get('type') == 'text' else f"An image file named {os.path.basename(file_path)}"
        similar_folders = retriever_instance.find_similar_folders(retrieval_query)
        folder_context = ", ".join(similar_folders) if similar_folders else "No relevant folders found yet."
        print(f"Found context from memory: {folder_context}")

        # --- Construct the multimodal message list ---
        content_type = extracted_data.get("type")
        content_data = extracted_data.get("data")
        filename = os.path.basename(file_path)
        
        user_message_content = []
        
        if content_type == "text":
            user_message_content.append({"type": "text", "text": f"Organize this text file named '{filename}' located at `{file_path}`. Content snippet: {content_data[:2000]}..."})
        elif content_type == "image":
            ext = extracted_data.get("extension", "jpeg")
            if ext == "jpg": # convert to standard extension
                ext = "jpeg"
            user_message_content.extend([
                {"type": "text", "text": f"Organize this image file named '{filename}' located at `{file_path}`. What does this image show?"},
                {"type": "image_url", "image_url": {"url": f"data:image/{ext};base64,{content_data}"}}
            ])
        elif content_type == "image_list":
            user_message_content.append({"type": "text", "text": f"This is a scanned PDF named '{filename}' located at `{file_path}` with {len(content_data)} pages. Analyze the content of these pages to organize the file."})
            for i, img_data in enumerate(content_data):
                user_message_content.append({"type": "text", "text": f"--- Page {i+1} ---"})
                user_message_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}})

        if not user_message_content:
            print("Could not construct a valid message for the agent.")
            return

        # --- Invoke the agent executor with the new 'messages' structure ---
        result = agent_executor.invoke({
            "input": [("user", user_message_content)],
            "existing_folders": folder_context,
        })
        
        print(f"✅ Agent finished processing. Final output: {result.get('output')}")
        
    except Exception as e:
        print(f"❌ An error occurred during agent execution: {e}")