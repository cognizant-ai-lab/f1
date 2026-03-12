import argparse
import os
import time
from pathlib import Path
from typing import Any

from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor

TEST_INPUT = "ALERT WARNING FL surface temp 105°C — approaching limit 12:45 TEMP"


class TyresAgent:

    SESSION_TYPE: str = "direct"
    AGENT_NETWORK_NAME: str = "tyres_engineer"
    THINKING_DIR: str = "logs/agents"
    THINKING_FILE: str = "tyres_engineer"
    DEFAULT_INPUT: str = "DEFAULT"

    def __init__(self, session_context=None) -> None:
        factory: AgentSessionFactory = AgentSessionFactory()
        # Create log folders if they don't exist
        os.makedirs(self.THINKING_DIR, exist_ok=True)
        # Roll the existing log file so previous sessions are preserved
        self._roll_log()
        self.session: Any = factory.create_session(session_type=self.SESSION_TYPE,
                                                   agent_name=self.AGENT_NETWORK_NAME)
        # Append the current's session context to the agent's system prompt
        if session_context:
            original_instructions = self.session.agent_network.agent_spec_map[self.AGENT_NETWORK_NAME]["instructions"]
            self.session.agent_network.agent_spec_map[self.AGENT_NETWORK_NAME]["instructions"] =\
                original_instructions + "\n" + session_context
        # Initialize any conversation state here
        self.conversation_state: dict[str, Any] = {
            "last_chat_response": None,
            "prompt": "Analyze the alerts log\n",
            "timeout": 5000.0,
            "num_input": 0,
            "user_input": None,
            "sly_data": None,
            "chat_filter": {"chat_filter_type": "MAXIMAL"},
        }

    def _roll_log(self) -> None:
        """Rename the existing log file with a timestamp suffix."""
        log_path: Path = Path(self.THINKING_DIR) / self.THINKING_FILE
        if log_path.exists() and log_path.stat().st_size > 0:
            ts: str = time.strftime("%Y%m%d-%H%M%S")
            stem: str = log_path.stem
            rolled: Path = log_path.with_name(f"{stem}_{ts}{log_path.suffix}")
            log_path.rename(rolled)
            print(f"Rolled log to {rolled}")

    def process_messages(self, messages: list[str]) -> str | None:
        combined: str = "\n".join(messages)
        # Use the current session to process the input
        input_processor: StreamingInputProcessor = StreamingInputProcessor(
            self.DEFAULT_INPUT,
            self.THINKING_FILE,
            self.session,
            self.THINKING_DIR,
        )
        # Update the conversation state with this turn's input
        self.conversation_state["user_input"] = combined
        self.conversation_state = input_processor.process_once(self.conversation_state)
        # Get the agent response for this turn
        last_chat_response: str | None = self.conversation_state.get("last_chat_response")
        return last_chat_response

if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Tyres engineer agent")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for input interactively (uses timedinput); otherwise uses TEST_INPUT",
    )
    args: argparse.Namespace = parser.parse_args()

    # Set env variables
    os.environ["AGENT_MANIFEST_FILE"] = "registries/manifest.hocon"
    # Instantiate the agent
    agent: TyresAgent = TyresAgent()

    user_input: str
    if args.interactive:
        from timedinput import timedinput
        user_input = timedinput("Input message:\n",
                                timeout=60.0, # 1 minute
                                default="<===TIMEOUT===>")
    else:
        user_input = TEST_INPUT

    response: str | None = agent.process_messages([user_input])
    print(f"Response:\n {response}")
