from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.middleware import Middleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
import json
from datetime import datetime
import asyncio
import logging
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware

# Import your existing modules
from src.core.unified_graphs import build_unified_therapy_plan_graph, build_unified_therapists_graph, get_unified_checkpointer
from src.core.schema import TherapyPlanState, Therapist
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_openai import ChatOpenAI
from src.utils.report_formatter import format_report_to_html
from src.utils.config_loader import get_model_name, get_temperature, get_max_tokens
import sqlite3
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Lihi's Assistant API")

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key="lihi-assistant-secret-key-change-in-production-2024")

# Hardcoded credentials (in production, use environment variables or a database)
ALLOWED_EMAIL = "harellihi12@gmail.com"
ALLOWED_PASSWORD = "lihi1206"

# Authentication helper functions
def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated"""
    return request.session.get("authenticated", False) == True

def require_auth(request: Request):
    """Require authentication, redirect to login if not authenticated"""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")

# Mount static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Templates
templates = Jinja2Templates(directory="frontend/templates")

# Create database directory if it doesn't exist
os.makedirs("db", exist_ok=True)

# Global storage for session progress tracking only
session_states = {}

# Cached therapist profiles (eliminates 3-8s LLM call per session)
CACHED_THERAPISTS = [
    Therapist(
        affiliation="קלינאית תקשורת מוסמכת",
        name="ד״ר שרה כהן",
        role="מטפלת בדיבור ושפה",
        description="קלינאית תקשורת בכירה בעלת 15 שנות ניסיון בטיפול בילדים עם עיכובים בהתפתחות השפה וקשיי דיבור. מתמחה בהערכה אבחנתית מקיפה ובניית תכניות טיפול מותאמות אישית. גישה טיפולית משלבת שיטות מבוססות מחקר עם משחק ויצירתיות. מובילה את הצוות הרב-מקצועי ומשלבת את כל חוות הדעת המקצועיות לתכנית טיפול אחודה."
    ),
    Therapist(
        affiliation="מרפאה בעיסוק",
        name="גל שפירא",
        role="מרפא בעיסוק (OT)",
        description="מרפא בעיסוק מומחה בטיפול בילדים עם קשיים סנסוריים ומוטוריים. מתמקד באינטגרציה חושית, פיתוח מיומנויות עדינות וגסות, וקידום עצמאות בפעילויות יומיומיות. בעל ניסיון של 12 שנה בעבודה עם ילדים בגיל הרך."
    ),
    Therapist(
        affiliation="מטפלת התנהגותית ABA",
        name="נועה ברק",
        role="מטפלת התנהגותית",
        description="מטפלת התנהגותית מוסמכת בגישת ABA (Applied Behavior Analysis) עם התמחות בניהול התנהגויות מאתגרות ופיתוח מיומנויות חברתיות. מתמחה בבניית תוכניות התערבות מותאמות אישית ובשיתוף פעולה עם משפחות. ניסיון של 10 שנים בטיפול בילדים עם קשיים התנהגותיים."
    ),
    Therapist(
        affiliation="פסיכולוגית ילדים קלינית",
        name="ד״ר מיכל רוזנברג",
        role="פסיכולוגית ילדים",
        description="פסיכולוגית קלינית מומחית בהתפתחות הילד והמשפחה. מתמקדת בהיבטים רגשיים וחברתיים של התפתחות, אבחון קשיים נפשיים והתערבות טיפולית משפחתית. בעלת ניסיון של 18 שנה בעבודה עם ילדים ומשפחות במצבי משבר והתפתחות."
    ),
    Therapist(
        affiliation="יועצת חינוכית מיוחדת",
        name="איריס לוי",
        role="מומחית לחינוך מיוחד",
        description="יועצת חינוכית מומחית בחינוך מיוחד עם התמחות בליקויי למידה והתפתחות. מתמקדת בהתאמות פדגוגיות, פיתוח אסטרטגיות למידה, ושיתוף פעולה עם מסגרות חינוכיות. ניסיון של 14 שנה בליווי ילדים עם צרכים מיוחדים במערכת החינוך."
    )
]

# Pydantic models
class TherapySessionRequest(BaseModel):
    patient_id: str
    patient_case: str

class ChatMessage(BaseModel):
    thread_id: str
    message: str

class PatientData(BaseModel):
    patient_id: str
    patient_name: str

class SessionInfo(BaseModel):
    thread_id: str
    patient_id: str
    case_summary_preview: str
    created_at: str
    created_at_formatted: str
    status: str
    status_class: str
    status_text: str

# Helper functions
def load_patient_names() -> Dict[str, str]:
    """Load patient names mapping from JSON file"""
    try:
        with open('data/patient_names.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not load patient names: {e}")
        return {}

def save_patient_names(patient_names: Dict[str, str]) -> bool:
    """Save patient names mapping to JSON file"""
    try:
        os.makedirs("data", exist_ok=True)
        with open('data/patient_names.json', 'w', encoding='utf-8') as f:
            json.dump(patient_names, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Could not save patient names: {e}")
        return False

def get_patient_name(patient_id: str) -> str:
    """Get patient name from ID, with fallback to ID if not found"""
    patient_names = load_patient_names()
    return patient_names.get(patient_id, f"מטופל {patient_id}")

def format_hebrew_date(date_str: str) -> str:
    """Format date for Hebrew display"""
    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    months_hebrew = [
        'ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני',
        'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'
    ]
    return f"{date.day} ב{months_hebrew[date.month-1]} {date.year}, {date.hour:02d}:{date.minute:02d}"

def format_chat_response(response: str) -> str:
    """Format chat response for better display with proper line breaks and structure"""
    if not response:
        return response

    import re

    # Clean up the response
    response = response.strip()

    # Replace multiple spaces with single space (but preserve newlines)
    response = re.sub(r'[^\S\n]+', ' ', response)

    # Clean up multiple consecutive newlines (more than 2)
    response = re.sub(r'\n{3,}', '\n\n', response)

    # Remove trailing whitespace from each line
    response = '\n'.join(line.rstrip() for line in response.split('\n'))

    return response

def get_therapist_icon(therapist_type: str) -> str:
    """Get icon for therapist type"""
    icons = {
        'speech': 'fa-comment-dots',
        'ot': 'fa-hands-helping',
        'behavioral': 'fa-brain',
        'psychology': 'fa-heart',
        'special_ed': 'fa-graduation-cap'
    }
    return icons.get(therapist_type, 'fa-user-md')

# Graph and Checkpointer Management
def create_llm():
    """Create the configured LLM instance from config file"""
    return ChatOpenAI(
        model=get_model_name(),
        temperature=get_temperature(),
        max_tokens=get_max_tokens()
    )

def create_therapy_graph():
    """Create the main therapy graph"""
    llm = create_llm()
    return build_unified_therapy_plan_graph(llm)

def create_therapists_graph():
    """Create the therapists generation graph"""
    llm = create_llm()
    return build_unified_therapists_graph(llm)

def get_main_checkpointer():
    """Get the main checkpointer for all operations"""
    return get_unified_checkpointer()

# Routes
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    # If already authenticated, redirect to home
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    """Process login"""
    if email == ALLOWED_EMAIL and password == ALLOWED_PASSWORD:
        request.session["authenticated"] = True
        request.session["user_email"] = email
        return RedirectResponse(url="/", status_code=303)
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "כתובת אימייל או סיסמה שגויים"
        })

@app.get("/logout")
async def logout(request: Request):
    """Logout"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page - requires authentication"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/sessions", response_class=HTMLResponse)
