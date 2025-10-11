import operator
import os
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
# We will simplify the state for now to align with the agent's expectations
class AgentState(TypedDict):
    input: str
    chat_history: Annotated[Sequence[BaseMessage], operator.add]
    agent_outcome: list
    intermediate_steps: Annotated[list[tuple], operator.add]


# --- 4. Define the Agent and Prompt ---
# This prompt now correctly uses 'input' and 'agent_scratchpad'
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a highly intelligent file organization agent... (Your detailed prompt here, including {existing_folders})""",
        ),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

# --- 5. Create the Agent ---
# We bind the tools to the LLM and create a runnable agent chain
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
# We will use a simpler, non-graph AgentExecutor for now to resolve the issue,
# as the manual graph setup was causing conflicts with the agent constructor.
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True) if agent else None


# --- 7. The Main Processing Function ---
def process_file_with_agent(file_path: str):
    if not agent_executor:
        print("Error: Agent is not configured (check API key). Cannot process file.")
        return

    print(f"🧠 RAG Agent is now processing: {file_path}")
    content = extract_content(file_path)
    if content:
        try:
            similar_folders = retriever_instance.find_similar_folders(content)
            folder_context = ", ".join(similar_folders) if similar_folders else "No relevant folders found yet."
            print(f"Found context from memory: {folder_context}")

            user_input = f"Organize file named '{os.path.basename(file_path)}' at `{file_path}`. Content snippet: {content[:2000]}..."

            # Invoke the agent executor
            result = agent_executor.invoke({
                "input": user_input,
                "existing_folders": folder_context,
            })
            
            print(f"✅ Agent finished processing. Final output: {result.get('output')}")
            
        except Exception as e:
            print(f"❌ An error occurred during agent execution: {e}")