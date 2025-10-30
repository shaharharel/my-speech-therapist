import os
import hydra
from omegaconf import DictConfig
from dotenv import dotenv_values
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
import logging
from src.utils.config_loader import get_model_name, get_temperature, get_max_tokens

# Configure logging early for debug output during imports
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
)

from unified_graphs import build_unified_therapists_graph, build_unified_case_analysis_graph, build_unified_therapy_plan_graph
from utils import save_therapist_case_to_docx_file, save_final_report_to_docx_file
from session_manager import SessionManager, TherapySession
from langchain_core.messages import HumanMessage

# Initialize at module level for Studio compatibility
os.environ.update({k: v for k, v in dotenv_values("./.env").items()})

# Create default LLM and tools for Studio (from config file)
llm = ChatOpenAI(
    model=get_model_name(),
    temperature=get_temperature(),
    max_tokens=get_max_tokens()
)
tool = TavilySearch(max_results=10)
tools = [tool]
llm_with_tools = llm.bind_tools(tools)

# Create graphs for Studio using unified graphs
therapists_graph = build_unified_therapists_graph(llm)
case_analysis_graph = build_unified_case_analysis_graph(llm)
therapy_plan_graph = build_unified_therapy_plan_graph(llm)

# Initialize session manager
session_manager = SessionManager()

def setup_logging(cfg: DictConfig):
    """Setup logging based on Hydra configuration"""
    # Configure logging based on config
    logging.basicConfig(
        level=getattr(logging, cfg.logging.level.upper()),
        format=cfg.logging.format,
        force=True  # Override any existing configuration
    )
    return logging.getLogger(__name__)

def run(cfg: DictConfig):
    """Main execution function with Hydra configuration"""
    # Setup logging with Hydra config
    logger = setup_logging(cfg)
    
    logger.info(f"Starting speech therapist analysis with config: {cfg.app.name} v{cfg.app.version}")
    
    # Run analysis with proper checkpointer configuration
    thread = {
        "configurable": {
            "thread_id": cfg.thread_id
        }
    }
    
    logger.info(f"Processing patient case: {cfg.patient_case}")
    
    # Generate therapists
    for event in therapists_graph.stream({"patient_case": cfg.patient_case}, thread, stream_mode="values"):
        logger.debug(f"Therapists graph event: {event}")
    
    final_state = therapists_graph.get_state(thread)
    therapists = final_state.values.get('therapists')
    
    logger.info(f"Generated {len(therapists)} therapists for analysis")
    
    # Analyze case with each therapist
    for therapist in therapists:
        logger.info(f"Analyzing case with therapist: {therapist.name} ({therapist.role})")
        
        # Create separate thread for each therapist analysis
        therapist_thread = {
            "configurable": {
                "thread_id": f"{cfg.thread_id}_{therapist.role}"
            }
        }
        
        for event in case_analysis_graph.stream({"therapist": therapist, "messages": [HumanMessage(cfg.patient_case)]}, therapist_thread):
            logger.debug(f"Case analysis event: {event}")
            
            if 'analyze_case' in event and 'report' in event['analyze_case']:
                report = event['analyze_case']['report']
                
                if cfg.output.save_reports:
                    patient_name = cfg.get('patient_name', f"Patient_{cfg.thread_id}")
                    patient_id = cfg.get('patient_id', None)
                    save_therapist_case_to_docx_file(report, therapist, cfg.output, patient_name, patient_id)
                else:
                    logger.info(f"Report for {therapist.name}: {report.content}")

