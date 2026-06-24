"""Generate DesktopClaw software engineering lab report with full content."""

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

OUTPUT = r"e:\workspace\Desktopclaw\desktopclaw\软件工程实验报告-DesktopClaw.docx"

TOC_ENTRIES = [
    ("1. 绪论", "3", 0),
    ("1.1 目标软件系统开发的目的和意义", "3", 1),
    ("1.2 开发工具及相关技术介绍", "3", 1),
    ("2. 可行性分析", "4", 0),
    ("2.1 技术可行性", "4", 1),
    ("2.2 经济可行性", "4", 1),
    ("2.3 操作可行性", "4", 1),
    ("3. 需求分析", "5", 0),
    ("3.1 功能需求", "5", 1),
    ("3.2 性能需求", "5", 1),
    ("3.3 软件开发约束需求", "6", 1),
    ("3.4 软件质量要求", "6", 1),
    ("4. 体系结构设计", "7", 0),
    ("4.1 软件设计目标和原则", "7", 1),
    ("4.2 逻辑视点的体系结构设计", "7", 1),
    ("4.3 部署视点的体系结构设计", "8", 1),
    ("4.4 开发视点的体系结构设计", "8", 1),
    ("4.5 运行视点的体系结构设计", "9", 1),
    ("5. 软件详细设计", "10", 0),
    ("5.1 用户界面设计", "10", 1),
    ("5.2 用例设计", "10", 1),
    ("5.3 类设计", "11", 1),
    ("5.4 数据设计", "12", 1),
    ("6. 编码实现", "13", 0),
    ("6.1 相关技术介绍", "13", 1),
    ("6.2 模块说明", "13", 1),
    ("7. 软件测试", "15", 0),
    ("7.1 单元测试", "15", 1),
    ("7.2 集成测试", "15", 1),
    ("7.3 确认测试", "16", 1),
    ("7.4 缺陷汇总", "16", 1),
    ("8. 总结", "17", 0),
    ("9. 附录", "17", 0),
]


def set_run_font(run, name="宋体", size=12, bold=False):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.bold = bold


def add_center_title(doc, text, size=16):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_run_font(run, size=size, bold=True)
    p.paragraph_format.space_after = Pt(18)
    return p


def add_heading(doc, text, level=1):
    sizes = {1: 14, 2: 12}
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, size=sizes.get(level, 12), bold=True)
    p.paragraph_format.space_before = Pt(12 if level == 1 else 6)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.5
    return p


def add_body(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run)
    p.paragraph_format.first_line_indent = Cm(0.74)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(0)
    return p


def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(item)
        set_run_font(run)
        p.paragraph_format.line_spacing = 1.5


def add_toc_line(doc, title, page, indent_level=0):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.left_indent = Cm(0.74 * indent_level)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.5
    tab_pos = Cm(15.5)
    paragraph.paragraph_format.tab_stops.add_tab_stop(
        tab_pos, WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS
    )
    run = paragraph.add_run(f"{title}\t{page}")
    set_run_font(run)


def setup_page(doc):
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.17)
    section.right_margin = Cm(3.17)


def add_cover_and_toc(doc):
    add_center_title(doc, "DesktopClaw 桌面 AI 智能助手系统", size=18)
    add_center_title(doc, "设计与实现", size=16)
    doc.add_page_break()

    add_center_title(doc, "目  录", size=16)
    for title_text, page, level in TOC_ENTRIES:
        add_toc_line(doc, title_text, page, level)
    doc.add_page_break()


