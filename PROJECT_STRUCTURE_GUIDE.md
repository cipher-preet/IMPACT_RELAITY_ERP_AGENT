# 📁 Impact Chatbot - Project Structure Guide

**Simple Overview:** This project is an AI Chatbot System that can understand what users want, make decisions, and take actions using AI. It has a **Frontend** that talks to a **Web Server (Node.js)**, which talks to a **Python AI Engine** that does all the smart thinking.

---

## 🎯 Project Structure at a Glance

```
Impact_Chatbot/
├── apps/                           # Main application code
│   ├── agent_runtime/              # The "Brain" - AI thinking and planning
│   └── api_gateway/                # The "Front Door" - handles web requests
├── docs/                           # Documentation and guides
├── README.md                        # Project overview
└── ASSISTANT_AI_API.md             # Technical API documentation
```

---

## 📂 Detailed Folder Breakdown

---

### **1. ROOT LEVEL FILES**

#### `README.md`
**What it is:** The welcome/instruction manual  
**In simple words:** Tells you what this project does, how to start it, and what technology it uses  
**What's inside:**
- Project description and features
- How to start the Python AI server
- How to start the FastAPI web server
- Technology stack used

#### `ASSISTANT_AI_API (1).md`
**What it is:** The communication contract/manual  
**In simple words:** Explains how the Frontend talks to Python AI, what format messages should be in, and what to expect back  
**What's inside:**
- Frontend-to-Backend API details
- gRPC (special communication protocol) specifications
- MCP (tool-calling protocol) details
- Error handling and permission rules
- Intent classifier guidance

#### `docs/` folder
**What it is:** Extra documentation  
**What's inside:**
- `ASSISTANT_INTENT_CLASSIFIER.md` - Explains how the AI understands user intentions

---

### **2. `apps/` - The Heart of the Application**

This folder contains all the working code for the AI chatbot.

#### **2.1 `apps/api_gateway/` - The Front Door**

**Purpose:** This is where web requests come in. It's like the receptionist that greets visitors.

```
api_gateway/
├── main.py                 # The entry point - starts the web server
├── config/
│   └── setting.py          # Configuration settings (like database URLs, API keys)
├── controllers/
│   └── health_controller.py # Checks if the system is healthy/working
├── middleware/
│   └── logging.py          # Records all requests and responses
├── routes/
│   ├── __init__.py
│   ├── health.py           # Health check API endpoint
│   └── Test.py             # Test endpoints
└── utils/
    └── response.py         # Helper to format API responses nicely
```

**What each file does:**

| File | Purpose | Simple Explanation |
|------|---------|-------------------|
| `main.py` | Server startup | Starts the web server and connects to AI engine |
| `setting.py` | Configuration | Stores all settings like passwords, URLs, port numbers |
| `health_controller.py` | Health check | Tests if system is working (like a heartbeat check) |
| `logging.py` | Request tracking | Writes down every request made to the system |
| `health.py` | Health endpoint | API path you can visit to check if server is alive |
| `Test.py` | Testing endpoint | API path for testing features |
| `response.py` | Response formatting | Makes API responses look nice and consistent |

---

#### **2.2 `apps/agent_runtime/` - The Brain**

**Purpose:** This is where all the AI intelligence happens. This is the "thinking engine" of the chatbot.

```
agent_runtime/
├── agents/                 # AI agents configuration
├── graphs/                 # Workflow graphs
├── grpc_runtime/          # Network communication handler
├── llms/                  # AI model integration (OpenAI)
├── mcp/                   # Tool discovery and calling
├── nodes/                 # Individual processing steps
├── runtime/               # Runtime manager
├── state/                 # Data structures
└── tools/                 # Tool registry
```

---

#### **2.2.1 `agents/` - Configuration and Rules**

**Purpose:** Defines what the AI agents should do and how they should behave.

```
agents/
├── config/
│   └── settings.py        # Agent configuration settings
├── constants/
│   ├── event_types.py     # Types of events the system can create
│   └── intents.py         # Different user intentions the AI recognizes
├── executor/              # Runs the tasks
│   ├── argument_generator.py    # Figures out what inputs a tool needs
│   ├── capability_resolver.py   # Finds which tool can do the job
│   ├── entity_resolver.py       # Identifies what the user is talking about
│   ├── execution_supervisor.py  # Oversees task execution
│   ├── parallel_executor.py     # Runs multiple tasks at same time
│   └── task_executor.py         # Runs individual tasks
├── planner/               # Plans what to do
│   └── decomposition.py   # Breaks big task into small steps
├── prompts/               # Instructions for AI
│   ├── executor/          # Instructions for doing tasks
│   ├── formatting/        # Instructions for formatting responses
│   ├── memory/           # Instructions for remembering things
│   ├── planner/          # Instructions for planning
│   ├── supervisor/       # Instructions for understanding intent
│   └── tool_selector/    # Instructions for choosing tools
├── schemas/               # Data format definitions
├── supervisor/            # Oversees the whole process
│   ├── graph_router.py    # Routes requests to right handler
│   └── intent_classifier.py # Understands what user wants
```

