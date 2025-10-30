#import all relevant modules
from typing import List, TypedDict, Annotated
from pydantic import BaseModel, Field
import operator
from langgraph.graph import MessagesState


class Therapist(BaseModel):
    affiliation: str = Field(
        description="Primary affiliation of the therapist.",
    )
    name: str = Field(
        description="Name of the therapist."
    )
    role: str = Field(
        description="Role of the therapist.",
    )
    description: str = Field(
        description="Description of the therapist focus, concerns, and motives.",
    )

    @property
    def persona(self) -> str:
        return f"Name: {self.name}\nRole: {self.role}\nAffiliation: {self.affiliation}\nDescription: {self.description}\n"


class Therapists(BaseModel):
    therapists: List[Therapist] = Field(
        description="Comprehensive list of therapists with their roles and affiliations.",
    )


class GenerateTherapistsState(TypedDict):
    patient_case: str  # Research topic
    human_analyst_feedback: str  # Human feedback
    therapists: List[Therapist]  # Analyst asking questions


class CaseAnalysisState(MessagesState):
    max_num_turns: int  # Number turns of conversation
    context: Annotated[list, operator.add]  # Source docs
    therapist: Therapist  # Analyst asking questions
    report: str  # Final analysis result
    sections: Annotated[list, operator.add]  # For Send() API compatibility with parent state


class TherapyPlanState(TypedDict):
    patient_id: str  # Patient identifier
    patient_case: str  # Research topic
    human_analyst_feedback: str  # Human feedback
    therapists: List[Therapist]  # Analyst asking questions
    sections: Annotated[list, operator.add]  # Send() API key
    introduction: str  # Introduction for the final report
    content: str  # Content for the final report
    conclusion: str  # Conclusion for the final report
    final_report: str  # Final report
    # Chat-related fields
    chat_message: str  # Incoming chat message from user
    chat_specialist_index: int  # Which specialist to chat with (0 = Sarah Cohen)
    chat_response: str  # Therapist response to user question
    chat_history: list  # Lead therapist (Sarah Cohen) chat history
    therapist_chat_history: dict  # Per-therapist chat history {therapist_index: [messages]}
    # Other fields
    parent_letter: str  # Generated letter to parents
    parent_letter_input: str  # User's input for parent letter generation

