"""
Crew definition: wires YAML agent/task configs to actual Agent/Task
objects, attaches tools and the LLM, and assembles the sequential crew.

Why @CrewBase: it's CrewAI's decorator-based pattern for YAML-configured
crews. It auto-loads config/agents.yaml and config/tasks.yaml into
`self.agents_config` / `self.tasks_config` dicts keyed by the top-level
YAML keys, so each @agent / @task method below just merges that config
with anything Python-only (tools, llm, output schema) that YAML can't
express.
"""

import os
import re
import time

import crewai.llms.cache
import litellm
from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from dotenv import load_dotenv

from trip_planner.schemas.models import CityGuide, CitySelection, TripItinerary
from trip_planner.tools import DuckDuckGoSearchTool, build_scrape_tool

load_dotenv()
litellm.drop_params = True
crewai.llms.cache.mark_cache_breakpoint = lambda m: m

# Automatically retry when hitting provider rate limits (e.g. Groq free tier TPM)
_original_llm_call = LLM.call

def _resilient_llm_call(self, *args, **kwargs):
    max_retries = 8
    for attempt in range(max_retries):
        try:
            return _original_llm_call(self, *args, **kwargs)
        except Exception as e:
            err_msg = str(e)
            if ("rate_limit" in err_msg.lower() or "429" in err_msg) and attempt < max_retries - 1:
                match = re.search(r"try again in ([\d\.]+)s", err_msg, re.IGNORECASE)
                if match:
                    sleep_sec = float(match.group(1)) + 1.5
                else:
                    sleep_sec = 15.0 + (attempt * 5)
                time.sleep(sleep_sec)
                continue
            if "tool choice is none" in err_msg.lower() and kwargs.get("tools"):
                kwargs_copy = dict(kwargs)
                kwargs_copy.pop("tools", None)
                kwargs_copy.pop("tool_choice", None)
                return _original_llm_call(self, *args, **kwargs_copy)
            raise

LLM.call = _resilient_llm_call


def _default_llm() -> LLM:
    """
    Single source of truth for model choice. Reading it here (rather than
    inline in every agent method) means changing providers later — e.g.
    swapping Groq for OpenAI for a higher-stakes demo — is a one-line
    change, not a find-and-replace across the file.
    """
    model = os.getenv("TRIP_PLANNER_MODEL", "groq/openai/gpt-oss-120b")
    return LLM(model=model, temperature=0.4)


@CrewBase
class TripPlannerCrew:
    """Sequential crew: city_selector -> local_expert -> travel_concierge."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self) -> None:
        self.llm = _default_llm()
        self.search_tool = DuckDuckGoSearchTool()
        self.scrape_tool = build_scrape_tool()

    @agent
    def city_selector(self) -> Agent:
        return Agent(
            config=self.agents_config["city_selector"],
            tools=[self.search_tool],
            llm=self.llm,
            max_iter=5,
        )

    @agent
    def local_expert(self) -> Agent:
        return Agent(
            config=self.agents_config["local_expert"],
            tools=[self.search_tool, self.scrape_tool],
            llm=self.llm,
            max_iter=5,
        )

    @agent
    def travel_concierge(self) -> Agent:
        return Agent(
            config=self.agents_config["travel_concierge"],
            tools=[self.search_tool],
            llm=self.llm,
            max_iter=5,
        )

    @task
    def select_city_task(self) -> Task:
        return Task(
            config=self.tasks_config["select_city_task"],
            output_pydantic=CitySelection,
        )

    @task
    def gather_city_info_task(self) -> Task:
        return Task(
            config=self.tasks_config["gather_city_info_task"],
            output_pydantic=CityGuide,
        )

    @task
    def plan_itinerary_task(self) -> Task:
        return Task(
            config=self.tasks_config["plan_itinerary_task"],
            output_pydantic=TripItinerary,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,  # populated by @agent-decorated methods, in definition order
            tasks=self.tasks,  # populated by @task-decorated methods, in definition order
            process=Process.sequential,
            verbose=True,
        )
