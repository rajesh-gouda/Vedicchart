import os
from datetime import datetime
from uuid import uuid4
from fastapi import FastAPI, APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor, tool
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from dotenv import load_dotenv
from context import set_current_user, get_current_user
from logger import logger

from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# --- Astrology helper imports (from your newhelper.py) ---
from vedic import (
    get_birth_chart,
    compare_transits,
    get_mahadasha,
    get_panchanga,
    get_divisional_chart,
    get_yogas,
)
from utils import get_timezone_offset

# --- FastAPI setup ---

load_dotenv()


users = {}

templates = Jinja2Templates(directory="templates")


router = APIRouter()


@router.get("/chat", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
        },
    )


@router.post("/register_user")
async def register_user(request: Request):
    data = await request.json()
    name = data["name"]
    dob = data["dob"]
    tob = data["tob"]
    place = data["place"]
    lat = float(data["lat"])
    lon = float(data["lon"])

    birth_str = f"{dob} {tob}:00"
    user_id = str(uuid4())
    tz_offset = get_timezone_offset(lat, lon, f"{dob}T{tob}:00")

    users[user_id] = {
        "user_id": user_id,
        "name": name,
        "birth_str": birth_str,
        "lat": lat,
        "lon": lon,
        "tz_offset": tz_offset,
    }

    return JSONResponse(content={"user_id": user_id})


# --- LangChain tools ---
@tool("divisional_chart")
def divisional_chart_tool(chart_type: str = "D9") -> str:
    """
    Get a divisional chart (e.g., D9 for marriage, D10 for career, etc).
    chart_type: D1, D2, D3, D7, D9, D10, D12, D16, D20, D24, D30, D60.
    D9 (Navamsha) is used for marriage/relationships, D10 for career, D7 for children, etc.
    Returns formatted chart text.
    """
    logger.info(
        f"[TOOL CALL] divisional_chart_tool called with chart_type={chart_type}"
    )

    user = get_current_user()
    logger.info(f"Current user: {user}")
    if not user:
        return "Error: No user session found. Please provide user_id in request."

    result = get_divisional_chart(
        chart_type=chart_type,
        dt=datetime.strptime(user["birth_str"], "%Y-%m-%d %H:%M:%S"),
        lat=user["lat"],
        lon=user["lon"],
        tz_offset=user["tz_offset"],
    )
    return result.get("formatted_text", "No chart found.")


PROMPT = """You are a traditional Vedic astrologer with expertise in interpreting divisional charts. Always use the available tools — especially the `divisional_chart_tool` — to answer astrology-related questions. 

- For marriage-related queries, reference the D9 chart.
- For career, use the D10 chart.
- For children, consult the D7 chart. and so on for other charts.

When answering, always:
1. Reference the relevant planet(s) and house(s) in the chart.
2. Describe the expected outcome based on the chart.
3. Suggest a simple mantra or remedy when applicable.

If the question is not related to astrology, politely respond that you can only assist with astrology-related topics.

Use prior chat history to maintain continuity and coherence. Keep responses concise (under 100 words), respectful, and focused."""


# --- Prompt template ---
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            PROMPT,
        ),
        ("human", "{input}"),
        ("ai", "{agent_scratchpad}"),
    ]
)

# --- Agent setup ---
tools = [divisional_chart_tool]
llm = ChatOpenAI(
    model="gpt-3.5-turbo", temperature=0.3, api_key=os.getenv("OPENAI_API_KEY")
)
agent = create_openai_tools_agent(llm, tools, prompt)

# Per-user memory storage
# A mapping for user sessions
store = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]


# --- Request/response models ---
class ChatRequest(BaseModel):
    user_id: str
    query: str


class ChatResponse(BaseModel):
    response: str


# --- Main chat route ---
@router.post("/vedicchat", response_model=ChatResponse)
async def vedic_chat(request: ChatRequest):
    # Get user/session details and set in session manager
    user = users.get(request.user_id)
    logger.info(f"Received chat request from user: {user} - query: {request.query}")
    if not user:
        return ChatResponse(response="Error: User not found. Please register first.")
    set_current_user(user)

    try:

        # Create agent executor with user-specific memory
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
        )
        agent_with_chat_history = RunnableWithMessageHistory(
            agent_executor,
            get_session_history,
            input_messages_key="user_query",
            history_messages_key="chat_history",
            verbose=True,
        )

        # Prepare core astrology data for context
        chart = get_birth_chart(
            user["birth_str"], user["lat"], user["lon"], user["tz_offset"]
        )
        transits = compare_transits(
            current_dt=datetime.now(),
            lat=user["lat"],
            lon=user["lon"],
            natal_chart=chart["chart"],
            tz_offset=user["tz_offset"],
        )
        mahadasha_data = get_mahadasha(
            chart["chart"], datetime.strptime(user["birth_str"], "%Y-%m-%d %H:%M:%S")
        )
        panchanga = get_panchanga(datetime.now(), tz_offset=user["tz_offset"])
        yogas = get_yogas(chart["chart"])

        # Inject context into agent input
        context = (
            f"User: {user['name']} (ID: {user['user_id']})\n"
            f"Birth Chart: {chart['formatted_text']}\n"
            f"Transits: {transits['formatted_text']}\n"
            f"Current Mahadasha: {mahadasha_data['current_mahadasha']}\n"
            f"Panchanga: Tithi: {panchanga['tithi']}, Nakshatra: {panchanga['nakshatra']}, Yoga: {panchanga['yoga']}\n"
            f"Yogas: {', '.join(yogas[:3]) if yogas else 'None'}"
        )

        full_input = f"{context}\n| User Query: {request.query}"
        result = await agent_with_chat_history.ainvoke(
            {"input": full_input, "user_query": request.query},  # Add this line
            config={
                "configurable": {"session_id": user["user_id"]},
            },
        )

        # print(f"--" * 40)
        # print(result)
        return ChatResponse(response=result["output"])
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return ChatResponse(
            response="An error occurred while processing your request. Please try again later."
        )