def add_chapter1(doc):
    add_heading(doc, "1. 绪论")
    add_heading(doc, "1.1 目标软件系统开发的目的和意义", level=2)
    add_body(
        doc,
        "随着大语言模型（LLM）技术的快速发展，个人用户对本地化、可定制、可扩展的 AI 助手需求日益增长。"
        "传统在线聊天机器人难以满足桌面常驻、多渠道接入、工具调用与长期记忆等复合场景。"
        "DesktopClaw 是一款面向个人用户的轻量级桌面 AI 智能助手框架，旨在将 LLM 能力以桌面宠物形态呈现，"
        "同时提供完整的 Agent 引擎、会话管理、记忆系统与多消息渠道集成能力。",
    )
    add_body(
        doc,
        "本系统的开发目的包括：（1）提供基于 Electron + Vue 3 的桌面交互界面，支持 Live2D 虚拟形象与独立聊天窗口；"
        "（2）构建 Python 异步后端，实现流式对话、工具调用、子代理调度与深度网络研究；"
        "（3）实现双域记忆体系，持久化用户事实与 Agent 推理策略；（4）支持 Telegram、飞书、钉钉、"
        "WhatsApp 等十余种消息渠道的统一接入。该系统对软件工程实践具有典型意义，涵盖前后端分离、"
        "事件驱动架构、插件化工具与可测试性设计等核心主题。",
    )

    add_heading(doc, "1.2 开发工具及相关技术介绍", level=2)
    add_body(doc, "本项目采用前后端分离的全栈架构，主要开发工具与技术如下：")
    add_bullets(
        doc,
        [
            "后端语言与框架：Python 3.11+，asyncio 原生 HTTP 服务，Pydantic 配置校验，LiteLLM 统一多模型调用；",
            "前端技术栈：Vue 3、Vite、Electron 28、PIXI.js + Live2D Display 实现桌面宠物渲染；",
            "通信协议：HTTP/1.1 REST API、Server-Sent Events（SSE）流式推送、Electron IPC、WebSocket（Bridge 层）；",
            "AI 能力：Agent 循环（AgentLoop）、工具注册表（ToolRegistry）、MCP 协议、Skills 技能系统；",
            "记忆与检索：sentence-transformers 本地嵌入、SQLite 图存储、Reasoning Bank 策略库；",
            "测试与工程化：pytest + pytest-asyncio（48 个测试文件）、Ruff 代码检查、electron-builder 打包。",
        ],
    )


def add_chapter2(doc):
    add_heading(doc, "2. 可行性分析")
    add_heading(doc, "2.1 技术可行性", level=2)
    add_body(
        doc,
        "项目技术选型成熟可靠。Python 生态在 AI Agent 领域已有丰富实践（LiteLLM、MCP、Playwright 等），"
        "Vue 3 + Electron 是桌面应用主流方案。后端 AgentLoop 采用 asyncio 消息总线解耦渠道与处理引擎，"
        "APIServer 已实现 /chat、/chat/stream、/sessions、/memory、/settings 等核心接口，技术路径清晰可行。",
    )
    add_heading(doc, "2.2 经济可行性", level=2)
    add_body(
        doc,
        "系统基于 MIT 开源协议，核心依赖均为开源组件。LLM 调用按用量计费，用户可自选 OpenAI、Anthropic、"
        "Azure 等提供商；本地嵌入模型可选安装，降低长期 API 成本。部署仅需本机运行 Python 后端与 Electron 前端，"
        "无需专用服务器，开发与运维成本可控。",
    )
    add_heading(doc, "2.3 操作可行性", level=2)
    add_body(
        doc,
        "用户通过 desktopclaw gateway 命令启动后端，npm run electron:dev 启动前端，操作流程简单。"
        "设置界面支持 Provider、模型、人格（SOUL）等可视化配置；聊天界面支持多会话侧边栏、流式输出、"
        "Markdown 渲染与语音录制。对于进阶用户，CLI 提供 onboard、cron 等命令行管理能力，学习曲线平缓。",
    )