def sessions_page(request: Request):
    """Sessions list page - requires authentication"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    checkpointer = get_main_checkpointer()
    sessions_data = []
    
    try:
        # Get all threads using the correct method
        threads = list(checkpointer.list(None))

        # Sort by timestamp (most recent first)
        threads.sort(key=lambda x: x.checkpoint.get('ts', ''), reverse=True)

        # Track unique thread_ids to avoid duplicates
        seen_threads = set()

        # Limit to last 50 unique sessions
        for checkpoint_tuple in threads:
            config = checkpoint_tuple.config
            checkpoint = checkpoint_tuple.checkpoint

            if checkpoint and 'channel_values' in checkpoint:
                values = checkpoint['channel_values']
                thread_id = config['configurable']['thread_id']

                # Skip therapist threads (those ending with _therapists)
                if thread_id.endswith('_therapists'):
                    continue

                # Skip if we've already seen this thread_id
                if thread_id in seen_threads:
                    continue

                # Check if this is a therapy session (has patient_id)
                if 'patient_id' in values and 'patient_case' in values:
                    patient_id = values['patient_id']

                    # Mark as seen
                    seen_threads.add(thread_id)

                    # Determine status based on state
                    if 'final_report' in values and values['final_report'] and values['final_report'] != 'דוח טרם הושלם':
                        status = 'completed'
                        status_class = 'success'
                        status_text = 'הושלם'
                    else:
                        status = 'in_progress'
                        status_class = 'warning'
                        status_text = 'בתהליך'

                    # Get creation timestamp from checkpoint
                    created_at = checkpoint.get('ts', datetime.now().isoformat())

                    session_info = {
                        'thread_id': thread_id,
                        'patient_id': patient_id,
                        'patient_name': get_patient_name(patient_id),
                        'case_summary_preview': values['patient_case'][:150] + '...' if len(values['patient_case']) > 150 else values['patient_case'],
                        'created_at': created_at,
                        'created_at_formatted': format_hebrew_date(created_at),
                        'status': status,
                        'status_class': status_class,
                        'status_text': status_text
                    }
                    sessions_data.append(session_info)

                    # Stop after 50 unique sessions
                    if len(sessions_data) >= 50:
                        break
    
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        # Fallback to empty sessions if there's an error
        sessions_data = []
    
    return templates.TemplateResponse("sessions.html", {
        "request": request,
        "sessions": sessions_data
    })

@app.get("/report/{thread_id}", response_class=HTMLResponse)
def report_page(request: Request, thread_id: str):
    """Report page - requires authentication"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    graph = create_therapy_graph()
    
    try:
        # Get the latest state for this thread
        config = {"configurable": {"thread_id": thread_id}}
        state = graph.get_state(config)
        
        if not state or not state.values:
            raise HTTPException(status_code=404, detail="Report not found")
        
        values = state.values
        
        # Debug logging
        logger.info(f"Loading report for thread {thread_id}")
        logger.info(f"State keys: {list(values.keys())}")
        if 'therapists' in values:
            logger.info(f"Number of therapists: {len(values['therapists'])}")
        if 'sections' in values:
            logger.info(f"Number of sections: {len(values['sections'])}")
        else:
            logger.warning("No sections found in state")
        
        # Prepare therapist data
        therapists_data = []
        therapist_analyses = {}
        
        if 'therapists' in values:
            for i, therapist in enumerate(values['therapists']):
                therapist_id = f"therapist_{i}"
                therapist_type = ['speech', 'ot', 'behavioral', 'psychology', 'special_ed'][i % 5]
                
                therapists_data.append({
                    'id': therapist_id,
                    'name': therapist.name,
                    'title': therapist.description.split('.')[0] if therapist.description else therapist.role,  # First sentence as title
                    'icon': get_therapist_icon(therapist_type)
                })
                
                # Get analysis data from sections (individual therapist reports)
                analysis_content = "אין ניתוח זמין למטפל זה"  # Default message
                
                if 'sections' in values and values['sections']:
                    if i < len(values['sections']) and values['sections'][i]:
                        # Extract the analysis from the section content
                        section_content = values['sections'][i]
                        
                        # Try different patterns to extract the analysis
                        analysis_content = section_content
                        if ". my detailed case analysis: " in section_content:
                            analysis_content = section_content.split(". my detailed case analysis: ", 1)[1].rstrip('.')
                        elif "my detailed case analysis: " in section_content:
                            analysis_content = section_content.split("my detailed case analysis: ", 1)[1].rstrip('.')
                        elif "ניתוח מקצועי" in section_content:
                            # If Hebrew analysis header is found, use the content as-is
                            analysis_content = section_content
                elif 'final_report' in values and values['final_report']:
                    # Fallback: try to extract therapist-specific content from final report
                    final_report = values['final_report']
                    therapist_name = therapist.name
                    
                    # Look for therapist name in final report and extract their section
                    if therapist_name in final_report:
                        # This is a basic fallback - could be improved
                        analysis_content = f"ניתוח זה נכלל בדוח הכללי. מטפל: {therapist_name}"
                
                therapist_analyses[therapist_id] = {
                    'name': therapist.name,
                    'title': therapist.description.split('.')[0] if therapist.description else therapist.role,
                    'analysis': analysis_content
                }
        
        # Get chat history if exists
        chat_history = values.get('chat_history', [])
        
        patient_id = values.get('patient_id', 'Unknown')
        
        # Format the final report from semantic markers to HTML
        final_report_raw = values.get('final_report', 'דוח טרם הושלם')
        final_report_html = format_report_to_html(final_report_raw) if final_report_raw != 'דוח טרם הושלם' else final_report_raw
        
        # Format therapist analyses from semantic markers to HTML
        formatted_analyses = {}
        for therapist_id, analysis in therapist_analyses.items():
            formatted_analyses[therapist_id] = {
                'name': analysis['name'],
                'title': analysis['title'],
                'analysis': format_report_to_html(analysis['analysis'])
            }

        return templates.TemplateResponse("report.html", {
            "request": request,
            "thread_id": thread_id,
            "patient_id": patient_id,
            "patient_name": get_patient_name(patient_id) if patient_id != 'Unknown' else 'לא ידוע',
            "report_date": format_hebrew_date(state.metadata.get('created_at', datetime.now().isoformat())),
            "patient_case": values.get('patient_case', ''),
            "final_report": final_report_html,
            "therapists": therapists_data,
            "therapist_analyses": formatted_analyses,
            "chat_history": chat_history,
            "download_url": f"/api/download-report/{thread_id}"
        })
    
    except Exception as e:
        logger.error(f"Error loading report: {e}")
        raise HTTPException(status_code=500, detail="Error loading report")