def run_parallel_analysis(cfg: DictConfig):
    """Run parallel therapy analysis using Send API with two separate graphs"""
    # Setup logging with Hydra config
    logger = setup_logging(cfg)
    
    logger.info(f"Starting parallel speech therapist analysis with config: {cfg.app.name} v{cfg.app.version}")
    
    # Step 1: Generate therapists using first graph
    therapists_thread = {
        "configurable": {
            "thread_id": f"{cfg.thread_id}_therapists"
        }
    }
    
    logger.info(f"Step 1: Generating therapists for patient case: {cfg.patient_case}")
    
    # Create session record
    patient_name = cfg.get('patient_name', f"Patient_{cfg.thread_id}")
    patient_id = cfg.get('patient_id', None)
    session = session_manager.create_session(
        thread_id=cfg.thread_id, 
        patient_name=patient_name, 
        patient_case=cfg.patient_case,
        patient_id=patient_id
    )
    
    # Run the therapist generation graph
    for event in therapists_graph.stream({"patient_case": cfg.patient_case}, therapists_thread, stream_mode="values"):
        logger.debug(f"Therapists graph event: {event}")
    
    # Get the generated therapists
    final_therapists_state = therapists_graph.get_state(therapists_thread)
    therapists = final_therapists_state.values.get('therapists')
    
    if not therapists:
        logger.error("No therapists were generated!")
        return
    
    logger.info(f"Generated {len(therapists)} therapists for analysis")
    
    # Step 2: Run therapy plan with parallel analysis using second graph
    therapy_thread = {
        "configurable": {
            "thread_id": f"{cfg.thread_id}_therapy"
        }
    }
    
    logger.info("Step 2: Running parallel case analysis and report generation")
    
    # Run the therapy plan graph with the generated therapists
    final_report = None
    sections = []
    
    for event in therapy_plan_graph.stream({
        "patient_case": cfg.patient_case,
        "therapists": therapists
    }, therapy_thread, stream_mode="values"):
        logger.info(f"Therapy plan graph event keys: {list(event.keys())}")
        logger.debug(f"Therapy plan graph event: {event}")
        
        # Capture sections (individual analysis results)
        if 'sections' in event:
            sections = event['sections']
            logger.info(f"Received {len(sections)} analysis sections")
            logger.debug(f"Sections content: {sections}")
        
        # Capture final synthesized report
        if 'final_report' in event:
            final_report = event['final_report']
            logger.info(f"Received final report: {final_report[:100] if final_report else 'None'}...")
    
    # Handle interactive follow-up chat (CLI only)
    current_state = therapy_plan_graph.get_state(therapy_thread)
    if current_state.next and 'user_follow_up' in current_state.next:
        logger.info("Starting interactive follow-up chat...")
        
        while True:
            try:
                # Get user input in CLI
                user_input = input("\n💬 Your question (or 'Done' to finish): ").strip()
                
                # Check if user wants to end
                if user_input.lower() in ['done', 'תם', 'סיום', 'גמור', '']:
                    # Update state to end conversation
                    therapy_plan_graph.update_state(
                        therapy_thread,
                        {"user_question": "Done"}
                    )
                    # Resume to end
                    for event in therapy_plan_graph.stream(None, therapy_thread, stream_mode="values"):
                        pass  # Just run to completion
                    break
                
                # Update state with user question
                therapy_plan_graph.update_state(
                    therapy_thread,
                    {"user_question": user_input}
                )
                
                # Resume graph execution
                for event in therapy_plan_graph.stream(None, therapy_thread, stream_mode="values"):
                    if 'chat_response' in event:
                        print(f"\n🗣️ Response: {event['chat_response']}")
                
            except KeyboardInterrupt:
                print("\n\n✅ Session ended. Thank you!")
                break
            except EOFError:
                print("\n\n✅ Session ended. Thank you!")
                break
    
    logger.info("Parallel therapy analysis and follow-up chat completed")
    
    if cfg.output.save_reports:
        # Save individual therapist reports (if we have the sections and therapists)
        if sections and therapists and len(sections) == len(therapists):
            logger.info("Saving individual therapist reports...")
            for section, therapist in zip(sections, therapists):
                # Create a mock report object with content
                class MockReport:
                    def __init__(self, content):
                        self.content = content
                
                mock_report = MockReport(section)
                patient_name = cfg.get('patient_name', f"Patient_{cfg.thread_id}")
                patient_id = cfg.get('patient_id', None)
                save_therapist_case_to_docx_file(mock_report, therapist, cfg.output, patient_name, patient_id)
                logger.info(f"Saved report for therapist: {therapist.name}")
        
        # Save the final synthesized report
        if final_report:
            patient_name = cfg.get('patient_name', f"Patient_{cfg.thread_id}")
            patient_id = cfg.get('patient_id', None)
            filepath = save_final_report_to_docx_file(final_report, cfg.patient_case, cfg.output, patient_name, patient_id)
            logger.info(f"Final therapy plan saved to: {filepath}")
        else:
            logger.warning("No final report generated")
    else:
        if final_report:
            logger.info(f"Final synthesized report: {final_report}")
        else:
            logger.warning("No final report generated")

def resume_session(thread_id: str):
    """Resume an existing therapy session"""
    logger = logging.getLogger(__name__)
    
    # Check if session exists
    session = session_manager.get_session(thread_id)
    if not session:
        logger.error(f"Session {thread_id} not found!")
        return
    
    logger.info(f"Resuming session: {session.patient_name} ({thread_id})")
    
    # Update activity
    session_manager.update_session_activity(thread_id)
    
    # Create thread for therapy plan graph
    therapy_thread = {
        "configurable": {
            "thread_id": f"{thread_id}_therapy"
        }
    }
    
    # Check the current state of the graph
    current_state = therapy_plan_graph.get_state(therapy_thread)
    
    if not current_state or not current_state.values:
        logger.error(f"No state found for thread {thread_id}. Cannot resume.")
        logger.info("This might be a session that was never started or completed.")
        return
    
    logger.info(f"Current state next nodes: {current_state.next}")
    
    # If we're at user_follow_up, resume the interactive chat
    if current_state.next and 'user_follow_up' in current_state.next:
        logger.info("Resuming at follow-up chat phase...")
        
        # Continue the graph execution from where it left off
        for event in therapy_plan_graph.stream(None, therapy_thread, stream_mode="values"):
            logger.debug(f"Resume event: {event}")
            
            # The user_follow_up node will handle the interactive input
            if 'chat_response' in event:
                logger.debug("Chat response generated")
    
    elif current_state.next:
        logger.info(f"Session is at: {current_state.next}. Continuing...")
        
        # Continue from wherever the graph stopped
        for event in therapy_plan_graph.stream(None, therapy_thread, stream_mode="values"):
            logger.debug(f"Resume event: {event}")
    
    else:
        logger.info("Session appears to be completed.")
        session_manager.mark_session_completed(thread_id)

def list_sessions():
    """List all therapy sessions"""
    sessions = session_manager.list_sessions()
    session_manager.print_sessions_table(sessions)
    return sessions

def search_sessions(patient_name: str = None, patient_id: str = None):
    """Search for sessions by patient name or ID"""
    sessions = session_manager.search_sessions(patient_name, patient_id)
    session_manager.print_sessions_table(sessions)
    return sessions

@hydra.main(version_base=None, config_path="config", config_name="config.yaml")
def main(cfg: DictConfig):
    """Main entry point with Hydra configuration"""
    
    # Check for resume mode
    if hasattr(cfg, 'resume_thread_id') and cfg.resume_thread_id:
        resume_session(cfg.resume_thread_id)
    elif hasattr(cfg, 'list_sessions') and cfg.list_sessions:
        list_sessions()
    elif hasattr(cfg, 'search_patient') and cfg.search_patient:
        search_sessions(patient_name=cfg.search_patient)
    else:
        run_parallel_analysis(cfg)

if __name__ == '__main__':
    main()