def add_chapter3(doc):
    add_heading(doc, "3. 需求分析")
    add_heading(doc, "3.1 功能需求", level=2)
    add_body(doc, "根据项目实现，系统功能需求归纳如下：")
    add_bullets(
        doc,
        [
            "桌面宠物模式：Live2D 形象展示、窗口拖拽缩放、鼠标穿透、控制按钮（设置/模型选择/打开聊天）；",
            "聊天对话：支持标准 POST /chat 与 SSE 流式 /chat/stream，多轮上下文、工具调用结果展示；",
            "会话管理：会话列表 CRUD、历史消息加载（/sessions、/sessions/{id}/messages）；",
            "记忆管理：用户事实（MEMORY.md、HISTORY.md）与 Agent 策略（reasoning_bank.json、graph.db）双域存储与 API 查询；",
            "设置配置：LLM Provider、API Key、模型选择、人格模板，前后端双写持久化；",
            "工具能力：文件读写、Shell 执行、深度网络研究（deep_web_search）、定时任务（Cron）、子代理（Spawn）；",
            "多渠道接入：Telegram、飞书、钉钉、Discord、Slack、QQ、微信、Email、Matrix、WhatsApp 等；",
            "媒体处理：音频上传（/audio/upload）、媒体文件访问（/media/）。",
        ],
    )

    add_heading(doc, "3.2 性能需求", level=2)
    add_bullets(
        doc,
        [
            "流式响应：SSE 首 token 延迟应低于 3 秒（取决于 LLM 提供商）；",
            "上下文窗口：默认支持 65536 tokens，超长会话触发记忆归档与摘要；",
            "并发处理：asyncio 异步 I/O，消息总线队列化处理入站消息；",
            "深度研究：deep_web_search 全流程超时默认 120 秒，可配置 maxPages、fetchConcurrency；",
            "记忆检索：向量检索 + 图遍历混合策略，索引任务由 MemoryIndexWorker 异步执行。",
        ],
    )

    add_heading(doc, "3.3 软件开发约束需求", level=2)
    add_bullets(
        doc,
        [
            "运行环境：Windows 10+，Python ≥ 3.11，Node.js 用于前端构建与 Bridge 服务；",
            "本地绑定：API 服务默认监听 127.0.0.1:3000，避免公网暴露；",
            "安全约束：Shell 工具受 ExecToolConfig 限制，文件操作可配置 restrict_to_workspace；",
            "配置管理：Pydantic Schema 统一校验，支持 camelCase/snake_case 别名；",
            "依赖可选：memory、web-search、wecom 等通过 extras 按需安装。",
        ],
    )

    add_heading(doc, "3.4 软件质量要求", level=2)
    add_bullets(
        doc,
        [
            "可维护性：模块化目录（agent/、api/、channels/、bus/、providers/），各渠道继承 BaseChannel；",
            "可测试性：pytest 覆盖 Agent、记忆、渠道、API、工具等 48 个测试模块；",
            "可扩展性：ToolRegistry 插件注册、Skills 目录热加载、MCP Server 动态接入；",
            "安全性：前端 DOMPurify 防 XSS、路径穿越防护、渠道 allow_from 白名单；",
            "可用性：健康检查 /health、错误信息中英文友好提示、Usage 令牌用量追踪。",
        ],
    )