# API Endpoints
@app.post("/api/start-therapy")
async def start_therapy(therapy_request: TherapySessionRequest, request: Request, background_tasks: BackgroundTasks):
    """Start a new therapy session - requires authentication"""
    require_auth(request)
    try:
        # Create unique thread ID
        thread_id = str(uuid.uuid4())

        # Initialize state
        initial_state = {
            "patient_id": therapy_request.patient_id,
            "patient_case": therapy_request.patient_case
        }
        
        # Store in session states
        session_states[thread_id] = {
            'status': 'initializing',
            'progress': 0,
            'created_at': datetime.now().isoformat()
        }
        
        # Run the graph in the background
        background_tasks.add_task(run_therapy_graph, thread_id, initial_state)
        
        return {"thread_id": thread_id, "status": "started"}
    
    except Exception as e:
        logger.error(f"Error starting therapy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def run_therapy_graph(thread_id: str, initial_state: dict):
    """Run the therapy graph asynchronously"""
    try:
        # Update progress
        session_states[thread_id]['status'] = 'מאתחל צוות מטפלים...'
        session_states[thread_id]['progress'] = 10

        # Use cached therapists (skips 3-8s LLM call)
        logger.info(f"Using {len(CACHED_THERAPISTS)} cached therapists (skipping creation)")

        session_states[thread_id]['status'] = 'טוען צוות מטפלים...'
        session_states[thread_id]['progress'] = 20

        # Now run the main therapy graph with cached therapists
        therapy_graph = create_therapy_graph()
        config = {"configurable": {"thread_id": thread_id}}

        # Add cached therapists to the initial state
        therapy_state = initial_state.copy()
        therapy_state['therapists'] = CACHED_THERAPISTS
        
        session_states[thread_id]['status'] = 'מטפלים מנתחים את המקרה...'
        session_states[thread_id]['progress'] = 40
        
        # Execute the main therapy graph (parallel therapist analysis preserved!)
        for event in therapy_graph.stream(therapy_state, config):
            # Update progress based on the node
            node_name = list(event.keys())[0] if event else ""
            
            if 'conduct_analysis' in node_name:
                session_states[thread_id]['status'] = 'מטפלים מנתחים את המקרה...'
                session_states[thread_id]['progress'] = 60
            elif 'generate_report' in node_name:
                session_states[thread_id]['status'] = 'מסנתז דוח מקיף...'
                session_states[thread_id]['progress'] = 90
        
        # Mark as completed
        session_states[thread_id]['status'] = 'הושלם'
        session_states[thread_id]['progress'] = 100
        session_states[thread_id]['state'] = 'completed'
        
        # Clean up session state after 5 minutes to free memory
        import threading
        import time
        def cleanup_session():
            time.sleep(300)  # 5 minutes
            if thread_id in session_states:
                del session_states[thread_id]
        
        cleanup_thread = threading.Thread(target=cleanup_session)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
    except Exception as e:
        logger.error(f"Error in therapy graph: {e}")
        session_states[thread_id]['state'] = 'error'
        session_states[thread_id]['error'] = str(e)

@app.get("/api/session-status/{thread_id}")
def get_session_status(thread_id: str):
    """Get the current status of a therapy session"""
    if thread_id not in session_states:
        # Check if the session exists in the database
        graph = create_therapy_graph()
        config = {"configurable": {"thread_id": thread_id}}
        state = graph.get_state(config)
        
        if state and state.values:
            # Session exists in DB, check completion status
            if 'final_report' in state.values and state.values['final_report']:
                return {
                    'status': 'הושלם',
                    'progress': 100,
                    'state': 'completed'
                }
            else:
                return {
                    'status': 'בתהליך',
                    'progress': 50,
                    'state': 'in_progress'
                }
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    
    return session_states[thread_id]

@app.get("/api/check-sessions/{patient_id}")
def check_sessions(patient_id: str):
    """Check if patient has previous sessions"""
    checkpointer = get_main_checkpointer()
    sessions = []
    
    try:
        # Get all threads using the correct method
        threads = list(checkpointer.list(None))
        
        for checkpoint_tuple in threads:
            config = checkpoint_tuple.config
            checkpoint = checkpoint_tuple.checkpoint
            
            if checkpoint and 'channel_values' in checkpoint:
                values = checkpoint['channel_values']
                thread_id = config['configurable']['thread_id']
                
                # Skip therapist threads
                if thread_id.endswith('_therapists'):
                    continue
                
                # Check if this session belongs to the specified patient
                if values.get('patient_id') == patient_id:
                    sessions.append({
                        'thread_id': thread_id,
                        'created_at': checkpoint.get('ts', '')
                    })
        
        # Sort by creation time, most recent first
        sessions.sort(key=lambda x: x['created_at'], reverse=True)
    
    except Exception as e:
        logger.error(f"Error checking sessions: {e}")
    
    return {"sessions": sessions}

@app.get("/api/sessions")
def get_all_sessions():
    """Get all therapy sessions for the sessions panel"""
    checkpointer = get_main_checkpointer()
    sessions_data = []

    try:
        # Get all threads using the correct method
        threads = list(checkpointer.list(None))

        # Sort by timestamp (most recent first)
        threads.sort(key=lambda x: x.checkpoint.get('ts', ''), reverse=True)

        # Track unique thread_ids to avoid duplicates
        seen_threads = set()

        for checkpoint_tuple in threads:
            config = checkpoint_tuple.config
            checkpoint = checkpoint_tuple.checkpoint

            if checkpoint and 'channel_values' in checkpoint:
                values = checkpoint['channel_values']
                thread_id = config['configurable']['thread_id']

                # Skip therapist threads (those ending with _therapists)
                if thread_id.endswith('_therapists'):
                    continue

                # Skip if we've already seen this thread_id
                if thread_id in seen_threads:
                    continue

                if 'patient_id' in values and 'patient_case' in values:
                    patient_id = values['patient_id']

                    # Mark as seen
                    seen_threads.add(thread_id)

                    # Determine status
                    if 'final_report' in values and values['final_report'] and values['final_report'] != 'דוח טרם הושלם':
                        status = 'completed'
                    else:
                        status = 'in_progress'

                    created_at = checkpoint.get('ts', datetime.now().isoformat())

                    session_info = {
                        'thread_id': thread_id,
                        'patient_id': patient_id,
                        'patient_name': get_patient_name(patient_id),
                        'case_summary_preview': values['patient_case'][:120] + '...' if len(values['patient_case']) > 120 else values['patient_case'],
                        'created_at': created_at,
                        'created_at_formatted': format_hebrew_date(created_at),
                        'status': status
                    }
                    sessions_data.append(session_info)

                    # Limit to 20 unique sessions
                    if len(sessions_data) >= 20:
                        break
    
    except Exception as e:
        logger.error(f"Error fetching all sessions: {e}")
    
    return {"sessions": sessions_data}

@app.delete("/api/delete-session/{thread_id}")
def delete_session(thread_id: str):
    """Delete a therapy session from the database"""
    try:
        checkpointer = get_main_checkpointer()

        # Get all checkpoints for this thread and delete them
        # Note: SqliteSaver doesn't have a direct delete method, so we use raw SQL
        conn = checkpointer.conn

        # Delete from both tables for this thread_id
        cursor = conn.cursor()

        # Delete from checkpoints table
        cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        checkpoint_count = cursor.rowcount

        # Delete from writes table
        cursor.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
        writes_count = cursor.rowcount

        conn.commit()

        logger.info(f"Deleted thread {thread_id}: {checkpoint_count} checkpoints, {writes_count} writes")

        return {"success": True, "deleted_checkpoints": checkpoint_count, "deleted_writes": writes_count}

    except Exception as e:
        logger.error(f"Error deleting session {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Error deleting session")

@app.post("/api/chat")
def chat_with_report(message: ChatMessage):
    """Chat about the therapy report with Dr. Sarah Cohen (lead therapist) - uses LangGraph"""
    try:
        graph = create_therapy_graph()
        config = {"configurable": {"thread_id": message.thread_id}}

        # Get current state
        current_state = graph.get_state(config)
        if not current_state:
            raise HTTPException(status_code=404, detail="Session not found")

        values = current_state.values

        # Validate we have therapists
        therapists_list = values.get('therapists', [])
        if not therapists_list or len(therapists_list) == 0:
            logger.error(f"No therapists found in state for thread {message.thread_id}")
            raise HTTPException(status_code=500, detail="Therapists not found. Please regenerate the report.")

        # Invoke graph with chat state
        # The graph will route to lead_chat node based on chat_message presence
        chat_input = {
            "chat_message": message.message,
            "chat_specialist_index": 0
        }

        result = graph.invoke(chat_input, config)
        raw_response = result.get('chat_response', 'מצטער, לא הצלחתי לעבד את השאלה.')
        formatted_response = format_chat_response(raw_response)

        # Update state with chat history
        try:
            chat_history = values.get('chat_history', [])
            chat_history.extend([
                {"role": "user", "content": message.message},
                {"role": "assistant", "content": formatted_response}
            ])
            graph.update_state(config, {"chat_history": chat_history})
        except Exception as e:
            logger.warning(f"Could not update chat history: {e}")

        return {"response": formatted_response}

    except Exception as e:
        logger.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail="Error processing message")

