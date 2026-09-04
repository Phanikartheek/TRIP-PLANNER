"""
Crew definition: wires YAML agent/task configs to actual Agent/Task
objects, attaches tools and the LLM, and assembles the sequential crew.
"""

import os
import sys
import time
from typing import Any

import litellm
from dotenv import load_dotenv

load_dotenv()
litellm.drop_params = True

# MONKEYPATCH LITELLM BEFORE CREWAI IS IMPORTED
_original_litellm_completion = litellm.completion

def _shrink_messages_further(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shrunk = []
    for m in messages:
        if not isinstance(m, dict):
            shrunk.append(m)
            continue
        role = str(m.get("role", ""))
        content = str(m.get("content", ""))
        if role == "system" and len(content) > 400:
            content = content[:250] + "\n...[trimmed]...\n" + content[-150:]
        elif role == "tool" and len(content) > 100:
            content = content[:50] + "\n...[trimmed]...\n" + content[-50:]
        elif role == "user" and len(content) > 500:
            content = content[:300] + "\n...[trimmed]...\n" + content[-200:]
        elif role == "assistant" and len(content) > 800 and not ("\"days\":" in content or "total_estimated_cost" in content):
            content = content[:400] + "\n...[trimmed]...\n" + content[-400:]
        m_copy = dict(m)
        m_copy["content"] = content
        shrunk.append(m_copy)

    system_msgs = [m for m in shrunk if isinstance(m, dict) and m.get("role") == "system"]
    user_msgs = [m for m in shrunk if isinstance(m, dict) and m.get("role") == "user"]
    non_system = [m for m in shrunk if not (isinstance(m, dict) and m.get("role") == "system")]

    if user_msgs:
        recent_non_user = [m for m in non_system[-2:] if m != user_msgs[0]]
        return system_msgs[:1] + user_msgs[:1] + recent_non_user
    else:
        return system_msgs[:1] + [{"role": "user", "content": "Please proceed with the trip planning task."}] + non_system[-2:]

def _safe_litellm_completion(*args, **kwargs):
    args_list = list(args)
    if len(args_list) > 0 and isinstance(args_list[0], str) and "model" not in kwargs:
        kwargs["model"] = args_list.pop(0)
    if len(args_list) > 0 and isinstance(args_list[0], (list, tuple)) and "messages" not in kwargs:
        kwargs["messages"] = list(args_list.pop(0))
    args = tuple(args_list)

    print(f"[SAFE_LITELLM] Intercepted call with args={len(args)}, kwargs_keys={list(kwargs.keys())}", flush=True)
    for k, v in kwargs.items():
        print(f"[SAFE_LITELLM_DEBUG] key={k}, len={len(str(v))}", flush=True)

    if "tools" in kwargs and isinstance(kwargs["tools"], list):
        # Trim function descriptions
        for t in kwargs["tools"]:
            if isinstance(t, dict) and "function" in t and isinstance(t["function"], dict):
                desc = str(t["function"].get("description", ""))
                if len(desc) > 100:
                    t["function"]["description"] = desc[:100]
        # If total tool schema size > 2000 chars, remove redundant web search/scrape tools for non-search calls
        if len(str(kwargs["tools"])) > 2000:
            kwargs["tools"] = [
                t for t in kwargs["tools"]
                if isinstance(t, dict) and t.get("function", {}).get("name") not in ("web_search", "scrape_website", "read_website_content")
            ]
            if len(kwargs["tools"]) == 0:
                del kwargs["tools"]
                if "tool_choice" in kwargs:
                    del kwargs["tool_choice"]

    if "messages" in kwargs and isinstance(kwargs["messages"], list):
        clean_messages = []
        total_chars = 0
        for m in kwargs["messages"]:
            if isinstance(m, dict):
                m_dict = {k: v for k, v in m.items() if k not in ("cache_breakpoint", "cache_control")}
            elif hasattr(m, "role") or hasattr(m, "content"):
                role = str(getattr(m, "role", "user"))
                content = str(getattr(m, "content", ""))
                m_dict = {"role": role, "content": content}
                for attr in ("tool_call_id", "tool_calls", "name"):
                    if hasattr(m, attr) and getattr(m, attr) is not None:
                        m_dict[attr] = getattr(m, attr)
            else:
                clean_messages.append(m)
                continue

            role = str(m_dict.get("role", ""))
            content = str(m_dict.get("content", ""))

            if role == "system" and len(content) > 400:
                m_dict["content"] = content[:250] + "\n...[trimmed]...\n" + content[-150:]
            elif role != "system" and len(content) > 500 and not ("\"days\":" in content or "total_estimated_cost" in content):
                m_dict["content"] = content[:300] + "\n...[trimmed]...\n" + content[-200:]

            total_chars += len(str(m_dict.get("content", "")))
            clean_messages.append(m_dict)

        clean_messages = _shrink_messages_further(clean_messages)
        # Strict hard cap on total message content length to guarantee < 2,000 tokens for Groq TPM
        total_len = sum(len(str(m.get("content", ""))) for m in clean_messages if isinstance(m, dict))
        if total_len > 1200:
            for m in clean_messages:
                if isinstance(m, dict):
                    role = str(m.get("role", ""))
                    content = str(m.get("content", ""))
                    if role == "system" and len(content) > 300:
                        m["content"] = content[:200] + "\n...[trimmed]...\n" + content[-100:]
                    elif role != "system" and len(content) > 300 and not ("\"days\":" in content or "total_estimated_cost" in content):
                        m["content"] = content[:150] + "\n...[trimmed]...\n" + content[-150:]

        kwargs["messages"] = clean_messages

    # Enforce max_tokens = 6000 so LLM structured JSON output is complete while prompt_tokens (<1000) keeps total < 7000 TPM
    kwargs["max_tokens"] = 6000

    max_retries = 8
    tool_use_fail_count = 0
    for attempt in range(max_retries):
        try:
            res = _original_litellm_completion(*args, **kwargs)
            if hasattr(res, "choices") and res.choices:
                choice = res.choices[0]
                if hasattr(choice, "message") and choice.message:
                    msg = choice.message
                    if getattr(msg, "content", None) is None and not getattr(msg, "tool_calls", None):
                        msg.content = "Information successfully gathered."
            return res
        except Exception as e:
            err_msg = str(e)
            is_tool_fail = ("tool_use_failed" in err_msg or "Failed to call a function" in err_msg) and "max_tokens" not in err_msg
            is_rate_limit = "rate_limit" in err_msg.lower() or "429" in err_msg or "tokens per minute" in err_msg.lower() or "tpm" in err_msg.lower() or "too large" in err_msg.lower()
            is_parse_fail = "output_parse_failed" in err_msg.lower() or "parsing failed" in err_msg.lower()
            is_max_tokens = "max_tokens" in err_msg.lower() or "output is incomplete" in err_msg.lower()
            is_retryable = (is_tool_fail or is_rate_limit or is_parse_fail or is_max_tokens) and attempt < max_retries - 1

            if is_retryable:
                if is_tool_fail:
                    tool_use_fail_count += 1
                    # Remove tool_choice forcing so model can respond naturally
                    if "tool_choice" in kwargs:
                        del kwargs["tool_choice"]
                    # Inject a nudge message to use the search tool
                    if "messages" in kwargs and isinstance(kwargs["messages"], list):
                        kwargs["messages"].append({
                            "role": "user",
                            "content": "You MUST use the search tool to look up real information. Do NOT answer from your own knowledge. Call the search function now."
                        })
                    wait_time = 10
                    print(f"[SAFE_LITELLM] tool_use_failed (attempt {attempt+1}/{max_retries}, fail#{tool_use_fail_count}). Retrying in {wait_time}s with tool_choice removed...", flush=True)
                    # After 3 consecutive tool_use_failed, drop tools entirely so model can just respond with text
                    if tool_use_fail_count >= 3:
                        if "tools" in kwargs:
                            del kwargs["tools"]
                        if "tool_choice" in kwargs:
                            del kwargs["tool_choice"]
                        # Remove nudge messages we added
                        if "messages" in kwargs and isinstance(kwargs["messages"], list):
                            kwargs["messages"] = [m for m in kwargs["messages"] if not (isinstance(m, dict) and "MUST use the search tool" in str(m.get("content", "")))]
                        print(f"[SAFE_LITELLM] Dropped tools entirely after {tool_use_fail_count} tool_use_failed errors. Model will respond with text.", flush=True)
                elif is_max_tokens:
                    # Output was truncated. Increase max_tokens and shrink context
                    kwargs["max_tokens"] = 8192
                    wait_time = 3
                    print(f"[SAFE_LITELLM] max_tokens truncation (attempt {attempt+1}/{max_retries}). Increasing max_tokens to 8192, shrinking context and retrying in {wait_time}s...", flush=True)
                    if "messages" in kwargs and isinstance(kwargs["messages"], list):
                        kwargs["messages"] = _shrink_messages_further(kwargs["messages"])
                else:
                    tool_use_fail_count = 0  # reset on non-tool errors
                    err_str = str(e)
                    if "TPD" in err_str or "tokens per day" in err_str or "daily" in err_str:
                        kwargs["model"] = "groq/qwen/qwen3.6-27b"
                        print(f"[SAFE_LITELLM] TPD limit hit. Auto-fallback model switched to {kwargs.get('model')}", flush=True)
                        time.sleep(1.0)
                        try:
                            return _original_litellm_completion(*args, **kwargs)
                        except Exception as inner_e:
                            print(f"[SAFE_LITELLM] Fallback model call failed: {inner_e}", flush=True)
                    wait_time = 12
                    print(f"[SAFE_LITELLM] Rate limit or parse failure ({err_msg[:60]}...). Backing off for {wait_time}s (Attempt {attempt+1}/{max_retries})...", flush=True)
                    if "messages" in kwargs and isinstance(kwargs["messages"], list):
                        kwargs["messages"] = _shrink_messages_further(kwargs["messages"])
                time.sleep(wait_time)
            else:
                raise e

litellm.completion = _safe_litellm_completion
if hasattr(litellm, "main"):
    litellm.main.completion = _safe_litellm_completion

import crewai  # noqa: E402
from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from crewai.project import CrewBase, agent, crew, task  # noqa: E402

# Patch any module internal references in crewai
for mod_name, mod in list(sys.modules.items()):
    if mod_name.startswith("crewai") or mod_name.startswith("litellm"):
        if hasattr(mod, "completion"):
            setattr(mod, "completion", _safe_litellm_completion)

from trip_planner.schemas.models import (  # noqa: E402
    CityGuide,
    CitySelection,
    QAResponse,
    TripItinerary,
)
from trip_planner.tools import DuckDuckGoSearchTool, build_scrape_tool  # noqa: E402

try:
    import crewai.llms.cache

    def _mark_cache_breakpoint(message: dict[str, Any]) -> dict[str, Any]:
        return message

    crewai.llms.cache._mark_cache_breakpoint = _mark_cache_breakpoint
except Exception:
    pass


@CrewBase
class TripPlannerCrew:
    """TripPlanner crew: multi-agent AI trip planning team."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def _get_llm(self) -> LLM:
        raw_model = os.environ.get("TRIP_PLANNER_MODEL", "").strip()
        or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()

        # Hermes 3 aliases & resolution
        if raw_model.lower() in ("hermes", "hermes3", "hermes-3", "hermes-3-70b"):
            model = "openrouter/nousresearch/hermes-3-llama-3.1-70b"
        elif raw_model.lower() in ("hermes-3-405b", "hermes-405b"):
            model = "openrouter/nousresearch/hermes-3-llama-3.1-405b"
        elif raw_model:
            model = raw_model
        elif or_key and len(or_key) >= 10:
            # Auto-default to Hermes 3 when OpenRouter key is configured
            model = "openrouter/nousresearch/hermes-3-llama-3.1-70b"
        else:
            model = "groq/qwen/qwen3.6-27b"

        if model.startswith("openrouter/"):
            if not or_key or len(or_key) < 10:
                # If Hermes 3 was requested but OpenRouter key is missing, fallback gracefully to Groq
                if groq_key and len(groq_key) >= 5:
                    import logging
                    logging.getLogger("trip_planner.crew").warning(
                        "OPENROUTER_API_KEY not found for Hermes 3 (%s). Falling back gracefully to Groq (qwen3.6-27b).",
                        model
                    )
                    return LLM(model="groq/qwen/qwen3.6-27b", api_key=groq_key, temperature=0.2)
                raise ValueError(
                    "OPENROUTER_API_KEY is not set. "
                    "Please set OPENROUTER_API_KEY in your .env file to use Hermes 3."
                )
            return LLM(
                model=model,
                api_key=or_key,
                api_base="https://openrouter.ai/api/v1",
                temperature=0.2,
            )
        else:
            if not groq_key or len(groq_key) < 5:
                raise ValueError(
                    "GROQ_API_KEY environment variable is not set. "
                    "Please set GROQ_API_KEY in your .env file or environment."
                )
            return LLM(model=model, api_key=groq_key, temperature=0.2)


    @agent
    def city_selector(self) -> Agent:
        return Agent(
            config=self.agents_config["city_selector"],
            tools=[DuckDuckGoSearchTool()],
            llm=self._get_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def local_expert(self) -> Agent:
        return Agent(
            config=self.agents_config["local_expert"],
            tools=[DuckDuckGoSearchTool(), build_scrape_tool()],
            llm=self._get_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def travel_concierge(self) -> Agent:
        return Agent(
            config=self.agents_config["travel_concierge"],
            tools=[DuckDuckGoSearchTool()],
            llm=self._get_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def local_qa_expert(self) -> Agent:
        return Agent(
            config=self.agents_config["local_qa_expert"],
            tools=[DuckDuckGoSearchTool()],
            llm=self._get_llm(),
            verbose=True,
            max_iter=2,
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
        """Creates the TripPlanner crew"""
        return Crew(
            agents=[self.city_selector(), self.local_expert(), self.travel_concierge()],
            tasks=[self.select_city_task(), self.gather_city_info_task(), self.plan_itinerary_task()],
            process=Process.sequential,
            verbose=True,
        )

    def revision_crew(self) -> Crew:
        """Single-agent revision crew for itinerary adjustments."""
        concierge = self.travel_concierge()
        task = Task(
            description="Revise trip itinerary according to traveler feedback",
            expected_output="Updated day-by-day itinerary matching request",
            agent=concierge,
            output_pydantic=TripItinerary,
        )
        return Crew(agents=[concierge], tasks=[task], verbose=True)

    def qa_crew(self) -> Crew:
        """Single-agent Q&A crew for destination questions."""
        qa_agent = self.local_qa_expert()
        task = Task(
            description="Answer destination question accurately",
            expected_output="Clear Q&A response",
            agent=qa_agent,
            output_pydantic=QAResponse,
        )
        return Crew(agents=[qa_agent], tasks=[task], verbose=True)


def run_qa(destination_city: str, question: str, itinerary_summary: str = "") -> QAResponse:
    """Standalone QA function: asks local_qa_expert agent a follow-up question."""
    crew_instance = TripPlannerCrew()
    agent = crew_instance.local_qa_expert()
    task = Task(
        description=(
            f"Answer user question about {destination_city}: '{question}'. "
            f"Context itinerary summary: {itinerary_summary[:500]}."
        ),
        expected_output="Direct answer to user question as QAResponse structure",
        agent=agent,
        output_pydantic=QAResponse,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=True)
    res = crew.kickoff()
    if hasattr(res, "pydantic") and res.pydantic:
        return res.pydantic
    return QAResponse(answer=str(res.raw), sources=[])