def add_chapter4(doc):
    add_heading(doc, "4. 体系结构设计")
    add_heading(doc, "4.1 软件设计目标和原则", level=2)
    add_body(
        doc,
        "设计目标：构建高内聚、低耦合的桌面 AI 助手平台，使前端交互、消息路由、Agent 推理、工具执行各层可独立演进。"
        "设计原则包括：单一职责（渠道适配与 Agent 逻辑分离）、依赖倒置（BaseChannel/LLMProvider 抽象）、"
        "事件驱动（MessageBus 解耦生产消费）、配置驱动（Pydantic Schema 集中管理）。",
    )

    add_heading(doc, "4.2 逻辑视点的体系结构设计", level=2)
    add_body(doc, "系统逻辑分层如下：")
    add_bullets(
        doc,
        [
            "表示层：App.vue（桌面宠物）、ChatApp.vue（聊天主界面）、SettingsPage/MemoryPage；",
            "通信层：Electron preload IPC、axios/fetch API 客户端、SSE 流解析；",
            "应用层：APIServer 路由分发、SessionManager 会话管理、ChannelManager 渠道路由；",
            "领域层：AgentLoop 核心引擎、ContextBuilder 上下文构建、MemoryConsolidator 记忆整合；",
            "基础设施层：LLMProvider（LiteLLM）、ToolRegistry、MessageBus、本地文件存储。",
        ],
    )
    add_body(
        doc,
        "核心数据流：用户消息 → APIServer/InboundMessage → MessageBus → AgentLoop → "
        "LLM + Tools → OutboundMessage/SSE → 前端渲染。",
    )

    add_heading(doc, "4.3 部署视点的体系结构设计", level=2)
    add_body(doc, "典型部署拓扑（单机桌面）：")
    add_bullets(
        doc,
        [
            "进程 1：Python Gateway（desktopclaw gateway --port 3000），含 AgentLoop + APIServer；",
            "进程 2：Electron 主进程 + 渲染进程（Vue 应用）；",
            "进程 3（可选）：Node.js Bridge WebSocket 服务，用于 WhatsApp 等第三方协议桥接；",
            "存储：用户目录下 workspace/（配置、会话、memory/、skills/、媒体文件）。",
        ],
    )

    add_heading(doc, "4.4 开发视点的体系结构设计", level=2)
    add_body(doc, "代码仓库模块划分：")
    add_bullets(
        doc,
        [
            "backend/desktopclaw/agent/：Agent 引擎、工具、记忆、子代理；",
            "backend/desktopclaw/api/：HTTP 服务、session_helpers、memory_helpers；",
            "backend/desktopclaw/channels/：各渠道适配器与 ChannelManager；",
            "backend/desktopclaw/bus/：InboundMessage/OutboundMessage 与 MessageBus；",
            "backend/desktopclaw/providers/：LLM 提供商抽象与重试策略；",
            "frontend/src/：Vue 组件、stores（useChat/useConversations/useLive2D）、api/ 客户端；",
            "backend/tests/：单元与集成测试。",
        ],
    )

    add_heading(doc, "4.5 运行视点的体系结构设计", level=2)
    add_body(
        doc,
        "运行时，AgentLoop 在独立 asyncio 任务中监听 MessageBus；APIServer 通过 asyncio Stream 处理 HTTP 连接；"
        "各 Channel 以后台任务方式连接外部平台（WebSocket/长轮询）。记忆系统在会话间隙触发 TriggerState 检索，"
        "MemoryIndexWorker 异步更新向量索引。CronService 与 HeartbeatService 提供定时与保活能力。",
    )


def add_chapter5(doc):
    add_heading(doc, "5. 软件详细设计")
    add_heading(doc, "5.1 用户界面设计", level=2)
    add_body(doc, "系统提供两套 UI 模式：")
    add_bullets(
        doc,
        [
            "桌面宠物模式（App.vue）：Live2DStage 渲染虚拟形象，ControlButtons 提供设置/模型/聊天入口，"
            "支持拖拽移动窗口、缩放宠物、鼠标穿透切换；",
            "聊天应用模式（ChatApp.vue）：ChatLayout 包含 ChatSidebar（会话列表）与 ChatMain（消息区 + ChatComposer），"
            "SettingsPage 管理 Provider 配置，MemoryPage 展示记忆条目；",
            "消息展示：MessageBubble 支持 Markdown（marked + DOMPurify）、工具调用折叠、思考过程、TTS 播放。",
        ],
    )

    add_heading(doc, "5.2 用例设计", level=2)
    add_body(doc, "主要用例包括：")
    add_bullets(
        doc,
        [
            "UC-01 发起对话：用户在 ChatComposer 输入消息 → useChat.send() → POST /chat/stream → 流式显示回复；",
            "UC-02 管理会话：侧边栏新建/切换/删除会话，调用 /sessions API 持久化；",
            "UC-03 配置模型：ModelPicker 选择 Provider 与模型，写入 /settings；",
            "UC-04 查看记忆：MemoryPage 调用 /memory 获取用户事实与策略记忆；",
            "UC-05 渠道消息：外部用户通过 Telegram/飞书发消息 → Channel → Bus → AgentLoop → 回复至渠道；",
            "UC-06 深度研究：Agent 调用 deep_web_search 工具，多轮 Bing 检索 + 页面深读 + 交叉验证后返回报告。",
        ],
    )

    add_heading(doc, "5.3 类设计", level=2)
    add_body(doc, "核心类及职责：")
    add_bullets(
        doc,
        [
            "AgentLoop：核心处理引擎，协调 ContextBuilder、ToolRegistry、MemoryConsolidator、SubagentManager；",
            "APIServer：HTTP 路由处理，管理 SSE 流、CORS、Feishu 事件推送；",
            "BaseChannel（抽象类）：connect/disconnect/send 接口，子类实现 TelegramChannel、FeishuChannel 等；",
            "ChannelManager：渠道生命周期管理与入站消息路由至 MessageBus；",
            "MessageBus：asyncio.Queue 实现的生产者-消费者消息总线；",
            "SessionManager / Session：会话元数据与消息历史持久化；",
            "MemoryStore / ReasoningBankStore / MemoryGraphStore：三存储后端支撑双域记忆；",
            "MRAgentRetriever：混合检索器，结合向量相似度与图关系扩展；",
            "LLMProvider：封装 LiteLLM 调用、流式输出、重试与 usage 统计。",
        ],
    )

    add_heading(doc, "5.4 数据设计", level=2)
    add_body(doc, "主要数据实体与存储：")
    add_bullets(
        doc,
        [
            "会话数据：sessions.json 存储会话列表（id、title、created_at），各会话消息存于独立 JSON 文件；",
            "配置数据：config.json（Pydantic DesktopclawConfig），含 providers、channels、tools、memory 等节；",
            "用户事实：memory/MEMORY.md（长期事实）、memory/HISTORY.md（事件日志，仅追加）；",
            "Agent 策略：memory/reasoning_bank.json（ReasoningUnit 列表）、memory/graph.db（SQLite 知识图谱）；",
            "向量索引：嵌入向量由 LocalEmbedder 生成，MemoryIndexWorker 异步维护；",
            "媒体文件：get_media_dir() 目录存储上传音频与渠道附件；",
            "Skills：skills/{name}/SKILL.md 定义 Agent 可加载的技能指令。",
        ],
    )


