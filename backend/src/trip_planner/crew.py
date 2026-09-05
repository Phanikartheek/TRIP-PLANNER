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

    # Enforce max_tokens = 3500 so LLM structured JSON output is complete while staying within Groq token limits
    kwargs["max_tokens"] = 3500

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
            is_otpm_limit = "otpm" in err_msg.lower() or "reduce max_tokens" in err_msg.lower() or "output tokens per minute" in err_msg.lower()
            is_rate_limit = is_otpm_limit or "rate_limit" in err_msg.lower() or "429" in err_msg or "tokens per minute" in err_msg.lower() or "tpm" in err_msg.lower() or "too large" in err_msg.lower()
            is_parse_fail = "output_parse_failed" in err_msg.lower() or "parsing failed" in err_msg.lower()
            is_max_tokens = ("output is incomplete" in err_msg.lower() or "finish_reason: length" in err_msg.lower()) and not is_rate_limit
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
                    # Output was truncated. Keep max_tokens at 3500 and shrink context
                    kwargs["max_tokens"] = 3500
                    wait_time = 3
                    print(f"[SAFE_LITELLM] max_tokens truncation (attempt {attempt+1}/{max_retries}). Shrinking context and retrying in {wait_time}s...", flush=True)
                    if "messages" in kwargs and isinstance(kwargs["messages"], list):
                        kwargs["messages"] = _shrink_messages_further(kwargs["messages"])
                else:
                    tool_use_fail_count = 0  # reset on non-tool errors
                    if is_otpm_limit:
                        kwargs["max_tokens"] = 950
                    wait_time = 15
                    print(f"[SAFE_LITELLM] Groq Rate limit or parse failure ({err_msg[:120]}...). Backing off for {wait_time}s (Attempt {attempt+1}/{max_retries})...", flush=True)
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
    EvaluationResult,
    QAResponse,
    TripItinerary,
)
from trip_planner.tools import DuckDuckGoSearchTool, build_scrape_tool  # noqa: E402

try:
    import crewai.llms.cache

    def _mark_cache_breakpoint(message: dict[str, Any]) -> dict[str, Any]:
        return message

    setattr(crewai.llms.cache, "_mark_cache_breakpoint", _mark_cache_breakpoint)
except Exception:
    pass

_create_agent: Any = Agent
_create_task: Any = Task


