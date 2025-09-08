"""
Unified graphs that use a single database for all checkpoints
"""

from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send
from .schema import GenerateTherapistsState, CaseAnalysisState, TherapyPlanState
from .states import CreateTherapists, AnalyzeCase, GenerateReport, FollowUpChat, user_follow_up, should_continue_chat
from langgraph.checkpoint.sqlite import SqliteSaver
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

def get_unified_checkpointer():
    """Get the unified checkpointer for all graphs"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up two levels to project root, then to db
    project_root = os.path.dirname(os.path.dirname(script_dir))
    db_dir = os.path.join(project_root, "db")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "lihi_assistant.db")
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)

def initiate_parallel_analysis(state: TherapyPlanState):
    """ Send parallel calls to compiled case analysis subgraph """
    from langchain_core.messages import HumanMessage
    return [
        Send("conduct_analysis", {
            "therapist": therapist,
            "messages": [HumanMessage(content=f"Please analyze this case: {state['patient_case']}")]
        })
        for therapist in state["therapists"]
    ]

def build_unified_therapists_graph(llm):
    """Build the therapists graph with unified checkpointer"""
    logger.debug("Building unified therapists graph")
    
    therapists_builder = StateGraph(GenerateTherapistsState)
    therapists_builder.add_node("create_therapists", CreateTherapists(llm))
    therapists_builder.add_edge(START, "create_therapists")
    therapists_builder.add_edge("create_therapists", END)
    
    # Use unified checkpointer
    memory = get_unified_checkpointer()
    
    # Compile the graph with checkpointer
    therapists_graph = therapists_builder.compile(checkpointer=memory)
    
    logger.debug("Unified therapists graph built successfully")
    return therapists_graph

def build_unified_case_analysis_graph(llm):
    """Build the case analysis graph with unified checkpointer"""
    logger.debug("Building unified case analysis graph")
    
    analysis_graph_builder = StateGraph(CaseAnalysisState)
    analysis_graph_builder.add_node("analyze_case", AnalyzeCase(llm))
    analysis_graph_builder.add_edge(START, "analyze_case")
    analysis_graph_builder.add_edge("analyze_case", END)

    # Use unified checkpointer
    memory = get_unified_checkpointer()

    # Compile the graph with checkpointer
    analysis_graph = analysis_graph_builder.compile(checkpointer=memory)
    
    logger.debug("Unified case analysis graph built successfully")
    return analysis_graph

def build_unified_therapy_plan_graph(llm):
    """Build the therapy plan graph with unified checkpointer"""
    logger.debug("Building unified therapy plan graph")
    
    # Compile the case analysis subgraph separately
    case_analysis_subgraph = build_unified_case_analysis_graph(llm)
    
    # Build the main therapy plan graph
    therapy_graph_builder = StateGraph(TherapyPlanState)
    therapy_graph_builder.add_node("conduct_analysis", case_analysis_subgraph)
    therapy_graph_builder.add_node("generate_report", GenerateReport(llm))
    therapy_graph_builder.add_node("user_follow_up", user_follow_up)
    therapy_graph_builder.add_node("follow_up_chat", FollowUpChat(llm))
    
    # Add edges
    therapy_graph_builder.add_conditional_edges(START, initiate_parallel_analysis, ["conduct_analysis"])
    therapy_graph_builder.add_edge("conduct_analysis", "generate_report")
    therapy_graph_builder.add_edge("generate_report", "user_follow_up")
    therapy_graph_builder.add_conditional_edges("user_follow_up", should_continue_chat, ["follow_up_chat", END])
    therapy_graph_builder.add_edge("follow_up_chat", "user_follow_up")

    # Use unified checkpointer
    memory = get_unified_checkpointer()

    # Compile the graph with checkpointer and interrupt on user_follow_up
    therapy_graph = therapy_graph_builder.compile(
        checkpointer=memory,
        interrupt_before=["user_follow_up"]
    )
    
    logger.debug("Unified therapy plan graph built successfully")
    return therapy_graph