def add_chapter6(doc):
    add_heading(doc, "6. 编码实现")
    add_heading(doc, "6.1 相关技术介绍", level=2)
    add_bullets(
        doc,
        [
            "LiteLLM：统一 OpenAI/Anthropic/Azure 等多厂商 API，支持流式 completion 与 tool_calls；",
            "asyncio Stream Server：APIServer 基于 asyncio.start_server 实现轻量 HTTP 服务，无需额外 Web 框架；",
            "Vue 3 Composition API：useChat、useConversations 等 composable 管理响应式状态；",
            "SSE 流式协议：/chat/stream 以 text/event-stream 推送 token、tool_call、complete 事件；",
            "Playwright：deep_web_search 使用无头 Chromium 进行 Bing 检索与页面抓取；",
            "sentence-transformers：可选本地嵌入模型，支持离线记忆检索。",
        ],
    )

    add_heading(doc, "6.2 模块说明", level=2)
    add_body(doc, "各模块实现要点：")
    add_bullets(
        doc,
        [
            "agent/loop.py：实现消息接收→上下文构建→LLM 调用→工具执行循环，最大迭代 40 次，"
            "集成 MemoryConsolidator 在上下文溢出时归档；",
            "api/server.py：路由 /chat、/chat/stream、/settings、/memory、/sessions、/audio/upload、/health；",
            "agent/memory/：factory 组装记忆服务，retriever 实现 MR-Agent 检索，distiller 蒸馏策略，"
            "consolidator 整合会话记忆；",
            "agent/tools/：filesystem（读写目录）、shell（命令执行）、deep_web_search、cron、spawn（子代理）；",
            "channels/manager.py：按配置启用渠道，统一 publish 出站消息；",
            "frontend/stores/useChat.js：管理 messages、loading、stream 解析与错误处理；",
            "frontend/api/stream.js：fetch + ReadableStream 解析 SSE 事件并回调 UI。",
        ],
    )


