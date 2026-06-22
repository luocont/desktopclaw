import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _monkey_patch_litellm():
    class MockModule:
        def __getattr__(self, name):
            if name == 'get_model_cost_map':
                def mock_get_model_cost_map(*args, **kwargs):
                    return {}
                return mock_get_model_cost_map
            raise AttributeError(name)
    
    sys.modules['litellm.litellm_core_utils.get_model_cost_map'] = MockModule()

_monkey_patch_litellm()

async def main():
    from loguru import logger
    from desktopclaw.agent.loop import AgentLoop
    from desktopclaw.api.server import start_api_server
    from desktopclaw.bus.queue import MessageBus
    from desktopclaw.config.paths import get_cron_dir
    from desktopclaw.cron.service import CronService
    from desktopclaw.config.loader import load_config
    from desktopclaw.utils.helpers import sync_workspace_templates

    print("Loading config...")
    config = load_config()
    sync_workspace_templates(config.workspace_path)

    print("Creating services...")
    bus = MessageBus()
    
    from desktopclaw.cli.commands import _make_provider
    provider = _make_provider(config)

    cron_store_path = get_cron_dir() / "jobs.json"
    cron = CronService(cron_store_path)

    logger.disable("nanobot")

    print("Creating agent loop...")
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        context_window_tokens=config.agents.defaults.context_window_tokens,
        brave_api_key=config.tools.web.search.api_key or None,
    )

    api_server = await start_api_server(
        agent_loop,
        bus,
        port=config.gateway.port,
    )

    print(f"API server started on http://127.0.0.1:{config.gateway.port}")
    await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
