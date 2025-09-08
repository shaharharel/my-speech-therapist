# import all necessary modules
import json
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState, END
from .schema import Therapists, GenerateTherapistsState, CaseAnalysisState, TherapyPlanState
from . import prompts
from langchain_core.messages import SystemMessage, HumanMessage


class CreateTherapists:
    def __init__(self, llm):
        self.llm = llm

    def __call__(self, state: GenerateTherapistsState):
        """ Create analysts """
        patient_case = state['patient_case']
        # human_analyst_feedback = state.get('human_analyst_feedback', '')

        # Enforce structured output
        structured_llm = self.llm.with_structured_output(Therapists)

        # System message
        system_message = prompts.therapists_prompt

        # Generate question
        therapists = structured_llm.invoke(
            [SystemMessage(content=system_message)] + [
                HumanMessage(content="Generate the set of therapists. provide your final answer in hebrew")])

        # Write the list of analysis to state
        return {"therapists": therapists.therapists}


class ProcessSearchResults:
    def __init__(self, llm):
        self.llm = llm

    def __call__(self, state: MessagesState):
        """ Node to answer a question """

        # Get state
        search_docs = json.loads(state["messages"][-1].content)["results"]
        formatted_search_docs = ["Title: " + i['title'] + "Content: " + i['content'] for i in search_docs]

        # docs_summary_prompt
        docs_summary_prompt = """summarize each of the following cases. for each one use title, general details summarized description and main takeaways in the context of the case discussed earlier: {formatted_search_docs}"""

        # Answer
        answer = self.llm.invoke(
            [SystemMessage(content=docs_summary_prompt.format(formatted_search_docs=formatted_search_docs))])

        # Append it to state
        return {"messages": answer}


class Chatbot:
    def __init__(self, llm_with_tools):
        self.llm_with_tools = llm_with_tools

    def __call__(self, state: MessagesState):
        """ Node to answer a question """
        # Get state
        sys_message = prompts.sys_message

        # Invoke the LLM with tools
        return {"messages": [self.llm_with_tools.invoke([SystemMessage(content=sys_message)] + state["messages"])]}


# lets write the class that does the same as process_search_results with __init__ and __call__ methods

class AnalyzeCase:
    def __init__(self, llm):
        self.llm = llm

    def __call__(self, state: CaseAnalysisState):
        """ Analyze the case with the therapist """
        # copy analyze_case function here
        prompt = prompts.analyze_case_prompt
        # Get state - extract case from the message content (like research assistant)
        case = state["messages"][0].content if state["messages"] else "No case provided"
        therapist = state["therapist"]
        prompt = prompt.format(FIELD=therapist.role, CASE=case, DETAILS=therapist.persona)
        res = self.llm.invoke([SystemMessage(content=prompt)] + [HumanMessage(content="החזר את האנליזה שלך בעברית")])
        
        # Include therapist details in the section using persona property for clear attribution in final report
        section_with_therapist = f"""{therapist.persona}. my detailed case analysis: {res.content}."""
        
        return {"report": res, "sections": [section_with_therapist]}



# lets write the class that does the same as generate_report with __init__ and __call__ methods
class GenerateReport:
    def __init__(self, llm):
        self.llm = llm

    def __call__(self, state: TherapyPlanState):
        """ Generate a report based on the parallel analysis sections """
        # Get all sections from parallel execution (like research assistant)
        sections = state.get("sections", [])
        patient_case = state["patient_case"]
        
        if not sections:
            return {"final_report": "No analysis sections generated"}
        
        # Combine all therapist analysis sections
        combined_sections = "\n\n".join([f"{section}" for section in sections])
        
        # Use the proper synthesis_report_prompt from prompts.py
        synthesis_prompt = prompts.synthesis_report_prompt.format(
            patient_case=patient_case,
            combined_sections=combined_sections
        )
        
        # Generate final synthesized report
        final_report = self.llm.invoke([SystemMessage(content=synthesis_prompt)])
        
        return {"final_report": final_report.content}


class FollowUpChat:
    def __init__(self, llm):
        self.llm = llm

    def __call__(self, state: TherapyPlanState):
        """ Provide follow-up discussion about the therapy report """
        # Get state
        final_report = state.get("final_report", "")
        user_question = state.get("user_question", "")
        patient_case = state.get("patient_case", "")
        
        # Chat prompt for follow-up discussion
        chat_prompt = f"""
        You are a senior speech therapist providing follow-up consultation about a therapy plan.
        
        Original Patient Case: {patient_case}
        
        Generated Therapy Plan:
        {final_report}
        
        User Question: {user_question}
        
        Please provide a helpful, professional response addressing the user's question about the therapy plan.
        Consider implementation details, timeline, potential challenges, and practical advice.
        
        IMPORTANT FORMATTING INSTRUCTIONS:
        - Write in Hebrew with clear, readable formatting
        - Use short paragraphs (2-3 sentences each) for better readability
        - Add line breaks between different topics or points
        - Use bullet points when listing multiple items (use • or -)
        - Keep sentences concise and focused
        - Structure your response with clear sections if covering multiple topics
        
        Example format:
        תשובה קצרה לשאלה הראשית.
        
        נקודה ראשונה להרחבה עם הסבר מפורט.
        
        נקודה שנייה חשובה:
        • פריט ראשון
        • פריט שני
        • פריט שלישי
        
        סיכום והמלצה מעשית.
        """
        
        # Generate response
        response = self.llm.invoke([SystemMessage(content=chat_prompt)])
        
        # Display the response nicely
        print("\n" + "-"*60)
        print("🗣️ SPEECH THERAPIST RESPONSE:")
        print("-"*60)
        print(response.content)
        print("-"*60)
        
        return {"chat_response": response.content}


def user_follow_up(state: TherapyPlanState):
    """ Interactive node that uses interrupts instead of blocking input """
    from langgraph.errors import NodeInterrupt
    
    # Check if we already have a user question from external input
    if 'user_question' in state and state['user_question']:
        # User question was provided externally (UI or resumed CLI)
        return {"user_question": state['user_question']}
    
    # For CLI: show prompt and interrupt to wait for external input
    print("\n" + "="*60)
    print("📋 THERAPY REPORT GENERATED")
    print("="*60)
    print("You can now ask follow-up questions about the therapy plan.")
    print("Type 'Done' (or תם/סיום/גמור) to finish the session.")
    print("-"*60)
    
    # Interrupt the graph to wait for external input
    raise NodeInterrupt("Waiting for user question")


def should_continue_chat(state: TherapyPlanState):
    """ Route between continuing chat or ending """
    
    # Check if user wants to continue
    user_question = state.get('user_question', '').strip().lower()
    
    # If user typed "Done" (case insensitive), end the conversation
    if user_question in ['done', 'תם', 'סיום', 'גמור']:
        return END
    
    # If there's a question, continue to chat
    if user_question:
        return "follow_up_chat"
    
    # Default to ending if no valid input
    return END


