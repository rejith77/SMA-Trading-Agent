import os
from dotenv import load_dotenv
from typing import TypedDict, List
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

import tools

# --- Setup ---
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found. Please add it to .env")

# --- State Definition ---
class AgentState(TypedDict):
    goal: str
    past_steps: List[str]
    action_command: str
    result: str

# --- Executor Node ---
def executor_node(state: AgentState) -> dict:
    print("\n--- EXECUTOR ---")
    past_steps = "\n".join(state["past_steps"])

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    prompt = f"""
You are a financial trading agent.
Your goal: {state['goal']}

Past Steps:
{past_steps}

Available Commands:
1. FETCH "TICKER"
2. INDICATOR "TICKER" "INDICATOR_NAME"
3. BACKTEST "TICKER" "STRATEGY_NAME"
4. FINISH "final answer"

Choose the next best command. Only output the command, no explanation.
"""
    response = llm.invoke(prompt)
    return {"action_command": response.content.strip()}

def tool_node(state: AgentState) -> dict:
    print("\n--- TOOLS ---")
    command = state["action_command"]
    result = tools.execute_command(command)

    if command.startswith("BACKTEST"):
        return {
            "past_steps": state["past_steps"] + [f"Action: {command}\nResult: {result}"],
            "action_command": f'FINISH "{result}"',
            "result": result
        }

    return {
        "past_steps": state["past_steps"] + [f"Action: {command}\nResult: {result}"],
        "result": result
    }

# Conditional Edge
def should_continue(state: AgentState) -> str:
    if state["action_command"].startswith("FINISH"):
        return "end"
    return "continue"

# Graph Definition 
workflow = StateGraph(AgentState)
workflow.add_node("executor", executor_node)
workflow.add_node("tools", tool_node)

workflow.set_entry_point("executor")
workflow.add_edge("executor", "tools")
workflow.add_conditional_edges("tools", should_continue, {"continue": "executor", "end": END})

app = workflow.compile()

if __name__ == "__main__":
    GOAL = "Fetch TSLA, calculate SMA, then backtest SMA strategy"
    inputs = {"goal": GOAL, "past_steps": [], "result": ""}
    
    for event in app.stream(inputs):
        for k, v in event.items():
            if k != "__end__":
                print(f"\n--- Event: {k} ---\n{v}")
