from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk.agents import Agent

from .tools import (
    get_best_usage_windows,
    get_carbon_intensity,
    get_carbon_intensity_forecast,
    get_monitoring_snapshot,
    get_recent_tool_traces,
    run_tool_self_test,
)

load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

root_agent = Agent(
    name="elec_wise_multi_tool_agent",
    model=MODEL,
    description="Helps users reduce electricity emissions with carbon-aware scheduling and operational telemetry.",
    instruction=(
        "You are ElecWise. Use tools to provide carbon intensity guidance. "
        "Always include current conditions, best overall window, daytime alternative when needed, and savings. "
        "If users ask about health, monitoring, testing, or traces, call monitoring and testing tools and summarize clearly."
    ),
    tools=[
        get_carbon_intensity,
        get_carbon_intensity_forecast,
        get_best_usage_windows,
        get_monitoring_snapshot,
        get_recent_tool_traces,
        run_tool_self_test,
    ],
)