**What each component does:**

| Component | Purpose | Simple Explanation |
|-----------|---------|-------------------|
| **config/** | Settings | Stores agent behavior settings |
| **constants/** | Definitions | Defines what event types and user intentions exist |
| **executor/** | Task running | Actually runs the tasks the AI planned |
| **planner/** | Task planning | Takes a big goal and breaks it into small steps |
| **prompts/** | AI instructions | Instructions given to ChatGPT/AI about what to do |
| **schemas/** | Data structure | Defines format of data used in different parts |
| **supervisor/** | Oversight | Makes decisions about what to do with user input |

---

#### **2.2.2 `graphs/` - Workflow Orchestration**

**Purpose:** Defines the flow of how information moves through the system.

```
graphs/
└── supervisor_graph/
    └── graph.py           # Main workflow - how information flows
```

**What it does:** Defines the order of operations - like a flowchart that says "First understand intent, then plan, then execute, then format response"

---

#### **2.2.3 `grpc_runtime/` - Network Communication**

**Purpose:** Handles communication between the Node.js web server and Python AI engine over a special protocol called gRPC.

```
grpc_runtime/
├── __init__.py
├── generated/             # Auto-generated code from proto file
│   ├── __init__.py
│   ├── ai_runtime_pb2.py           # Message format definitions
│   └── ai_runtime_pb2_grpc.py      # Communication handler
├── handlers/
│   └── query_handler.py    # Processes incoming requests
├── proto/
│   ├── __init__.py
│   └── ai_runtime.proto    # Blueprint for messages
├── runtime/
│   ├── __init__.py
│   └── runtime_manager.py  # Manages the gRPC service
├── server/
│   ├── __init__.py
│   └── server.py           # Starts the gRPC server
```

**What each file does:**

| File | Purpose | Simple Explanation |
|------|---------|-------------------|
| `ai_runtime.proto` | Blueprint | Defines what messages look like (like XML schema) |
| `ai_runtime_pb2.py` | Message format | Auto-generated - defines message structure |
| `ai_runtime_pb2_grpc.py` | Communication | Auto-generated - handles sending/receiving messages |
| `query_handler.py` | Request handler | Takes incoming requests and processes them |
| `runtime_manager.py` | Service manager | Starts and manages the gRPC service |
| `server.py` | Server startup | Actually starts the gRPC server |

---

#### **2.2.4 `llms/` - AI Model Integration**

**Purpose:** Connects to AI models like ChatGPT to do the actual thinking.

```
llms/
└── openai/
    └── openai_client.py   # Talks to OpenAI's ChatGPT API
```

**What it does:** 
- Connects to OpenAI's GPT models
- Sends prompts to ChatGPT
- Gets intelligent responses back

---

#### **2.2.5 `mcp/` - Tool Discovery and Usage**

**Purpose:** Finds what tools are available and allows the AI to use them.

MCP = "Model Context Protocol" - a way for AI to discover and call tools/functions.

```
mcp/
├── client/
│   └── mcp_client.py      # Calls tools from Node.js
└── discovery/
    └── tool_discovery.py  # Finds what tools are available
```

**What it does:**
- Discovers available tools (like "send email", "create task", etc.)
- Calls those tools when AI decides it needs them
- Gets results back from those tools

---

#### **2.2.6 `nodes/` - Processing Steps**

**Purpose:** Defines each step of the AI thinking process as individual "nodes" that can be connected.

```
nodes/
├── execution/             # Actually doing the work
│   ├── executor_node.py   # Executes planned tasks
│   └── tool_selector.py   # Chooses which tool to use
├── formatting/            # Making output pretty
│   └── response_formatter.py # Formats AI response for user
├── human_in_the_loop/     # Gets human approval
│   ├── hitl_builder.py    # Builds approval request
│   └── human_response_node.py # Gets human's decision
├── memory/                # Remembering things
│   ├── checkpoint_resume_node.py # Saves/loads progress
│   ├── load_memory.py     # Loads conversation history
│   └── normalizers/       # Cleans up memory data
├── planning/              # Making a plan
│   └── planner_node.py    # Creates action plan
└── reasoning/             # Understanding intent
    └── intent_node.py     # Figures out what user wants
```

**What each node does:**

| Node | Purpose | Simple Explanation |
|------|---------|-------------------|
| `executor_node.py` | Task execution | Actually performs the planned actions |
| `tool_selector.py` | Tool selection | Picks the right tool for the job |
| `response_formatter.py` | Output formatting | Makes response readable for user |
| `hitl_builder.py` | Approval request | Asks human to approve action |
| `human_response_node.py` | Human feedback | Gets human's yes/no decision |
| `checkpoint_resume_node.py` | Progress saving | Saves where it left off in case of interruption |
| `load_memory.py` | History loading | Loads past conversations |
| `planner_node.py` | Planning | Creates step-by-step plan |
| `intent_node.py` | Intent understanding | Figures out what user wants to do |

---

#### **2.2.7 `runtime/` - Runtime Manager**

**Purpose:** Manages the startup and runtime of the entire AI system.

```
runtime/
└── runtime_manager.py     # Initializes system, loads tools
```

**What it does:**
- Starts up the AI system
- Loads all available tools
- Sets up the AI environment
- Manages the overall runtime lifecycle

---

#### **2.2.8 `state/` - Data Structures**

**Purpose:** Defines the shape of data that flows through the system.

```
state/
└── graph_state.py         # Defines what information flows in the workflow
```

**What it does:** Defines what data is tracked and passed between each processing step

---

#### **2.2.9 `tools/` - Tool Registry**

**Purpose:** Keeps track of all available tools/functions the AI can use.

```
tools/
└── registry/
    ├── capability_registry.py # Stores what capabilities are available
    └── tool_registry.py       # Stores what tools are available
```

**What it does:** 
- Maintains a list of all available tools
- Helps the AI find the right tool when it needs something

---

### **3. `apps/__init__.py`**

**What it is:** An empty marker file  
**Purpose:** Tells Python this folder is a package (can be imported)

---

### **4. `apps/dependencies/` - External Dependencies**

**Purpose:** Houses shared dependencies used across the application.

```
dependencies/
└── mcp/
    └── mcp.py             # Shared MCP utilities
```

---

## 🔄 How Everything Works Together

### **Simple Flow:**

1. **User sends message** via Frontend
2. **API Gateway receives it** (`api_gateway/main.py`)
3. **gRPC server** (`grpc_runtime/server.py`) sends to Python
4. **Runtime Manager** starts processing (`runtime/runtime_manager.py`)
5. **Intent Node** figures out what user wants (`nodes/reasoning/intent_node.py`)
6. **Planner Node** makes a plan (`nodes/planning/planner_node.py`)
7. **Executor Node** runs tasks (`nodes/execution/executor_node.py`)
8. **Tool Selector** picks right tool (`nodes/execution/tool_selector.py`)
9. **MCP Client** calls the tool (`mcp/client/mcp_client.py`)
10. **Response Formatter** makes response pretty (`nodes/formatting/response_formatter.py`)
11. **Response sent back** to user

---

## 🚀 Starting the System

### **Start Python AI Engine:**
```bash
python -m apps.agent_runtime.grpc_runtime.server.server
```

### **Start Web API Server:**
```bash
uvicorn apps.api_gateway.main:app --reload
```

---

## 📊 Summary Table

| Folder | What it Does | Key Files |
|--------|-------------|-----------|
| `api_gateway/` | Receives web requests | `main.py`, `routes/` |
| `agent_runtime/` | AI thinking engine | `nodes/`, `graphs/`, `agents/` |
| `grpc_runtime/` | Network communication | `server.py`, `handlers/` |
| `llms/` | AI model connection | `openai_client.py` |
| `mcp/` | Tool discovery & calling | `tool_discovery.py`, `mcp_client.py` |
| `nodes/` | Processing steps | Planning, executing, formatting |
| `runtime/` | System startup | `runtime_manager.py` |
| `tools/` | Available tools list | `tool_registry.py`, `capability_registry.py` |

---

## 💡 Key Concepts Explained

### **gRPC**
- A fast way for programs to talk to each other
- Like a phone call instead of sending email

### **MCP (Model Context Protocol)**
- A way for AI to discover and use tools
- Like giving AI access to a toolbox

### **Nodes**
- Individual steps in the thinking process
- Like building blocks that connect together

### **Agents**
- The configuration and rules for AI behavior
- Like instructions for how the AI should act

### **Graph**
- The workflow showing how data flows
- Like a flowchart showing the order of operations

---

## 🎓 For Different Roles

### **Frontend Developer**
Focus on: `api_gateway/routes/` - understand API endpoints

### **Backend Developer**
Focus on: `api_gateway/` - understand server setup and routing

### **AI/ML Developer**
Focus on: `agent_runtime/agents/`, `agents/prompts/` - understand AI logic

### **DevOps/Infrastructure**
Focus on: `grpc_runtime/server.py`, `main.py` - understand startup commands

### **Tool Integration**
Focus on: `mcp/`, `tools/registry/` - understand tool registration

---

**Created:** 2026-06-18  
**Project:** Impact Chatbot - AI Agent Platform