class SpecialistChatMessage(BaseModel):
    thread_id: str
    therapist_index: int
    message: str

class ParentLetterRequest(BaseModel):
    thread_id: str
    user_summary: str  # User's additional input for the letter
    word_count: int = 500  # Number of words for the letter (default 500)

@app.post("/api/specialist-chat")
def chat_with_specialist(message: SpecialistChatMessage):
    """Chat with a specific therapist from the team - uses LangGraph"""
    try:
        graph = create_therapy_graph()
        config = {"configurable": {"thread_id": message.thread_id}}

        # Get current state
        current_state = graph.get_state(config)
        if not current_state:
            raise HTTPException(status_code=404, detail="Session not found")

        values = current_state.values

        # Validate therapist index
        therapists_list = values.get('therapists', [])
        if message.therapist_index < 0 or message.therapist_index >= len(therapists_list):
            raise HTTPException(status_code=400, detail="Invalid therapist index")

        therapist = therapists_list[message.therapist_index]

        # Invoke graph with chat state
        # The graph will route to appropriate chat node based on specialist_index
        chat_input = {
            "chat_message": message.message,
            "chat_specialist_index": message.therapist_index
        }

        result = graph.invoke(chat_input, config)
        raw_response = result.get('chat_response', 'מצטער, לא הצלחתי לעבד את השאלה.')
        formatted_response = format_chat_response(raw_response)

        # Update therapist chat history in state
        therapist_chat_history = values.get('therapist_chat_history', {})
        history_key = str(message.therapist_index)

        if history_key not in therapist_chat_history:
            therapist_chat_history[history_key] = []

        therapist_chat_history[history_key].extend([
            {"role": "user", "content": message.message},
            {"role": "assistant", "content": formatted_response}
        ])

        graph.update_state(config, {"therapist_chat_history": therapist_chat_history})

        return {
            "response": formatted_response,
            "therapist_name": therapist.name,
            "therapist_role": therapist.role
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in specialist chat: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@app.post("/api/generate-parent-letter")
async def generate_parent_letter(request: ParentLetterRequest, http_request: Request):
    """Generate a letter to parents based on the therapy report"""
    require_auth(http_request)
    try:
        graph = create_therapy_graph()
        config = {"configurable": {"thread_id": request.thread_id}}

        # Get current state
        current_state = graph.get_state(config)
        if not current_state:
            raise HTTPException(status_code=404, detail="Session not found")

        values = current_state.values
        final_report = values.get('final_report', '')
        patient_id = values.get('patient_id', '')
        patient_case = values.get('patient_case', '')

        if not final_report:
            raise HTTPException(status_code=400, detail="No report found for this session")

        # Build prompt for parent letter
        from langchain_core.messages import SystemMessage, HumanMessage

        # Calculate word distribution based on total word count
        word_count = request.word_count
        intro_words = int(word_count * 0.15)  # ~15%
        findings_words = int(word_count * 0.35)  # ~35%
        recommendations_words = int(word_count * 0.35)  # ~35%
        conclusion_words = int(word_count * 0.15)  # ~15%

        prompt = f"""אתה קלינאי תקשורת מומחה. עליך לכתוב מכתב להורים של ילד שעבר הערכה קלינית.

**מידע על המטופל:**
{patient_case}

**הדוח המקצועי המלא:**
{final_report}

**מיקוד מבוקש מההורים:**
{request.user_summary}

**הוראות:**
כתוב מכתב להורים ב-{word_count} מילים בדיוק. המכתב צריך להיות:
1. מנוסח בשפה פשוטה וברורה, ללא ז'רגון מקצועי
2. מתחיל בפתיחה חמה ומעודדת
3. מסביר את הממצאים העיקריים בקצרה
4. מתמקד ב{request.user_summary}
5. כולל צעדים בהירים והמלצות מעשיות לבית
6. מסתיים בתקווה ועידוד

**פורמט:**
- פסקה 1 ({intro_words} מילים): פתיחה חמה וסיכום כללי
- פסקה 2 ({findings_words} מילים): ממצאים עיקריים ומיקוד על {request.user_summary}
- פסקה 3 ({recommendations_words} מילים): המלצות מעשיות לבית - צעדים ברורים שההורים יכולים לעשות
- פסקה 4 ({conclusion_words} מילים): סיכום מעודד וצעדים הבאים

כתוב את המכתב בעברית."""

        messages = [
            SystemMessage(content="אתה קלינאי תקשורת מנוסה הכותב מכתבים להורים."),
            HumanMessage(content=prompt)
        ]

        # Generate letter
        llm = create_llm()
        response = llm.invoke(messages)
        letter = response.content.strip()

        # Store in state
        graph.update_state(config, {"parent_letter": letter, "parent_letter_input": request.user_summary})

        return {
            "success": True,
            "letter": letter,
            "patient_name": get_patient_name(patient_id)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating parent letter: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating letter: {str(e)}")

@app.post("/api/resume-session/{thread_id}")
def resume_session(thread_id: str, background_tasks: BackgroundTasks):
    """Resume an incomplete session"""
    try:
        graph = create_therapy_graph()
        config = {"configurable": {"thread_id": thread_id}}
        
        # Check if session exists
        current_state = graph.get_state(config)
        if not current_state:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Resume the graph execution from current state
        session_states[thread_id] = {
            'status': 'ממשיך טיפול...',
            'progress': 50,
            'state': 'resuming'
        }
        
        # Resume execution (no initial state needed - continues from checkpoint)
        def resume_execution():
            try:
                for event in graph.stream(None, config):
                    pass  # Process remaining graph events

                session_states[thread_id]['status'] = 'הושלם'
                session_states[thread_id]['progress'] = 100
                session_states[thread_id]['state'] = 'completed'
                
            except Exception as e:
                logger.error(f"Error resuming execution: {e}")
                session_states[thread_id]['state'] = 'error'
                session_states[thread_id]['error'] = str(e)
        
        background_tasks.add_task(resume_execution)
        
        return {"status": "resumed"}
    
    except Exception as e:
        logger.error(f"Error resuming session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/duplicate-session/{thread_id}")
def duplicate_session(thread_id: str):
    """Duplicate a session for a new therapy"""
    try:
        graph = create_therapy_graph()
        config = {"configurable": {"thread_id": thread_id}}
        
        # Get the session state
        state = graph.get_state(config)
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")
        
        values = state.values
        
        return {
            "patient_id": values.get('patient_id', ''),
            "case_summary": values.get('patient_case', '')
        }
    
    except Exception as e:
        logger.error(f"Error duplicating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download-report/{thread_id}")
def download_report(thread_id: str):
    """Download report as Word document - generate if not exists"""
    try:
        # Get the session data
        graph = create_therapy_graph()
        config = {"configurable": {"thread_id": thread_id}}
        state = graph.get_state(config)
        
        if not state or not state.values:
            raise HTTPException(status_code=404, detail="Session not found")
        
        values = state.values
        patient_id = values.get('patient_id', 'unknown')
        
        # Create reports directory if it doesn't exist
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        # Try different possible file paths
        possible_paths = [
            f"reports/{thread_id}.docx",
            f"reports/patient_{patient_id}_report.docx",
            f"reports/{patient_id}.docx"
        ]
        
        report_path = None
        for path_str in possible_paths:
            path = Path(path_str)
            if path.exists():
                report_path = path
                break
        
        # If no existing file, generate a basic Word document
        if not report_path:
            from docx import Document
            doc = Document()

            # Add content to document
            doc.add_heading(f'דוח טיפול למטופל {get_patient_name(patient_id)}', 0)
            doc.add_paragraph(f'מזהה מטופל: {patient_id}')
            doc.add_paragraph(f'תאריך: {datetime.now().strftime("%d/%m/%Y")}')

            # Add final report if available
            if 'final_report' in values and values['final_report']:
                doc.add_heading('דוח טיפול משולב', 1)
                doc.add_paragraph(values['final_report'])

            # Save the document
            report_path = reports_dir / f"{thread_id}.docx"
            doc.save(str(report_path))
            logger.info(f"Generated new Word document: {report_path}")
        
        return FileResponse(
            path=str(report_path),
            filename=f"therapy_report_{patient_id}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    
    except Exception as e:
        logger.error(f"Error downloading report: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

# Patient Management Endpoints
@app.get("/api/patients")
def get_patients():
    """Get all patients"""
    try:
        patient_names = load_patient_names()
        patients = [
            {"id": patient_id, "name": name} 
            for patient_id, name in patient_names.items()
        ]
        # Sort by name
        patients.sort(key=lambda x: x['name'])
        return {"patients": patients}
    
    except Exception as e:
        logger.error(f"Error getting patients: {e}")
        raise HTTPException(status_code=500, detail="Error loading patients")

@app.post("/api/patients")
def add_patient(patient_data: PatientData):
    """Add a new patient"""
    try:
        patient_names = load_patient_names()
        
        # Check if patient ID already exists
        if patient_data.patient_id in patient_names:
            raise HTTPException(status_code=400, detail="Patient ID already exists")
        
        # Add new patient
        patient_names[patient_data.patient_id] = patient_data.patient_name
        
        # Save to file
        if not save_patient_names(patient_names):
            raise HTTPException(status_code=500, detail="Could not save patient data")
        
        logger.info(f"Added new patient: {patient_data.patient_id} - {patient_data.patient_name}")
        return {"success": True, "message": "Patient added successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding patient: {e}")
        raise HTTPException(status_code=500, detail="Error adding patient")

@app.delete("/api/patients/{patient_id}")
def delete_patient(patient_id: str):
    """Delete a patient"""
    try:
        patient_names = load_patient_names()
        
        # Check if patient exists
        if patient_id not in patient_names:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Remove patient
        patient_name = patient_names.pop(patient_id)
        
        # Save to file
        if not save_patient_names(patient_names):
            raise HTTPException(status_code=500, detail="Could not save patient data")
        
        logger.info(f"Deleted patient: {patient_id} - {patient_name}")
        return {"success": True, "message": "Patient deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting patient: {e}")
        raise HTTPException(status_code=500, detail="Error deleting patient")

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7777)