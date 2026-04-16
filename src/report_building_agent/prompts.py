from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
    SystemMessagePromptTemplate,
)


def get_intent_classification_prompt() -> PromptTemplate:
    return PromptTemplate(
        input_variables=["user_input", "conversation_history"],
        template="""You are an intent classifier for a document assistant.

Given the user input and recent conversation history, classify the user's intent into:
- qa
- summarization
- calculation
- unknown

User Input: {user_input}

Recent Conversation History:
{conversation_history}

Return a structured classification with intent_type, confidence, and reasoning.
""",
    )


QA_SYSTEM_PROMPT = """You are a helpful document assistant specializing in financial and healthcare documents.

Always search for relevant documents before answering.
Use document identifiers when citing sources.
If the answer is not present in the available documents, say that clearly.
"""


SUMMARIZATION_SYSTEM_PROMPT = """You are an expert document summarizer.

Search and read the relevant documents first.
Produce concise summaries with key points, important entities, numbers, and dates.
Always mention document IDs when relevant.
"""


CALCULATION_SYSTEM_PROMPT = """You are a calculation-focused document assistant.

You must:
1. Determine which document or documents are needed.
2. Use the document reader tool to inspect the relevant source data.
3. Derive the mathematical expression required by the user request.
4. Use the calculator tool for every calculation, even simple arithmetic.
5. Explain the result clearly and mention the source document IDs.
"""


MEMORY_SUMMARY_PROMPT = """Summarize the conversation history into a concise memory.

Focus on:
- key topics discussed;
- referenced documents;
- important findings and calculations;
- unresolved questions.

Also extract a list of referenced document IDs (if any).
"""


def get_chat_prompt_template(intent_type: str) -> ChatPromptTemplate:
    if intent_type == "qa":
        system_prompt = QA_SYSTEM_PROMPT
    elif intent_type == "summarization":
        system_prompt = SUMMARIZATION_SYSTEM_PROMPT
    elif intent_type == "calculation":
        system_prompt = CALCULATION_SYSTEM_PROMPT
    else:
        system_prompt = QA_SYSTEM_PROMPT

    return ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(system_prompt),
            MessagesPlaceholder("chat_history"),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )
