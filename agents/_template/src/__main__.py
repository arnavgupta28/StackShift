import logging
import os

from dotenv import load_dotenv

# Telemetry must initialise before a2a-sdk / Starlette are imported, or spans
# never join the platform's session trace. See the nasiko openai template.
from telemetry import init_telemetry

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)
init_telemetry()

import click
import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from agents import set_tracing_disabled

from agent import StackShiftAgent
from agent_executor import ResearchAgentExecutor
from role import DESCRIPTION, EXAMPLES, SKILL_ID, SKILL_NAME, TAGS, TITLE

set_tracing_disabled(True)
logger = logging.getLogger(__name__)

CORS_ORIGINS = [
    "http://localhost:4000", "http://127.0.0.1:4000",
    "http://localhost:3000", "http://127.0.0.1:3000",
]


@click.command()
@click.option("--host", default="localhost")
@click.option("--port", default=8000)
def main(host, port):
    skill = AgentSkill(
        id=SKILL_ID, name=SKILL_NAME, description=DESCRIPTION,
        tags=TAGS, examples=EXAMPLES,
    )
    agent_url = os.getenv("HOST_OVERRIDE", f"http://{host}:{port}/")
    agent_card = AgentCard(
        name=TITLE,
        description=DESCRIPTION,
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", url=agent_url)],
        version="1.0.0",
        default_input_modes=StackShiftAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=StackShiftAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )
    handler = DefaultRequestHandler(
        agent_executor=ResearchAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = []
    routes.extend(create_agent_card_routes(agent_card))
    routes.extend(create_jsonrpc_routes(handler, rpc_url="/"))
    app = Starlette(routes=routes)
    app.add_middleware(
        CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
