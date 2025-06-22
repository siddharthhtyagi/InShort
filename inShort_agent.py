from typing import Annotated, Any
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

import fetch_bills as fb

class State(TypedDict):
    messages: Annotated[list, add_messages]

def create_agent_graph():
    """
    Creates and returns a compiled LangGraph agent using the available tools.
    """
    graph_builder = StateGraph(State)

    llm = ChatOpenAI(model_name="gpt-4o")
    agent = llm.bind_tools([
        fb.fetch_congress_bills,
        fb.search_bills_by_keyword,
        fb.get_bill_details,
        fb.get_bill_cosponsors,
        fb.get_bill_summaries
    ])

    def chatbot(state: State):
        message = agent.invoke(state["messages"])
        return {"messages": [message]}

    def route_tools(state: State):
        if isinstance(state, list):
            ai_message = state[-1]
        elif messages := state.get("messages", []):
            ai_message = messages[-1]
        else:
            raise ValueError(f"No messages found in input state to tool_edge: {state}")

        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            tool_name = ai_message.tool_calls[0]["name"]
            if tool_name in [
                "fetch_congress_bills",
                "search_bills_by_keyword",
                "get_bill_details",
                "get_bill_cosponsors",
                "get_bill_summaries"
            ]:
                return tool_name
        return END

    # Create ToolNodes
    fetch_congress_bills_node = ToolNode(tools=[fb.fetch_congress_bills])
    search_bills_by_keyword_node = ToolNode(tools=[fb.search_bills_by_keyword])
    get_bill_details_node = ToolNode(tools=[fb.get_bill_details])
    get_bill_cosponsors_node = ToolNode(tools=[fb.get_bill_cosponsors])
    get_bill_summaries_node = ToolNode(tools=[fb.get_bill_summaries])

    # Add nodes to the graph
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("fetch_congress_bills", fetch_congress_bills_node)
    graph_builder.add_node("search_bills_by_keyword", search_bills_by_keyword_node)
    graph_builder.add_node("get_bill_details", get_bill_details_node)
    graph_builder.add_node("get_bill_cosponsors", get_bill_cosponsors_node)
    graph_builder.add_node("get_bill_summaries", get_bill_summaries_node)

    # Add edges
    graph_builder.add_conditional_edges("chatbot", route_tools)
    graph_builder.add_edge("fetch_congress_bills", "chatbot")
    graph_builder.add_edge("search_bills_by_keyword", "chatbot")
    graph_builder.add_edge("get_bill_details", "chatbot")
    graph_builder.add_edge("get_bill_cosponsors", "chatbot")
    graph_builder.add_edge("get_bill_summaries", "chatbot")
    graph_builder.add_edge(START, "chatbot")

    memory = MemorySaver()
    graph = graph_builder.compile(checkpointer=memory)
    return graph

def get_system_message(user_profile: dict[str, Any]):
    return SystemMessage(content=f"You are a helpful assistant. "
                         f"You aid the user in finding information about US Congress bills. "
                         f"You can use the following tools to help the user: "
                         f"fetch_congress_bills, search_bills_by_keyword, "
                         f"get_bill_details, get_bill_cosponsors, get_bill_summaries. "
                         f"Try to get a lot of bills for more information. "
                         f"For each response, you should get the title, summary, "
                         f"you should explain how the bill affects the user's life based on their profile, "
                         f"and you should include a link to the bill. "
                         f"Explain the bill in a way that is easy to understand and not too technical. "
                         f"If the bill is not relevant to the user's profile, you should say so. "
                         f"If the bill is relevant to the user's profile, you should say so. "
                         f"Explain how the user's life will be impacted by each bill. "
                         f"The user's profile is {user_profile}")

def run_agent(graph: StateGraph, config: dict, user_input: str, user_profile: dict[str, Any]):
    system_msg = get_system_message(user_profile)
    final_response = None
    for event in graph.stream({"messages": [system_msg, HumanMessage(content=user_input)]},
                              config, stream_mode="values"):
        message = event["messages"][-1]
        if isinstance(message, AIMessage) and not message.tool_calls:
            final_response = message.content
    return final_response

USER_PROFILE = {
    "name": "John Doe",
    "age": 30,
    "gender": "male",
    "location": "San Francisco, CA",
    "interests": ["technology", "politics", "finance", ],
    "political_affiliation": "Democrat",
    "political_views": "Liberal",
    "political_party": "Democratic Party",
    "political_ideology": "Liberal",
}

if __name__ == "__main__":
    graph = create_agent_graph()
    config = {"configurable": {"thread_id": "1"}}
    user_input = input("User: ")
    response = run_agent(graph, config, user_input, USER_PROFILE)
    print(f"Agent: {response}")