def add_chapter7(doc):
    add_heading(doc, "7. 软件测试")
    add_heading(doc, "7.1 单元测试", level=2)
    add_body(
        doc,
        "backend/tests/ 目录包含 48 个测试文件，使用 pytest + pytest-asyncio。"
        "单元测试覆盖：Agent 循环（test_loop_save_turn、test_loop_consolidation_tokens）、"
        "记忆模块（test_memory_graph、test_reasoning_bank、test_mragent_retriever、test_strategy_distiller）、"
        "渠道适配（test_telegram_channel、test_feishu_post_content、test_dingtalk_channel）、"
        "工具校验（test_tool_validation、test_filesystem_tools、test_web_search）、"
        "配置迁移（test_config_migration、test_embedding_migration）等。",
    )

    add_heading(doc, "7.2 集成测试", level=2)
    add_body(
        doc,
        "集成测试验证跨模块协作：test_memory_integration 测试记忆写入→检索→注入全流程；"
        "test_session_api、test_memory_api、test_settings_api 测试 HTTP API 端到端；"
        "test_index_worker 验证异步索引任务；test_provider_retry 验证 LLM 调用重试策略。",
    )

    add_heading(doc, "7.3 确认测试", level=2)
    add_body(
        doc,
        "确认测试从用户场景出发：桌面宠物启动与聊天窗口切换、流式对话完整性、多会话切换、"
        "设置保存与重载、记忆页面数据展示。安全测试报告（DesktopClaw_安全测试报告.md）"
        "对 XSS 防护、路径穿越、Shell 执行策略、API Key 管理等进行代码审查与自动化验证，"
        "覆盖 246 个测试用例执行。",
    )

    add_heading(doc, "7.4 缺陷汇总", level=2)
    add_body(doc, "测试过程中发现的主要问题及处理：")
    add_bullets(
        doc,
        [
            "【严重】config/schema.py 中 ASR API Key 硬编码默认值 → 建议改为空字符串，由用户配置；",
            "【建议】前端 API Key 存于 localStorage，存在 XSS 窃取风险 → 建议迁移至 Electron safeStorage；",
            "【已修复】聊天气泡鼠标穿透导致无法点击 → App.vue 将 hover 监听移至 desktop-pet-wrapper；",
            "【待优化】深度网络研究可能触发 Bing 验证码 → 可通过 proxy 与 minIntervalS 缓解。",
        ],
    )


def add_chapter8_and_appendix(doc):
    add_heading(doc, "8. 总结")
    add_body(
        doc,
        "DesktopClaw 项目成功实现了一款功能完整的桌面 AI 智能助手系统，涵盖桌面宠物交互、流式对话、"
        "双域记忆、多工具 Agent 与多渠道消息接入。系统采用前后端分离与事件驱动架构，"
        "模块边界清晰，测试覆盖较为完善。后续可在安全加固（密钥管理、CSP 策略）、"
        "性能优化（记忆检索缓存、并发会话）与打包分发（electron-builder 一键安装）方向持续改进。",
    )

    add_heading(doc, "9. 附录")
    add_body(doc, "附录 A：主要 API 接口列表")
    add_bullets(
        doc,
        [
            "GET  /health — 健康检查",
            "POST /chat — 标准对话",
            "GET  /chat/stream — SSE 流式对话",
            "GET/POST /settings — 配置读写",
            "GET  /memory — 记忆数据查询",
            "GET  /sessions — 会话列表",
            "GET  /sessions/{id}/messages — 会话消息",
            "POST /audio/upload — 音频上传",
            "GET  /media/{path} — 媒体文件访问",
        ],
    )
    add_body(doc, "附录 B：项目目录结构（节选）")
    add_bullets(
        doc,
        [
            "desktopclaw/backend/desktopclaw/ — Python 后端主模块",
            "desktopclaw/frontend/src/ — Vue 3 前端源码",
            "desktopclaw/backend/tests/ — 自动化测试",
            "desktopclaw/readme.md — 前后端通信架构文档",
        ],
    )


def main():
    doc = Document()
    setup_page(doc)
    add_cover_and_toc(doc)
    add_chapter1(doc)
    doc.add_page_break()
    add_chapter2(doc)
    doc.add_page_break()
    add_chapter3(doc)
    doc.add_page_break()
    add_chapter4(doc)
    doc.add_page_break()
    add_chapter5(doc)
    doc.add_page_break()
    add_chapter6(doc)
    doc.add_page_break()
    add_chapter7(doc)
    doc.add_page_break()
    add_chapter8_and_appendix(doc)
    doc.save(OUTPUT)
    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    main()
