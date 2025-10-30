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


class SpecialistChat:
    """Chat node for individual specialists - each uses their own analysis as context"""
    def __init__(self, llm):
        self.llm = llm

    def __call__(self, state: TherapyPlanState):
        """Handle chat with a specific specialist"""
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        from . import prompts

        # Get the specialist index and message from state
        specialist_index = state.get("chat_specialist_index", 0)
        user_message = state.get("chat_message", "")

        if not user_message:
            return {"chat_response": ""}

        # Get specialist and their analysis
        therapists = state.get("therapists", [])
        sections = state.get("sections", [])

        if specialist_index >= len(therapists):
            return {"chat_response": "מטפל לא נמצא"}

        therapist = therapists[specialist_index]
        therapist_analysis = sections[specialist_index] if specialist_index < len(sections) else ""

        # Build context-aware prompt using prompts file
        system_prompt = prompts.specialist_chat_prompt.format(
            therapist_name=therapist.name,
            therapist_role=therapist.role,
            therapist_analysis=therapist_analysis[:500] + "..."
        )

        # Get chat history for this specialist
        therapist_chat_history = state.get("therapist_chat_history", {})
        history_key = str(specialist_index)
        history = therapist_chat_history.get(history_key, [])

        # Build messages
        messages = [SystemMessage(content=system_prompt)]
        for msg in history:
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            else:
                messages.append(AIMessage(content=msg['content']))

        messages.append(HumanMessage(content=user_message))

        # Generate response
        response = self.llm.invoke(messages)

        return {"chat_response": response.content}


class LeadTherapistChat:
    """Chat node for Dr. Sarah Cohen - has access to final report and all analyses"""
    def __init__(self, llm):
        self.llm = llm

    def __call__(self, state: TherapyPlanState):
        """Handle chat with lead therapist (Sarah Cohen)"""
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        from . import prompts

        user_message = state.get("chat_message", "")

        if not user_message:
            return {"chat_response": ""}

        # Get full context for lead therapist
        final_report = state.get("final_report", "")
        therapists = state.get("therapists", [])
        sections = state.get("sections", [])

        if not therapists:
            return {"chat_response": "מטפלים לא נמצאו"}

        lead_therapist = therapists[0]
        lead_analysis = sections[0] if sections else ""

        # Build context with all information using prompts file
        system_prompt = prompts.lead_therapist_chat_prompt.format(
            lead_analysis=lead_analysis[:500] + "...",
            final_report=final_report[:500] + "..."
        )

        # Get chat history
        chat_history = state.get("chat_history", [])

        # Build messages
        messages = [SystemMessage(content=system_prompt)]
        for msg in chat_history:
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            else:
                messages.append(AIMessage(content=msg['content']))

        messages.append(HumanMessage(content=user_message))

        # Generate response
        response = self.llm.invoke(messages)

        return {"chat_response": response.content}


