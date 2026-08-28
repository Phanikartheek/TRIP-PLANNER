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
from typing import Any

import crewai
import litellm
from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from dotenv import load_dotenv

from trip_planner.schemas.models import CityGuide, CitySelection, TripItinerary
from trip_planner.tools import DuckDuckGoSearchTool, build_scrape_tool

load_dotenv()
litellm.drop_params = True

try:
    import crewai.llms.cache

    def _mark_cache_breakpoint(message: dict[str, Any]) -> dict[str, Any]:
        return message

    crewai.llms.cache.mark_cache_breakpoint = _mark_cache_breakpoint
except Exception:
    pass

_original_litellm_completion = litellm.completion

def _safe_litellm_completion(*args, **kwargs):
    if "messages" in kwargs and isinstance(kwargs["messages"], list):
        kwargs["messages"] = [
            {k: v for k, v in m.items() if k not in ("cache_breakpoint", "cache_control")}
            if isinstance(m, dict) else m
            for m in kwargs["messages"]
        ]
    return _original_litellm_completion(*args, **kwargs)

litellm.completion = _safe_litellm_completion

# Automatically retry when hitting provider rate limits (e.g. Groq free tier TPM)
_original_llm_call = LLM.call

def _parse_retry_after(err_msg: str) -> float | None:
    match = re.search(r"try again in (?:(\d+)m)?([\d\.]+)s", err_msg, re.IGNORECASE)
    if match:
        minutes = float(match.group(1)) if match.group(1) else 0.0
        seconds = float(match.group(2))
        return (minutes * 60.0) + seconds + 2.0
    return None


def _clean_messages(messages):
    if not isinstance(messages, list):
        return messages
    cleaned = []
    for msg in messages:
        if isinstance(msg, dict):
            c = {k: v for k, v in msg.items() if k not in ("cache_breakpoint", "cache_control")}
            cleaned.append(c)
        else:
            cleaned.append(msg)
    return cleaned


def _resilient_llm_call(self, *args, **kwargs):
    clean_args = [_clean_messages(a) for a in args]
    if "messages" in kwargs:
        kwargs["messages"] = _clean_messages(kwargs["messages"])

    max_retries = 8
    for attempt in range(max_retries):
        try:
            return _original_llm_call(self, *clean_args, **kwargs)
        except Exception as e:
            err_msg = str(e)
            if ("rate_limit" in err_msg.lower() or "429" in err_msg) and attempt < max_retries - 1:
                parsed_sleep = _parse_retry_after(err_msg)
                sleep_sec = parsed_sleep if parsed_sleep is not None else (15.0 + (attempt * 10))
                time.sleep(sleep_sec)
                continue
            if "tool choice is none" in err_msg.lower() and kwargs.get("tools"):
                kwargs_copy = dict(kwargs)
                kwargs_copy.pop("tools", None)
                kwargs_copy.pop("tool_choice", None)
                return _original_llm_call(self, *clean_args, **kwargs_copy)
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

    @agent
    def local_qa_expert(self) -> Agent:
        return Agent(
            config=self.agents_config["local_qa_expert"],
            tools=[self.search_tool, self.scrape_tool],
            llm=self.llm,
            max_iter=5,
        )

    @task
    def select_city_task(self) -> Task:
        return Task(
            config=self.tasks_config["select_city_task"],
            agent=self.city_selector(),
            output_pydantic=CitySelection,
        )

    @task
    def gather_city_info_task(self) -> Task:
        return Task(
            config=self.tasks_config["gather_city_info_task"],
            agent=self.local_expert(),
            output_pydantic=CityGuide,
        )

    @task
    def plan_itinerary_task(self) -> Task:
        return Task(
            config=self.tasks_config["plan_itinerary_task"],
            agent=self.travel_concierge(),
            output_pydantic=TripItinerary,
        )

    @task
    def revise_itinerary_task(self) -> Task:
        return Task(
            config=self.tasks_config["revise_itinerary_task"],
            agent=self.travel_concierge(),
            output_pydantic=TripItinerary,
        )

    @task
    def answer_destination_question_task(self) -> Task:
        return Task(
            config=self.tasks_config["answer_destination_question_task"],
            agent=self.local_qa_expert(),
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.city_selector(), self.local_expert(), self.travel_concierge()],
            tasks=[self.select_city_task(), self.gather_city_info_task(), self.plan_itinerary_task()],
            process=Process.sequential,
            verbose=True,
        )

    def revision_crew(self) -> Crew:
        """
        Specialized single-agent crew for conversational revisions.
        Skips city selection and local research agents to revise existing itineraries quickly.
        """
        agent_instance = self.travel_concierge()
        task_instance = Task(
            config=self.tasks_config["revise_itinerary_task"],
            agent=agent_instance,
            output_pydantic=TripItinerary,
        )
        return Crew(
            agents=[agent_instance],
            tasks=[task_instance],
            process=Process.sequential,
            verbose=True,
        )

    def qa_crew(self) -> Crew:
        """
        Specialized single-agent crew for answering direct destination questions.
        Outputs a direct text answer with real named establishments.
        """
        agent_instance = self.local_qa_expert()
        task_instance = Task(
            config=self.tasks_config["answer_destination_question_task"],
            agent=agent_instance,
        )
        return Crew(
            agents=[agent_instance],
            tasks=[task_instance],
            process=Process.sequential,
            verbose=True,
        )
