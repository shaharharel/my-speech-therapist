#!/usr/bin/env python3
"""
CLI tool for managing therapy sessions
"""
import argparse
import sys
from session_manager import SessionManager
from run import resume_session, list_sessions, search_sessions

def main():
    parser = argparse.ArgumentParser(description="Therapy Session Management CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List sessions
    list_parser = subparsers.add_parser('list', help='List all therapy sessions')
    list_parser.add_argument('--status', choices=['active', 'completed'], 
                           help='Filter by session status')
    
    # Search sessions
    search_parser = subparsers.add_parser('search', help='Search for sessions')
    search_parser.add_argument('--name', help='Search by patient name')
    search_parser.add_argument('--id', help='Search by patient ID')
    
    # Resume session
    resume_parser = subparsers.add_parser('resume', help='Resume a therapy session')
    resume_parser.add_argument('thread_id', help='Thread ID of the session to resume')
    
    # Show session details
    show_parser = subparsers.add_parser('show', help='Show session details')
    show_parser.add_argument('thread_id', help='Thread ID of the session to show')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    session_manager = SessionManager()
    
    if args.command == 'list':
        sessions = session_manager.list_sessions(status=args.status)
        session_manager.print_sessions_table(sessions)
        
    elif args.command == 'search':
        sessions = search_sessions(patient_name=args.name, patient_id=args.id)
        
    elif args.command == 'resume':
        print(f"Resuming session: {args.thread_id}")
        resume_session(args.thread_id)
        
    elif args.command == 'show':
        session = session_manager.get_session(args.thread_id)
        if session:
            print(f"\nSession Details:")
            print(f"Thread ID: {session.thread_id}")
            print(f"Patient Name: {session.patient_name}")
            print(f"Patient ID: {session.patient_id or 'N/A'}")
            print(f"Created: {session.created_at}")
            print(f"Last Activity: {session.last_activity}")
            print(f"Status: {session.status}")
            print(f"\nPatient Case:")
            print(session.patient_case)
        else:
            print(f"Session {args.thread_id} not found.")

if __name__ == "__main__":
    main()