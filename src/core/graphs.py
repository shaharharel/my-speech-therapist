from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send
from schema import GenerateTherapistsState, CaseAnalysisState, TherapyPlanState
from states import CreateTherapists, AnalyzeCase, GenerateReport, FollowUpChat, user_follow_up, should_continue_chat
from prompts import therapists_prompt
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage
import logging
import os
import sqlite3

# Note: logger will be configured by setup_logging() in run.py
logger = logging.getLogger(__name__)

def initiate_parallel_analysis(state: TherapyPlanState):
    """ Send parallel calls to compiled case analysis subgraph (like research assistant) """
    return [
        Send("conduct_analysis", {
            "therapist": therapist,
            "messages": [HumanMessage(content=f"Please analyze this case: {state['patient_case']}")]
        })
        for therapist in state["therapists"]
    ]

def build_therapists_graph(llm):
    """Build the therapists graph with configurable LLM"""
    logger.debug("Building therapists graph")
    
    # Build the therapists graph
    therapists_builder = StateGraph(GenerateTherapistsState)
    therapists_builder.add_node("create_therapists", CreateTherapists(llm))
    therapists_builder.add_edge(START, "create_therapists")
    therapists_builder.add_edge("create_therapists", END)
    
    # Create SQLite checkpointer for persistence
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(script_dir, "db")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "therapists_sessions.db")
    
    # Use SqliteSaver with sqlite3 connection for LangGraph 0.5+
    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)
    
    # Compile the graph with checkpointer
    therapists_builder = therapists_builder.compile(checkpointer=memory)
    
    logger.debug("Therapists graph built successfully")
    return therapists_builder

def build_case_analysis_graph(llm):
    """Build the case analysis graph with configurable LLM"""
    logger.debug("Building case analysis graph")
    
    # Build the case analysis graph
    analysis_graph_builder = StateGraph(CaseAnalysisState)
    analysis_graph_builder.add_node("analyze_case", AnalyzeCase(llm))
    analysis_graph_builder.add_edge(START, "analyze_case")
    analysis_graph_builder.add_edge("analyze_case", END)

    # Create SQLite checkpointer for persistence
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(script_dir, "db")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "case_analysis_sessions.db")
    
    # Use SqliteSaver with sqlite3 connection for LangGraph 0.5+
    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)

    # Compile the graph with checkpointer
    analysis_graph_builder = analysis_graph_builder.compile(checkpointer=memory)
    
    logger.debug("Case analysis graph built successfully")
    return analysis_graph_builder

def build_therapy_plan_graph(llm):
    """Build the therapy plan graph with parallel analysis (therapists pre-generated)"""
    logger.debug("Building therapy plan graph")
    
    # Compile the case analysis subgraph separately (like research assistant)
    case_analysis_subgraph = build_case_analysis_graph(llm)
    
    # Build the main therapy plan graph (no therapist generation - that's in separate graph)
    therapy_graph_builder = StateGraph(TherapyPlanState)
    therapy_graph_builder.add_node("conduct_analysis", case_analysis_subgraph)  # Add compiled subgraph as node
    therapy_graph_builder.add_node("generate_report", GenerateReport(llm))
    therapy_graph_builder.add_node("user_follow_up", user_follow_up)  # Interactive follow-up
    therapy_graph_builder.add_node("follow_up_chat", FollowUpChat(llm))  # Chat with therapist
    
    # Add edges - use conditional edges for Send API
    therapy_graph_builder.add_conditional_edges(START, initiate_parallel_analysis, ["conduct_analysis"])
    therapy_graph_builder.add_edge("conduct_analysis", "generate_report")
    therapy_graph_builder.add_edge("generate_report", "user_follow_up")  # Go to follow-up after report
    therapy_graph_builder.add_conditional_edges("user_follow_up", should_continue_chat, ["follow_up_chat", END])
    therapy_graph_builder.add_edge("follow_up_chat", "user_follow_up")  # Loop back for more questions

    # Create SQLite checkpointer for persistence
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(script_dir, "db")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "therapy_sessions.db")
    
    # Use SqliteSaver with sqlite3 connection for LangGraph 0.5+
    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)

    # Compile the graph with checkpointer and interrupt on user_follow_up
    therapy_graph_builder = therapy_graph_builder.compile(
        checkpointer=memory,
        interrupt_before=["user_follow_up"]
    )
    
    logger.debug("Therapy plan graph built successfully")
    return therapy_graph_builder