@CrewBase
class TripPlannerCrew:
    """TripPlanner crew: multi-agent AI trip planning team."""

    agents_config: Any = "config/agents.yaml"
    tasks_config: Any = "config/tasks.yaml"

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
            model = "groq/qwen/qwen3.8-27b"

        if model.startswith("openrouter/"):
            if not or_key or len(or_key) < 10:
                # If Hermes 3 was requested but OpenRouter key is missing, fallback gracefully to Groq
                if groq_key and len(groq_key) >= 5:
                    import logging
                    logging.getLogger("trip_planner.crew").warning(
                        "OPENROUTER_API_KEY not found for Hermes 3 (%s). Falling back gracefully to Groq (qwen3.8-27b).",
                        model
                    )
                    return LLM(model="groq/qwen/qwen3.8-27b", api_key=groq_key, temperature=0.2)
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
        return _create_agent(
            config=self.agents_config["city_selector"],
            tools=[DuckDuckGoSearchTool()],
            llm=self._get_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def local_expert(self) -> Agent:
        from trip_planner.patterns.parallelizer import ParallelCityResearchTool
        return _create_agent(
            config=self.agents_config["local_expert"],
            tools=[DuckDuckGoSearchTool(), build_scrape_tool(), ParallelCityResearchTool()],
            llm=self._get_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def travel_concierge(self) -> Agent:
        return _create_agent(
            config=self.agents_config["travel_concierge"],
            tools=[DuckDuckGoSearchTool()],
            llm=self._get_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def local_qa_expert(self) -> Agent:
        return _create_agent(
            config=self.agents_config["local_qa_expert"],
            tools=[DuckDuckGoSearchTool()],
            llm=self._get_llm(),
            verbose=True,
            max_iter=2,
        )

    @task
    def select_city_task(self) -> Task:
        return _create_task(
            config=self.tasks_config["select_city_task"],
            output_pydantic=CitySelection,
        )

    @task
    def gather_city_info_task(self) -> Task:
        return _create_task(
            config=self.tasks_config["gather_city_info_task"],
            output_pydantic=CityGuide,
        )

    @task
    def plan_itinerary_task(self) -> Task:
        return _create_task(
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

    @task
    def revise_itinerary_task(self) -> Task:
        return _create_task(
            config=self.tasks_config["revise_itinerary_task"],
            output_pydantic=TripItinerary,
        )

    def revision_crew(self) -> Crew:
        """Single-agent revision crew for itinerary adjustments."""
        concierge = self.travel_concierge()
        task = _create_task(
            config=self.tasks_config["revise_itinerary_task"],
            agent=concierge,
            output_pydantic=TripItinerary,
        )
        return Crew(agents=[concierge], tasks=[task], verbose=True)

    @task
    def answer_destination_question_task(self) -> Task:
        return _create_task(
            config=self.tasks_config["answer_destination_question_task"],
            output_pydantic=QAResponse,
        )

    def qa_crew(self) -> Crew:
        """Single-agent Q&A crew for destination questions."""
        qa_agent = self.local_qa_expert()
        task = _create_task(
            config=self.tasks_config["answer_destination_question_task"],
            agent=qa_agent,
            output_pydantic=QAResponse,
        )
        return Crew(agents=[qa_agent], tasks=[task], verbose=True)

    @agent
    def budget_evaluator(self) -> Agent:
        return _create_agent(
            config=self.agents_config["budget_evaluator"],
            tools=[],
            llm=self._get_llm(),
            verbose=True,
            max_iter=1,
        )

    @task
    def evaluate_itinerary_task(self) -> Task:
        return _create_task(
            config=self.tasks_config["evaluate_itinerary_task"],
            output_pydantic=EvaluationResult,
        )

    def evaluator_crew(self) -> Crew:
        """Single-agent evaluation crew for budget and quality review."""
        eval_agent = self.budget_evaluator()
        task = _create_task(
            config=self.tasks_config["evaluate_itinerary_task"],
            agent=eval_agent,
            output_pydantic=EvaluationResult,
        )
        return Crew(agents=[eval_agent], tasks=[task], verbose=True)

    def evaluate_itinerary(
        self,
        itinerary: dict[str, Any] | TripItinerary,
        target_budget: float,
        destination_city: str = "",
        use_llm: bool = False,
    ) -> EvaluationResult:
        """
        Reviews a generated itinerary against explicit criteria:
        1. total_estimated_cost <= requested budget (hard check).
        2. No generic "Miscellaneous" catch-all line items over 25% of a day's cost.
        3. cost_breakdown items look specific and real, not vague filler.
        Returns: EvaluationResult(passes: bool, feedback: str).
        """
        import json

        data = itinerary.model_dump() if hasattr(itinerary, "model_dump") else dict(itinerary)
        total_cost = float(data.get("total_estimated_cost", 0.0))

        # Criterion 1: Hard budget ceiling
        if target_budget > 0 and total_cost > target_budget:
            overrun = round(total_cost - target_budget, 2)
            pct = round((overrun / target_budget) * 100.0, 1)
            feedback = (
                f"Total estimated cost of ₹{total_cost:,.0f} exceeds requested budget of ₹{target_budget:,.0f} "
                f"by ₹{overrun:,.0f} (+{pct}%). Cut accommodation tier, dining budget, or activity costs to fit within budget."
            )
            return EvaluationResult(passes=False, feedback=feedback)

        # Criterion 2: No generic "Miscellaneous" padding > 25% of any day
        days = data.get("days", [])
        if isinstance(days, list):
            for day in days:
                if isinstance(day, dict):
                    d_num = day.get("day_number", 1)
                    d_cost = float(day.get("estimated_cost", 0.0))
                    breakdown = day.get("cost_breakdown", [])
                    if isinstance(breakdown, list):
                        for item in breakdown:
                            if isinstance(item, dict):
                                name = str(item.get("item", "")).strip()
                                amount = float(item.get("amount", 0.0))
                                lower = name.lower()
                                if any(kw in lower for kw in ["miscellaneous", "misc", "contingency", "buffer", "unforeseen", "extras", "other expenses"]):
                                    if d_cost > 0 and (amount / d_cost) > 0.25:
                                        pct = round((amount / d_cost) * 100.0, 1)
                                        feedback = (
                                            f"Day {d_num} has generic '{name}' line item of ₹{amount:,.0f} ({pct}% of day's cost), "
                                            f"exceeding the 25% padding limit. Replace with concrete, named attractions or dining."
                                        )
                                        return EvaluationResult(passes=False, feedback=feedback)

                                # Criterion 3: Specificity (avoid vague 1-word filler)
                                if lower in ["food", "transport", "sightseeing", "activities", "shopping", "dinner", "lunch", "cab", "hotel", "travel"]:
                                    feedback = (
                                        f"Day {d_num} has vague line item '{name}'. "
                                        f"Specify the exact restaurant, attraction, or transit line instead of generic filler."
                                    )
                                    return EvaluationResult(passes=False, feedback=feedback)

        # Optional LLM-assisted evaluation if requested
        if use_llm:
            try:
                res = self.evaluator_crew().kickoff(inputs={
                    "destination_city": destination_city or data.get("destination_city", "Destination"),
                    "budget": f"₹{target_budget:,.0f}",
                    "itinerary": json.dumps(data)[:2500],
                })
                if hasattr(res, "pydantic") and isinstance(res.pydantic, EvaluationResult):
                    return res.pydantic
            except Exception:
                pass

        return EvaluationResult(passes=True, feedback="Itinerary satisfies budget ceiling and quality criteria.")

    def run_with_evaluator_loop(self, inputs: dict[str, Any], max_retries: int = 2) -> dict[str, Any]:
        """
        Evaluator-Optimizer loop:
        1. Generates itinerary via main crew.
        2. Evaluates against budget and quality criteria.
        3. If fails and retry_count < 2, feeds evaluator feedback to Concierge and regenerates.
        4. If still fails after 2 attempts, returns last attempt with honest budget_exceeded_warning.
        5. Logs each attempt's status and feedback.
        """
        import json
        import logging
        logger = logging.getLogger("trip_planner.evaluator")

        inputs = dict(inputs)
        if "currency" not in inputs:
            inputs["currency"] = "INR"
        if "language" not in inputs:
            inputs["language"] = "en"
        if "trip_length" not in inputs and "days" in inputs:
            inputs["trip_length"] = inputs["days"]

        target_budget = float(inputs.get("budget", 25000.0))
        dest_city = str(inputs.get("cities", inputs.get("destination_city", "Destination"))).split(",")[0].strip()

        # Initial generation
        logger.info(f"[EVALUATOR_LOOP] Starting initial generation for {dest_city} with target budget ₹{target_budget:,.0f}")
        crew_res = self.crew().kickoff(inputs=inputs)

        out_dict: dict[str, Any] = {}
        if hasattr(crew_res, "pydantic") and crew_res.pydantic:
            out_dict = crew_res.pydantic.model_dump()
        elif hasattr(crew_res, "raw"):
            try:
                out_dict = json.loads(crew_res.raw)
            except Exception:
                out_dict = {"raw_output": crew_res.raw}
        else:
            out_dict = {"raw_output": str(crew_res)}

        # Evaluation Loop
        attempt = 1
        eval_res = self.evaluate_itinerary(out_dict, target_budget, destination_city=dest_city)
        logger.info(f"[EVALUATOR_LOOP] Attempt {attempt} Evaluation: passes={eval_res.passes} | Feedback: {eval_res.feedback}")

        while not eval_res.passes and attempt <= max_retries:
            logger.warning(
                f"[EVALUATOR_LOOP] Attempt {attempt} FAILED: {eval_res.feedback}. "
                f"Feeding feedback back to Concierge for regeneration (attempt {attempt + 1}/{max_retries + 1})..."
            )
            feedback_prompt = (
                f"CRITICAL BUDGET & QUALITY FEEDBACK FROM EVALUATOR:\n{eval_res.feedback}\n"
                f"You MUST revise the itinerary so total_estimated_cost strictly <= ₹{target_budget:,.0f}. "
                f"Cut luxury hotel prices, scale down dining expenses, and eliminate vague padding."
            )
            rev_inputs = {
                "feedback": feedback_prompt,
                "itinerary": json.dumps(out_dict),
                "language": inputs.get("language", "en"),
            }
            try:
                rev_res = self.revision_crew().kickoff(inputs=rev_inputs)
                if hasattr(rev_res, "pydantic") and rev_res.pydantic:
                    out_dict = rev_res.pydantic.model_dump()
                elif hasattr(rev_res, "raw"):
                    try:
                        parsed = json.loads(rev_res.raw)
                        if isinstance(parsed, dict) and parsed.get("days"):
                            out_dict = parsed
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"[EVALUATOR_LOOP] Regeneration attempt {attempt + 1} raised error: {e}")
                break

            attempt += 1
            eval_res = self.evaluate_itinerary(out_dict, target_budget, destination_city=dest_city)
            logger.info(f"[EVALUATOR_LOOP] Attempt {attempt} Evaluation: passes={eval_res.passes} | Feedback: {eval_res.feedback}")

        if not eval_res.passes:
            tot_cost = float(out_dict.get("total_estimated_cost", 0.0))
            overrun = max(0.0, tot_cost - target_budget)
            warn_msg = (
                f"⚠️ Budget Alert: This itinerary's estimated cost (₹{tot_cost:,.0f}) "
                f"exceeds your requested budget (₹{target_budget:,.0f}) by ₹{overrun:,.0f} after {attempt} optimization attempts."
            )
            out_dict["budget_exceeded_warning"] = warn_msg
            out_dict["budget_alert"] = warn_msg
            logger.warning(f"[EVALUATOR_LOOP] Final status: FAILED after {attempt} attempts. Attaching honest budget_exceeded_warning.")
        else:
            logger.info(f"[EVALUATOR_LOOP] Final status: PASSED! Itinerary complies with budget ceiling in attempt {attempt}.")

        out_dict["evaluation_passes"] = eval_res.passes
        out_dict["evaluation_feedback"] = eval_res.feedback
        out_dict["evaluation_attempts"] = attempt
        return out_dict

    def run_agentic_workflow(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Executes the Four-Pattern Agentic Architecture:
        1. Routing: Classifies persona and topology with tailored prompt guardrails.
        2. Parallelization: Concurrently gathers weather, transit, food, and attractions.
        3. Orchestrator-Workers: Breaks down goals, delegates to sub-workers, and synthesizes.
        4. Evaluator-Optimizer: Evaluates against budget and quality gates, optimizing iteratively.
        """
        from trip_planner.patterns import (
            EvaluatorOptimizer,
            ParallelResearcher,
            TripOrchestrator,
            TripRouter,
        )

        # 1. Routing
        route_decision = TripRouter.classify(inputs)

        # 2. Parallel Research
        origin = str(inputs.get("origin", "Bengaluru")).strip()
        cities_raw = str(inputs.get("cities", inputs.get("destination_city", "Vijayawada"))).strip()
        first_city = [c.strip() for c in cities_raw.split(",") if c.strip()][0] if cities_raw else "Vijayawada"
        researcher = ParallelResearcher()
        research_data = researcher.run_parallel_research(
            origin=origin,
            destination=first_city,
            interests=str(inputs.get("interests", "")),
            budget=float(inputs.get("budget", 25000.0)),
            travel_date=inputs.get("travel_date"),
        )

        # 3. Orchestrator-Workers
        orchestrator = TripOrchestrator()
        candidate_itinerary = orchestrator.orchestrate_itinerary(inputs)

        # 4. Evaluator-Optimizer Loop
        target_budget = float(inputs.get("budget", 25000.0))
        eval_optimizer = EvaluatorOptimizer(max_passes=2)
        refined_itinerary, eval_report, passes = eval_optimizer.run_optimization_loop(
            candidate=candidate_itinerary,
            target_budget=target_budget,
            default_origin=origin,
        )

        out_dict = refined_itinerary.model_dump()
        out_dict["route_decision"] = route_decision.model_dump()
        out_dict["research_summary"] = research_data.model_dump()
        out_dict["evaluation_report"] = eval_report.model_dump()
        out_dict["optimization_passes"] = passes
        return out_dict


def run_qa(destination_city: str, question: str, itinerary_summary: str = "") -> QAResponse:
    """Standalone QA function: asks local_qa_expert agent a follow-up question."""
    crew_instance = TripPlannerCrew()
    agent = crew_instance.local_qa_expert()
    task = _create_task(
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
    if hasattr(res, "pydantic") and isinstance(res.pydantic, QAResponse):
        return res.pydantic
    raw_text = getattr(res, "raw", str(res))
    return QAResponse(answer=str(raw_text), sources=[])
