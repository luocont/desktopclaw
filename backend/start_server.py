import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        fast_model=config.agents.defaults.fast_model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        context_window_tokens=config.agents.defaults.context_window_tokens,
        search_config=config.tools.web.search,
        research_config=config.tools.web.research,
        web_proxy=config.tools.web.proxy or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
    )

    print("Starting services...")
    try:
        agent_task = asyncio.create_task(agent_loop.run())
        api_server = await start_api_server(agent_loop, bus, 3000)

        print("[green]✓[/green] API Server started on http://127.0.0.1:3000")
        print("[dim]Press Ctrl+C to stop[/dim]\n")

        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n[yellow]Shutting down...[/yellow]")
    finally:
        await api_server.stop()
        agent_loop.stop()
        await agent_task
        await agent_loop.close_mcp()
        print("[green]✓[/green] Server stopped")

if __name__ == "__main__":
    asyncio.run(main())
