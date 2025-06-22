
from typing import Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

import fetch_bills as fb

class State(TypedDict):
    messages: Annotated[list, add_messages]

def route_tools(state: State,):
    """
    Use in the conditional_edge to route to the appropriate tool node 
    if the last message has tool calls. Otherwise, route to the end.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0 and ai_message.tool_calls[0]["name"] == "fetch_congress_bills":
        return "fetch_congress_bills"
    elif hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0 and ai_message.tool_calls[0]["name"] == "search_bills_by_keyword":
        return "search_bills_by_keyword"
    elif hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0 and ai_message.tool_calls[0]["name"] == "get_bill_details":
        return "get_bill_details"
    elif hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0 and ai_message.tool_calls[0]["name"] == "get_bill_cosponsors":
        return "get_bill_cosponsors"
    elif hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0 and ai_message.tool_calls[0]["name"] == "get_bill_summaries":
        return "get_bill_summaries"
    
    return END

def graph_builder(thread_id: int):
    graph_builder = StateGraph(State)
        
    llm = ChatOpenAI(model_name="gpt-4o")
    agent = llm.bind_tools([fb.fetch_congress_bills, fb.search_bills_by_keyword, \
                            fb.get_bill_details, fb.get_bill_cosponsors, ])
    # fb.get_bill_summaries, fb.get_bills_by_sponsor, fb.get_bills_by_subject
    def chatbot(state: State):
        message = agent.invoke(state["messages"])
        return {"messages": [message]}

    # Creating ToolNodes
    fetch_congress_bills = ToolNode(tools=[fb.fetch_congress_bills])
    search_bills_by_keyword = ToolNode(tools=[fb.search_bills_by_keyword])
    get_bill_details = ToolNode(tools=[fb.get_bill_details])
    get_bill_cosponsors = ToolNode(tools=[fb.get_bill_cosponsors])
    get_bill_summaries = ToolNode(tools=[fb.get_bill_summaries])
    #get_bills_by_sponsor = ToolNode(tools=[fb.get_bills_by_sponsor])
    #get_bills_by_subject = ToolNode(tools=[fb.get_bills_by_subject])
    
    # Attaching tools to nodes
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("fetch_congress_bills", fetch_congress_bills)
    graph_builder.add_node("search_bills_by_keyword", search_bills_by_keyword)
    graph_builder.add_node("get_bill_details", get_bill_details)
    graph_builder.add_node("get_bill_cosponsors", get_bill_cosponsors)
    graph_builder.add_node("get_bill_summaries", get_bill_summaries)
    #graph_builder.add_node("get_bills_by_sponsor", get_bills_by_sponsor)
    #graph_builder.add_node("get_bills_by_subject", get_bills_by_subject)
    
    # Creating edges
    graph_builder.add_conditional_edges(
        "chatbot",
        route_tools,
    )
    graph_builder.add_edge("fetch_congress_bills", "chatbot")
    graph_builder.add_edge("search_bills_by_keyword", "chatbot")
    graph_builder.add_edge("get_bill_details", "chatbot")
    graph_builder.add_edge("get_bill_cosponsors", "chatbot")
    graph_builder.add_edge("get_bill_summaries", "chatbot")
    graph_builder.add_edge(START, "chatbot")
    
    # Creating memory and conversation id
    memory = MemorySaver()
    graph = graph_builder.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": f"{thread_id}"}}

    user_interaction(graph, config)

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

def get_system_message():
    return SystemMessage(content=f"You are a helpful assistant. \
                         You aid the user in finding information about US Congress bills. \
                         You can use the following tools to help the user: \
                         fetch_congress_bills, search_bills_by_keyword, \
                         get_bill_details, get_bill_cosponsors, get_bill_summaries. \
                         Try to get a lot of bills for more information. \
                         For each response, you should get the title, summary, \
                         you should explain how the bill affects the user's life based on their profile, \
                         and you should include a link to the bill. \
                         Explain the bill in a way that is easy to understand and not too technical. \
                         If the bill is not relevant to the user's profile, you should say so. \
                         If the bill is relevant to the user's profile, you should say so. \
                         Explain how the user's life will be impacted by each bill. \
                         The user's profile is {USER_PROFILE}")

def user_interaction(graph: StateGraph, config: dict):
    while True:
        user_input = input("User: ")
        if user_input == "":
            print("Goodbye!")
            break

        # Create a new system message with current time
        system_msg = get_system_message()

        # Stream the response with both system and user message
        for event in graph.stream({"messages": [system_msg,HumanMessage(content=user_input)]}, 
                                  config, stream_mode="values",):
            event["messages"][-1].pretty_print()


if __name__ == "__main__":
    graph_builder(1)