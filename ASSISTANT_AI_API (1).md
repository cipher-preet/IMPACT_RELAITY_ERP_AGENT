# Assistant AI API, gRPC, MCP, Python Contract, and Intent Guide

Base URL: `http://localhost:3000/api/v1` or your deployed host.

This document explains how the persistent AI assistant is used end to end. The browser only talks to NodeJS. NodeJS talks to the Python AI service over gRPC. The Python AI service calls NodeJS MCP tools when it needs data or business actions.

This is the single source of truth for assistant AI documentation. It combines the API flow, Python gRPC contract, MCP contract, failure handling rules, and intent classifier guidance.

## Document Index

Use this index to jump to the section that matches your work.

| Requirement | Read Section |
|---|---|
| Understand full assistant ownership and runtime flow | `1. Responsibility Split` |
| Configure NodeJS and Python service secrets | `2. Required Environment` |
| Integrate frontend assistant APIs and SSE | `3. Frontend to NodeJS API Sequence` and `4. Frontend Rendering Rules` |
| Implement Python gRPC server request/response handling | `5. NodeJS to Python gRPC Integration` and `11. Python gRPC Contract Checklist` |
| Implement Python MCP client calls | `6. Python AI to NodeJS MCP Integration` and `12. MCP Request/Response Contract` |
| Handle gRPC, MCP, permission, validation, timeout, and malformed payload failures | `13. Failure Cases and Required Python Behavior` |
| Understand browser, Python service, and business permission boundaries | `7. Authentication and Permission Model` |
| Resolve ambiguous users/entities safely | `8. Safe Entity Resolution Flow` |
| Understand NodeJS responsibilities without internal implementation details | `9. NodeJS Platform Boundary` |
| Know current contract status | `10. Current Contract Status` |
| Build the intent classifier prompt/model | `14. Intent Classifier Contract` |
| Know how to update this doc when contracts change | `15. Contract Update Rules` |

```text
Frontend
  -> NodeJS REST/SSE
  -> Authenticated assistant run
  -> Python AI over gRPC
  -> Python MCP client
  -> NodeJS MCP server
  -> MCP tool
  -> NodeJS business layer
```

The frontend only needs the REST/SSE contract. Python only needs the gRPC and MCP contracts. NodeJS keeps its internal implementation behind these contracts.

---

## 1. Responsibility Split

### Frontend

The frontend sends user messages, renders chat history, opens an SSE stream for live progress, and reconnects after refresh. It never calls Python AI and never calls the MCP server.

### NodeJS

NodeJS authenticates the browser user, owns assistant run state, builds the context sent to Python, streams events to the frontend through SSE, calls the Python AI service through gRPC, and exposes MCP tools for Python.

### Python AI

Python receives trusted run context from NodeJS over gRPC, performs LLM reasoning/planning, streams progress back to NodeJS, and calls NodeJS MCP tools when it needs data or actions.

### MCP Tools

MCP tools live in NodeJS and execute through the NodeJS business layer. Python receives structured tool results; it does not need to know how NodeJS implements those tools internally.

---

## 2. Required Environment

NodeJS requires a service token for the MCP endpoint:

```env
ASSISTANT_MCP_SERVER_TOKEN=replace-with-long-random-secret
ASSISTANT_AI_GRPC_TARGET=localhost:50051
ASSISTANT_AI_GRPC_TLS=false
ASSISTANT_AI_GRPC_TOKEN=optional-python-grpc-token
```

The Python MCP client must send this token:

```http
Authorization: Bearer replace-with-long-random-secret
```

This token authenticates the Python service. It does not authenticate the end user.

`ASSISTANT_AI_GRPC_TARGET` tells NodeJS where the Python assistant gRPC server is listening. Use `localhost:50051` for local development when Python runs on the same machine. Use a service DNS name such as `assistant-ai:50051` in Docker or Kubernetes.

`ASSISTANT_AI_GRPC_TLS` controls the NodeJS gRPC channel credentials. Use `false` for local/Docker private-network development unless the Python service exposes TLS. Use `true` only when the Python gRPC endpoint is configured with server TLS.

`ASSISTANT_AI_GRPC_TOKEN` is optional metadata sent by NodeJS to Python as:

```http
authorization: Bearer <ASSISTANT_AI_GRPC_TOKEN>
```

Use it if the Python gRPC server validates service-to-service callers. Do not expose it to the frontend.

### How Python Gets the MCP Token

`ASSISTANT_MCP_SERVER_TOKEN` is a shared service credential between NodeJS and the Python AI service. It should be generated once per environment and injected into both services by the deployment platform or secret manager.

Example local configuration:

```env
# NodeJS .env
ASSISTANT_MCP_SERVER_TOKEN=local-dev-long-random-secret
ASSISTANT_AI_GRPC_TARGET=localhost:50051
ASSISTANT_AI_GRPC_TLS=false
ASSISTANT_AI_GRPC_TOKEN=local-node-to-python-secret
```

```env
# Python AI .env
NODE_MCP_SERVER_URL=http://localhost:3000/api/v1/mcp
NODE_MCP_SERVER_TOKEN=local-dev-long-random-secret
PYTHON_GRPC_BIND_ADDRESS=0.0.0.0:50051
PYTHON_GRPC_AUTH_TOKEN=local-node-to-python-secret
```

Example production configuration:

```text
Secret manager:
  assistant-mcp-server-token = prod-long-random-secret

NodeJS deployment:
  ASSISTANT_MCP_SERVER_TOKEN <- assistant-mcp-server-token
  ASSISTANT_AI_GRPC_TARGET <- assistant-ai:50051
  ASSISTANT_AI_GRPC_TLS <- false
  ASSISTANT_AI_GRPC_TOKEN <- assistant-ai-grpc-token

Python AI deployment:
  NODE_MCP_SERVER_TOKEN <- assistant-mcp-server-token
  NODE_MCP_SERVER_URL <- https://api.yourdomain.com/api/v1/mcp
  PYTHON_GRPC_AUTH_TOKEN <- assistant-ai-grpc-token
```

Python should send the token as:

```http
Authorization: Bearer <NODE_MCP_SERVER_TOKEN>
```

Do not expose this token to the frontend. Do not return it from any API. Do not log it. This token only proves that the caller is the trusted Python service; it does not prove which app user is making a request.

---

## 3. Frontend to NodeJS API Sequence

### Step 1: Send a User Message

```http
POST /api/v1/assistant/messages
Cookie: impact_session=...
Content-Type: application/json
```

Body:

```json
{
  "message": "delete rahool",
  "agencyId": "2d72ce1f-8a4a-49c2-8f22-000000000001"
}
```

`agencyId` is optional, but should be sent when the user is working inside an agency context.

Success response:

```json
{
  "success": true,
  "message": "I'm getting started.",
  "data": {
    "runId": "9f44fd50-fb3a-49f3-95e5-000000000001",
    "status": "running"
  },
  "requestId": "req_...",
  "timestamp": "2026-05-27T10:00:00.000Z"
}
```

Frontend abstraction:

```text
The request starts an assistant run.
The response returns the run ID and current run status.
The frontend should then open the SSE stream for that run.
```

### Step 2: Open SSE Stream for Live Progress

```http
GET /api/v1/assistant/runs/:runId/events?afterSequence=0
Cookie: impact_session=...
Accept: text/event-stream
```

Example:

```http
GET /api/v1/assistant/runs/9f44fd50-fb3a-49f3-95e5-000000000001/events?afterSequence=0
```

SSE event example:

```text
id: 1
event: run_started
data: {"id":"...","runId":"...","sequence":1,"eventType":"run_started","payload":{"message":"I'm getting started."},"createdAt":"..."}

id: 2
event: thinking
data: {"id":"...","runId":"...","sequence":2,"eventType":"thinking","payload":{"message":"Thinking..."},"createdAt":"..."}

id: 3
event: final_message
data: {"id":"...","runId":"...","sequence":3,"eventType":"final_message","payload":{"message":"Which Rahul do you mean?"},"createdAt":"..."}
```

The frontend should store the latest received `sequence`. If the browser refreshes or reconnects, pass it as `afterSequence`.

### Step 3: Browser Refresh Recovery

After refresh, first ask NodeJS whether the user has an active run:

```http
GET /api/v1/assistant/runs/active
Cookie: impact_session=...
```

Response when active:

```json
{
  "success": true,
  "message": "Active assistant conversation fetched successfully.",
  "data": {
    "id": "9f44fd50-fb3a-49f3-95e5-000000000001",
    "status": "running",
    "startedAt": "2026-05-27T10:00:00.000Z",
    "endedAt": null,
    "lastSequence": 4
  }
}
```

Then reconnect:

```http
GET /api/v1/assistant/runs/:runId/events?afterSequence=:lastSeenSequence
```

### Step 4: Load Persistent Chat History

```http
GET /api/v1/assistant/history
Cookie: impact_session=...
```

Response:

```json
{
  "success": true,
  "message": "Assistant history fetched successfully.",
  "data": [
    {
      "id": "msg-id",
      "runId": "run-id",
      "senderType": "user",
      "message": "delete rahool",
      "metadata": null,
      "createdAt": "2026-05-27T10:00:00.000Z"
    },
    {
      "id": "msg-id",
      "runId": "run-id",
      "senderType": "assistant",
      "message": "Which Rahul do you mean?",
      "metadata": {
        "eventType": "follow_up_question"
      },
      "createdAt": "2026-05-27T10:00:02.000Z"
    }
  ]
}
```

---

## 4. Frontend Rendering Rules

The frontend should render event types based on `eventType`.

| Event Type | Recommended UI |
|---|---|
| `run_started` | Start progress state |
| `thinking` | Show "Thinking..." |
| `analyzing` | Show "Analyzing request..." |
| `tool_start` | Show tool/action progress |
| `tool_result` | Optionally show completed progress |
| `tool_error` | Show safe error state |
| `follow_up_question` | Render assistant question and input |
| `confirmation_required` | Render confirmation UI |
| `waiting_for_user` | Keep run paused for user input |
| `permission_denied` | Show permission-safe message |
| `final_message` | Render assistant response |
| `run_completed` | Close active progress |
| `run_failed` | Show safe failure message |
| `run_cancelled` | Show cancelled state |

The SSE connection is temporary. It should be opened only for an active run and will close automatically after the run reaches `completed`, `failed`, or `cancelled`.

---

## 5. NodeJS to Python gRPC Integration

NodeJS owns the assistant run. When a run starts, NodeJS sends context to Python over gRPC.

Proto file:

```text
Backend/infrastructure/grpc/proto/assistant_ai.proto
```

Service:

```proto
service AssistantAiService {
  rpc RunAssistant(stream AssistantStreamRequest) returns (stream AssistantStreamResponse);
}
```

NodeJS sends `AssistantRunStart`:

```proto
message AssistantRunStart {
  string run_id = 1;
  string user_id = 2;
  string session_id = 3;
  string agency_id = 4;
  string user_message = 5;
  string summary_memory = 6;
  string pending_task_context_json = 7;
  string recent_messages_json = 8;
  string access_json = 9;
}
```

### `AssistantRunStart` Field Contract

`AssistantRunStart` is the initial context payload that NodeJS sends to Python for one assistant execution. Python should use this payload to reason, plan, stream progress, and call MCP tools. Python should not treat user text or LLM output as trusted business input; any business action must still go through MCP tools.

| Field | Source abstraction | Meaning | How Python Should Use It |
|---|---|---|---|
| `run_id` | NodeJS assistant run state | Unique ID for this assistant execution. | Store it for the whole run and include it in every MCP tool call as `_meta.runId`. NodeJS uses it to attach the call to the real authenticated user. |
| `user_id` | Authenticated NodeJS session user | ID of the logged-in application user. | Use only for correlation/logging. Do not send it as trusted MCP identity. Node MCP derives user identity from `run_id`. |
| `session_id` | NodeJS auth session cookie/session lookup | Current user session ID if available. | Use only for tracing/debugging. It may be empty. |
| `agency_id` | Frontend request body, when user is inside an agency context | Current agency context for agency-scoped workflows. | Use as a planning hint and pass it to MCP as `_meta.agencyId` when calling agency-scoped tools. Usecases still validate access. |
| `user_message` | Latest message from the authenticated user | Natural-language instruction, such as `delete rahool`. | Main LLM input for intent detection and planning. Treat it as untrusted text. |
| `summary_memory` | NodeJS assistant memory | Compact memory summary for this user's persistent assistant. | Include in LLM context instead of full historical chat. It may be empty. |
| `pending_task_context_json` | NodeJS pending assistant task state | Paused workflow state, such as pending clarification or confirmation. | Parse JSON and resume the workflow safely. If invalid/empty, continue without pending state. |
| `recent_messages_json` | NodeJS conversation history abstraction | Recent visible conversation history. | Parse JSON and include in LLM context for short-term continuity. |
| `access_json` | NodeJS access snapshot | Current roles and permissions known to NodeJS. | Use as advisory planning context only. Final permission is checked by NodeJS when MCP tools run. |

Example decoded `recent_messages_json`:

```json
[
  {
    "senderType": "user",
    "message": "delete rahool",
    "createdAt": "2026-05-27T10:00:00.000Z"
  },
  {
    "senderType": "assistant",
    "message": "Which Rahul do you mean?",
    "createdAt": "2026-05-27T10:00:02.000Z"
  }
]
```

Example decoded `pending_task_context_json`:

```json
{
  "intent": "delete_user",
  "step": "disambiguation",
  "waitingFor": "follow_up_question",
  "confirmationRequired": true,
  "candidates": [
    {
      "id": "user-id-1",
      "label": "Rahul Sharma",
      "type": "user"
    },
    {
      "id": "user-id-2",
      "label": "Rahul Verma",
      "type": "user"
    }
  ]
}
```

Example decoded `access_json`:

```json
{
  "roles": ["admin"],
  "permissions": ["agency.member.view", "board.member.add"]
}
```

Python should parse JSON fields defensively. Optional fields may be empty depending on the run. A missing `summary_memory` should not fail the run.

Python streams `AssistantEvent` back:

```proto
message AssistantEvent {
  string event_type = 1;
  string message = 2;
  string payload_json = 3;
  string summary_memory = 4;
}
```

Example Python progress response:

```json
{
  "event_type": "thinking",
  "message": "Thinking...",
  "payload_json": "{\"stage\":\"intent_detection\"}"
}
```

### How Python Knows What `AssistantEvent` to Send

Python should send event types that NodeJS and the frontend already understand. These event types are part of the public assistant event contract and are rendered by the frontend through SSE.

Recommended event contract:

| Event Type | When Python Should Send It | Message Required |
|---|---|---|
| `thinking` | Python has started reasoning about the request. | No, but recommended |
| `analyzing` | Python is detecting intent, planning, or reading context. | No, but recommended |
| `tool_start` | Python is about to call an MCP tool. | No, but useful for progress UI |
| `tool_result` | Python received and interpreted an MCP tool result. | No |
| `tool_error` | MCP call failed or returned an unusable result. | Recommended |
| `follow_up_question` | Python needs missing information or entity disambiguation. | Yes |
| `confirmation_required` | Python needs explicit confirmation before a destructive action. | Yes |
| `waiting_for_user` | Python is intentionally pausing the run for user input. | Recommended |
| `permission_denied` | MCP result indicates the user cannot perform the action. | Yes |
| `final_message` | Python has completed the run and has a final answer. | Yes |
| `run_failed` | Python cannot continue safely. | Yes |
| `run_cancelled` | The run was cancelled. | Yes |

Example event sequence for entity disambiguation:

```text
AssistantEvent(
  event_type="thinking",
  message="Thinking...",
  payload_json="{\"stage\":\"start\"}"
)

AssistantEvent(
  event_type="analyzing",
  message="Searching for matching users...",
  payload_json="{\"stage\":\"entity_resolution\",\"entity\":\"user\"}"
)

AssistantEvent(
  event_type="follow_up_question",
  message="I found multiple Rahul users. Which one do you mean?",
  payload_json="{\"candidates\":[{\"id\":\"user-id-1\",\"label\":\"Rahul Sharma\",\"confidence\":0.93},{\"id\":\"user-id-2\",\"label\":\"Rahul Verma\",\"confidence\":0.82}]}"
)
```

Example event sequence for final success:

```text
AssistantEvent(
  event_type="final_message",
  message="Rahul Sharma has been removed from the board.",
  payload_json="{}"
)
```

NodeJS receives Python events, stores the assistant run output, and forwards live events to the frontend through SSE. Python does not need to know the storage tables or internal persistence model.

Important: gRPC is not used for MCP tool execution. gRPC is for assistant run messages, progress, and final responses.

---

## 6. Python AI to NodeJS MCP Integration

MCP endpoint:

```http
POST /api/v1/mcp
Authorization: Bearer <ASSISTANT_MCP_SERVER_TOKEN>
Content-Type: application/json
```

### Initialize MCP Session

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {}
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-06-18",
    "capabilities": {
      "tools": {
        "listChanged": false
      }
    },
    "serverInfo": {
      "name": "impact-node-mcp",
      "version": "1.0.0"
    }
  }
}
```

### List Tools

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

Response shape:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "assistant.list_tools",
        "description": "List the assistant tools that are currently available.",
        "inputSchema": {
          "type": "object",
          "properties": {},
          "additionalProperties": false
        },
        "annotations": {
          "scope": "platform",
          "riskLevel": "read",
          "requiredPermissions": [],
          "requiresConfirmation": false
        }
      },
      {
        "name": "users.search_user_details",
        "description": "Search user details by fuzzy name, email, or phone query for safe entity resolution.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "minLength": 1,
              "description": "Name, email, or phone text to search. Typos are accepted."
            },
            "agencyId": {
              "type": "string",
              "format": "uuid",
              "description": "Agency ID used to scope the user search."
            },
            "limit": {
              "type": "integer",
              "minimum": 1,
              "maximum": 25,
              "description": "Maximum number of candidates to return."
            }
          },
          "required": ["agencyId", "query"],
          "additionalProperties": false
        },
        "annotations": {
          "scope": "user",
          "riskLevel": "read",
          "requiredPermissions": ["agency.member.view"],
          "requiresConfirmation": false
        }
      },
      {
        "name": "board.list_boards",
        "description": "List boards for an agency through the existing board use case and permission rules.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "agencyId": {
              "type": "string",
              "format": "uuid",
              "description": "Agency ID whose boards should be listed."
            }
          },
          "required": ["agencyId"],
          "additionalProperties": false
        },
        "annotations": {
          "scope": "agency",
          "riskLevel": "read",
          "requiredPermissions": [],
          "requiresConfirmation": false
        }
      }
    ]
  }
}
```

Current registered tools:

| Tool | Purpose |
|---|---|
| `assistant.list_tools` | Lists registered assistant tools. |
| `users.search_user_details` | Fuzzy-searches user details by name, email, phone, or full name. |
| `board.list_boards` | Lists agency boards through the existing board use case. |
| `agency.list_agency_details` | Lists agency details through the existing agency use case. |

### Call a Tool

Example: fuzzy-search users for safe entity resolution.

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "users.search_user_details",
    "arguments": {
      "agencyId": "2d72ce1f-8a4a-49c2-8f22-000000000001",
      "query": "rahool",
      "limit": 10
    },
    "_meta": {
      "runId": "9f44fd50-fb3a-49f3-95e5-000000000001",
      "agencyId": "2d72ce1f-8a4a-49c2-8f22-000000000001",
      "requestId": "req_...",
      "confirmed": false
    }
  }
}
```

Important rules:

- Python must send `_meta.runId`.
- Python gets `_meta.runId` from `AssistantRunStart.run_id` over gRPC.
- Python must not send trusted `userId`.
- NodeJS resolves the real user from the assistant run.
- The MCP tool executes through the NodeJS business layer.
- NodeJS performs final permission and business-rule checks.

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"status\":\"success\",\"data\":{\"candidates\":[{\"id\":\"user-id-1\",\"label\":\"Rahul Sharma\",\"type\":\"user\",\"email\":\"rahul@example.com\",\"phone\":\"9999999999\",\"firstName\":\"Rahul\",\"lastName\":\"Sharma\",\"confidence\":0.93}]}}"
      }
    ],
    "isError": false,
    "structuredContent": {
      "status": "success",
      "data": {
        "candidates": [
          {
            "id": "user-id-1",
            "label": "Rahul Sharma",
            "type": "user",
            "email": "rahul@example.com",
            "phone": "9999999999",
            "firstName": "Rahul",
            "lastName": "Sharma",
            "confidence": 0.93
          }
        ]
      }
    }
  }
}
```

Example: list boards for an agency.

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "board.list_boards",
    "arguments": {
      "agencyId": "2d72ce1f-8a4a-49c2-8f22-000000000001"
    },
    "_meta": {
      "runId": "9f44fd50-fb3a-49f3-95e5-000000000001",
      "agencyId": "2d72ce1f-8a4a-49c2-8f22-000000000001",
      "requestId": "req_..."
    }
  }
}
```

---

## 7. Authentication and Permission Model

There are three checks, and they are intentionally different.

### Browser User Authentication

```text
Frontend -> NodeJS
```

The browser user is authenticated by the normal NodeJS web session.

### Python Service Authentication

```text
Python AI -> NodeJS MCP
```

Python is authenticated by:

```http
Authorization: Bearer <ASSISTANT_MCP_SERVER_TOKEN>
```

This proves the caller is the trusted Python AI service.

### Business Permission

```text
MCP tool -> NodeJS business permission layer
```

The use case checks whether the real user can perform the action.

The real user is derived from:

```text
_meta.runId -> NodeJS assistant run owner
```

This prevents Python from impersonating another user.

---

## 8. Safe Entity Resolution Flow

For a request like:

```text
delete rahool
```

Expected flow:

```text
User sends message
Node creates run
Python detects destructive intent
Python calls users.search_user_details via MCP
NodeJS resolves the assistant run owner
MCP tool runs through the NodeJS business layer
NodeJS returns fuzzy candidates
Python asks follow-up question over gRPC
Node persists follow_up_question event
Frontend shows options
User selects candidate
Python asks confirmation
User confirms
Python calls destructive MCP tool with confirmed=true
Tool runs through the NodeJS business layer
NodeJS checks permission
NodeJS applies the business action
Python sends final_message
Node completes run
```

The assistant must never guess which entity to mutate.

---

## 9. NodeJS Platform Boundary

This section is for NodeJS maintainers. Frontend and Python developers can skip it.

NodeJS exposes three stable boundaries:

| Boundary | Who uses it | What the consumer sees |
|---|---|---|
| Assistant REST API | Frontend | Start a run, fetch active run, fetch history. |
| Assistant SSE stream | Frontend | Ordered assistant events for one run. |
| Assistant gRPC client + MCP server | Python | gRPC run context, streamed event response, MCP tool calls. |

NodeJS hides these implementation details from external consumers:

- how assistant runs are stored,
- how events are persisted,
- how user sessions are resolved,
- how permissions are checked,
- how tools call business operations,
- how repositories or database tables are organized.

Contract rule:

```text
Frontend and Python depend on API/gRPC/MCP shapes only.
They must not depend on NodeJS folders, classes, database tables, or service names.
```

MCP tool implementation rule for NodeJS maintainers:

```text
Validation, execution, permission checks, and result formatting must stay behind the MCP contract.
Python should only see tool metadata, input schema, status, data, message, code, and details.
```

---

## 10. Current Contract Status

Implemented:

- Assistant REST APIs
- SSE event streaming and replay
- Persistent assistant run state and conversation history
- Node MCP HTTP JSON-RPC endpoint
- MCP tool registry and executor
- Registered MCP tools: `assistant.list_tools`, `users.search_user_details`, `board.list_boards`, `agency.list_agency_details`
- gRPC proto and real NodeJS gRPC client transport

Still required:

- Python AI gRPC server
- Business use cases for any missing operations
- More MCP tools for create/update/delete workflows as use cases become available
- Optional audit logs/rate limiting for MCP calls

---

## 11. Python gRPC Contract Checklist

Python must implement the `AssistantAiService.RunAssistant` gRPC method from:

```text
Backend/infrastructure/grpc/proto/assistant_ai.proto
```

NodeJS opens one stream per assistant run, writes one `run_start`, then ends the request side. Python should keep the response stream open while it reasons, calls MCP tools, and emits assistant events.

### Incoming gRPC Request

```proto
message AssistantRunStart {
  string run_id = 1;
  string user_id = 2;
  string session_id = 3;
  string agency_id = 4;
  string user_message = 5;
  string summary_memory = 6;
  string pending_task_context_json = 7;
  string recent_messages_json = 8;
  string access_json = 9;
}
```

| Field | Python rule |
|---|---|
| `run_id` | Required. Store it for the whole run and send it as `_meta.runId` in every MCP call. |
| `user_id` | Use only for logs/correlation. Do not treat it as permission proof. |
| `session_id` | Optional correlation value. May be empty. |
| `agency_id` | Optional planning context. For agency tools, send it as both `arguments.agencyId` and `_meta.agencyId`. |
| `user_message` | Main user instruction. Treat as untrusted natural language. |
| `summary_memory` | Optional assistant memory. Empty string means no summary. |
| `pending_task_context_json` | JSON string. Parse defensively; if invalid, continue without pending state and emit a safe progress/error event if needed. |
| `recent_messages_json` | JSON string containing recent chat messages. Parse defensively and default to `[]` if unusable. |
| `access_json` | JSON string with advisory access data. Use for planning only; NodeJS use cases enforce final permission. |

Expected decoded `recent_messages_json`:

```ts
type AssistantContextMessage = {
  senderType: "user" | "assistant" | "system";
  message: string;
  createdAt: string; // ISO datetime
};
```

### Outgoing gRPC Response

Python streams:

```proto
message AssistantEvent {
  string event_type = 1;
  string message = 2;
  string payload_json = 3;
  string summary_memory = 4;
}
```

Allowed `event_type` values:

```text
thinking
analyzing
tool_start
tool_result
tool_error
follow_up_question
partial_message
final_message
permission_denied
confirmation_required
waiting_for_user
run_started
run_completed
run_failed
run_cancelled
```

Python must keep `message` user-facing and plain. Put technical details in `payload_json`. `payload_json` should be a JSON object string such as `{}` or `{"stage":"entity_resolution"}`.

---

## 12. MCP Request/Response Contract

Python calls MCP through:

```http
POST /api/v1/mcp
Authorization: Bearer <ASSISTANT_MCP_SERVER_TOKEN>
Content-Type: application/json
```

Python must send JSON-RPC `2.0` requests.

### MCP Tool Call Request

```ts
type McpToolCallRequest = {
  jsonrpc: "2.0";
  id: string | number;
  method: "tools/call";
  params: {
    name: string;
    arguments: Record<string, unknown>;
    _meta: {
      runId: string;
      requestId?: string;
      agencyId?: string;
      confirmed?: boolean;
    };
  };
};
```

Required rules:

1. Always include `_meta.runId`.
2. For agency tools, include both `arguments.agencyId` and `_meta.agencyId`.
3. Do not send `userId`; NodeJS resolves the real user from the assistant run.
4. Do not retry write/destructive actions with `_meta.confirmed = true` unless the user explicitly confirmed.

### MCP Tool Call Response

```ts
type McpToolCallResponse<TData = unknown> = {
  jsonrpc: "2.0";
  id: string | number | null;
  result: {
    content: Array<{
      type: "text";
      text: string;
    }>;
    isError: boolean;
    structuredContent: McpToolResult<TData>;
  };
};

type McpToolResult<TData = unknown> =
  | {
      status: "success";
      data: TData;
      message?: string;
    }
  | {
      status:
        | "failed"
        | "permission_denied"
        | "requires_confirmation"
        | "requires_input";
      message: string;
      code?: string;
      details?: Record<string, unknown>;
    };
```

Python should read `result.structuredContent`. `result.content[0].text` is the same MCP result serialized as text for compatibility.

### Current MCP Tool Contracts

#### `assistant.list_tools`

Input:

```json
{}
```

Success data:

```ts
type ListToolsData = {
  tools: Array<{
    name: string;
    description: string;
    scope: "platform" | "agency" | "user";
    riskLevel: "read" | "write" | "destructive";
    requiredPermissions: string[];
    requiresConfirmation: boolean;
  }>;
};
```

#### `users.search_user_details`

Input:

```ts
type SearchUserDetailsInput = {
  agencyId: string;
  query: string;
  limit?: number;
};
```

Success data:

```ts
type SearchUserDetailsData = {
  candidates: Array<{
    id: string;
    label: string;
    type: "user";
    email: string | null;
    phone: string | null;
    firstName: string | null;
    lastName: string | null;
    confidence: number;
  }>;
};
```

#### `board.list_boards`

Input:

```ts
type ListBoardsInput = {
  agencyId: string;
};
```

Success data:

```ts
type ListBoardsData = {
  boards: Array<{
    id: string;
    agencyId: string;
    templateId: string | null;
    name: string;
    createdAt: string | Date;
    updatedAt: string | Date;
  }>;
};
```

#### `agency.list_agency_details`

Input:

```ts
type ListAgencyDetailsInput = {
  agencyId: string;
};
```

Current success data:

```ts
type ListAgencyDetailsData = {
  agancy: {
    agencyId: string;
    agencyName?: string | null;
    agencyEmail?: string | null;
    agencyPhoneNumber?: string | null;
    websiteUrl?: string | null;
    country?: unknown;
    emirate?: unknown;
    city?: unknown;
    addressLine?: string | null;
    tradeLicenseNumber?: string | null;
    issueDate?: string | Date | null;
  };
};
```

Compatibility note: NodeJS currently returns the key `agancy`. Python should read that exact key for now. If NodeJS later adds the corrected `agency` key, it should keep `agancy` temporarily for backward compatibility.

---

## 13. Failure Cases and Required Python Behavior

Python must handle both gRPC failures and MCP failures. A failure should not make Python guess, mutate data directly, or hide the state from NodeJS.

### gRPC Failure Cases

| Failure case | Where it happens | Current NodeJS behavior | Required Python behavior |
|---|---|---|---|
| Python gRPC server unavailable | NodeJS gRPC call | NodeJS fails the assistant run and sends a safe failure event to the frontend. | Python side should expose health checks and logs. No MCP call should happen because the run never reaches Python. |
| Python throws while handling a run | Python gRPC server | NodeJS fails the assistant run and sends a safe failure event to the frontend. | Catch internal Python exceptions when possible, emit `run_failed` with safe text, then end the stream. |
| Python sends unsupported `event_type` | NodeJS gRPC contract validation | NodeJS rejects the event and fails the run. | Only send event types listed in section 11. Add tests/enum validation in Python. |
| Python sends invalid `payload_json` | NodeJS gRPC payload parsing | NodeJS does not fail the run; it keeps safe metadata that the payload could not be parsed. | Prefer valid JSON object strings. If Python cannot serialize metadata, send `{}` and log the Python-side serialization error. |
| Python sends no final visible event | Python planning/runtime | NodeJS can complete/fail based on stream behavior, but user may not get useful final text. | Always send `final_message`, `follow_up_question`, `permission_denied`, `confirmation_required`, or `run_failed` before ending. |
| Python times out calling an LLM or external service | Python runtime | NodeJS only sees delayed stream or eventual gRPC error. | Emit `thinking`/`analyzing` while working. On timeout, emit `run_failed` or a recoverable `follow_up_question` if the user can retry. |
| Python receives malformed JSON fields from NodeJS | Python request parsing | NodeJS sends JSON via `JSON.stringify`, so this should be rare. | Parse defensively. Default `recent_messages` to `[]`, `pending_task_context` to `null`, and `access` to `{}`. Emit `tool_error` only if it affects the user request. |

### MCP Failure Cases

| Failure case | MCP response | Current NodeJS behavior | Required Python behavior |
|---|---|---|---|
| Missing or invalid MCP token | HTTP 401 | NodeJS rejects the request as an unauthorized service call. | Stop the run with `run_failed`; this is service configuration failure. Do not retry endlessly. |
| Invalid JSON-RPC body | JSON-RPC `error` with invalid request code | NodeJS returns a protocol error. | Treat as Python client bug. Emit `run_failed` with safe text and log request details without secrets. |
| Unknown MCP method | JSON-RPC `error` method not found | MCP server returns `"This assistant tool action is not supported."` | Fix Python client method. Do not ask the user to solve it. |
| Missing tool name | JSON-RPC `error` invalid params | MCP server returns `"Please choose an assistant tool to run."` | Treat as planner/client bug. Emit `run_failed`. |
| Missing `_meta.runId` | JSON-RPC `error` invalid params | MCP server returns `"This assistant action needs an active conversation."` | Treat as Python bug. Emit `run_failed`. |
| Unknown `runId` | JSON-RPC `error` invalid params | MCP server returns `"This assistant conversation could not be found."` | Stop with `run_failed`. Do not continue without a valid run. |
| Tool does not exist | `structuredContent.status = "failed"`, `code = "MCP_TOOL_NOT_FOUND"` | Tool executor returns a structured MCP failure. | Tell the user that this action is not available yet, or choose another listed tool. |
| Tool input fails Zod validation | `structuredContent.status = "requires_input"`, `code = "MCP_INVALID_TOOL_INPUT"` | Tool executor returns field-level validation issues. | Ask a `follow_up_question` for the missing/invalid fields. |
| Tool requires confirmation | `structuredContent.status = "requires_confirmation"` | Tool executor blocks execution until confirmed. | Emit `confirmation_required`. Retry only after user confirms, with `_meta.confirmed = true`. |
| Permission denied by NodeJS business layer | `structuredContent.status = "permission_denied"` | NodeJS returns a structured permission denial. | Emit `permission_denied` with plain user-facing text. Do not attempt another tool to bypass permission. |
| Business operation failure | `structuredContent.status = "failed"` | NodeJS returns a safe failure message and code/details when available. | Emit `tool_error` if recoverable, otherwise `run_failed` or a safe `final_message` explaining it could not be completed. |
| MCP HTTP/network timeout | Python HTTP client exception | NodeJS may not receive anything unless Python reports it over gRPC. | Retry only idempotent read tools with backoff. For writes/destructive tools, do not blindly retry; emit `tool_error` or `run_failed`. |

### Python Decision Table

| MCP status/error | Python should emit |
|---|---|
| `success` with enough data | `tool_result`, then `final_message` or next planning step |
| `success` with multiple possible entities | `follow_up_question` |
| `requires_input` | `follow_up_question` |
| `requires_confirmation` | `confirmation_required`, then `waiting_for_user` |
| `permission_denied` | `permission_denied`, then end the run safely |
| `failed` recoverable read failure | `tool_error`, then ask user to retry or continue with limited info |
| `failed` non-recoverable or write/destructive failure | `run_failed` with safe text |
| JSON-RPC `error` | `run_failed` unless it is clearly recoverable |
| HTTP 401/403 service auth failure | `run_failed` and alert/log for operators |
| HTTP timeout | retry read-only calls once or twice; otherwise `tool_error`/`run_failed` |

### Required Python Guardrails

1. Never perform business writes outside MCP.
2. Never bypass MCP after a permission denial.
3. Never invent IDs for users, agencies, boards, leads, templates, or roles.
4. Never execute destructive/write workflows without confirmation when the classifier or MCP tool says confirmation is required.
5. Never expose service tokens, stack traces, SQL errors, or internal exception text to the user-facing `message`.
6. Always log technical errors on the Python side with `run_id` and `requestId`.
7. Always send a terminal or waiting event before ending the gRPC response stream.

---

## 14. Intent Classifier Contract

The classifier should not execute business logic. It should only classify the user message so the planner can decide whether to answer directly, ask a follow-up question, request confirmation, or call an MCP tool.

### Intent Model

Keep `intent` broad and stable. Use `operation` for the exact backend or business action.

```python
from enum import Enum

from pydantic import BaseModel, Field


class IntentEnum(str, Enum):
    ERP_OPERATION = "ERP_OPERATION"
    SUPPORT_OPERATION = "SUPPORT_OPERATION"
    AUTOMATION_OPERATION = "AUTOMATION_OPERATION"
    GENERAL_QUERY = "GENERAL_QUERY"


class OperationEnum(str, Enum):
    GENERAL_HELP = "GENERAL_HELP"
    LIST_AVAILABLE_TOOLS = "LIST_AVAILABLE_TOOLS"

    AUTH_SEND_OTP = "AUTH_SEND_OTP"
    AUTH_VERIFY_OTP = "AUTH_VERIFY_OTP"
    AUTH_GOOGLE_SIGNIN = "AUTH_GOOGLE_SIGNIN"
    AUTH_GET_SESSION = "AUTH_GET_SESSION"
    AUTH_GET_LAST_LOGIN = "AUTH_GET_LAST_LOGIN"

    AGENCY_CREATE = "AGENCY_CREATE"
    AGENCY_GET_DETAILS = "AGENCY_GET_DETAILS"

    ROLE_LIST = "ROLE_LIST"
    ROLE_CREATE_CUSTOM = "ROLE_CREATE_CUSTOM"
    ROLE_ASSIGN_TO_USER = "ROLE_ASSIGN_TO_USER"
    ROLE_PERMISSION_ENABLE = "ROLE_PERMISSION_ENABLE"
    ROLE_PERMISSION_DISABLE = "ROLE_PERMISSION_DISABLE"

    USER_SEARCH = "USER_SEARCH"
    MEMBER_VIEW = "MEMBER_VIEW"

    BROKER_ASSIGN_ROLE = "BROKER_ASSIGN_ROLE"
    BROKER_KYC_STATUS_CHECK = "BROKER_KYC_STATUS_CHECK"

    LEAD_CREATE = "LEAD_CREATE"
    LEAD_VIEW_ALL = "LEAD_VIEW_ALL"
    LEAD_EDIT = "LEAD_EDIT"
    LEAD_STATUS_MANAGE = "LEAD_STATUS_MANAGE"
    LEAD_CLOSURE_APPROVAL_SUBMIT = "LEAD_CLOSURE_APPROVAL_SUBMIT"
    LEAD_ASSIGN_OR_REMOVE_MEMBER = "LEAD_ASSIGN_OR_REMOVE_MEMBER"

    BOARD_LIST = "BOARD_LIST"
    BOARD_CREATE = "BOARD_CREATE"
    BOARD_RENAME = "BOARD_RENAME"
    BOARD_DELETE = "BOARD_DELETE"
    BOARD_ASSIGN_TEMPLATE = "BOARD_ASSIGN_TEMPLATE"
    BOARD_ADD_MEMBER = "BOARD_ADD_MEMBER"
    BOARD_ASSIGN_BROKER_TO_STAGE = "BOARD_ASSIGN_BROKER_TO_STAGE"
    BOARD_ASSIGN_LEAD = "BOARD_ASSIGN_LEAD"
    BOARD_MOVE_LEAD = "BOARD_MOVE_LEAD"

    TEMPLATE_LIST = "TEMPLATE_LIST"
    TEMPLATE_CREATE = "TEMPLATE_CREATE"
    TEMPLATE_RENAME = "TEMPLATE_RENAME"
    TEMPLATE_DELETE = "TEMPLATE_DELETE"
    TEMPLATE_STAGE_TREE_UPDATE = "TEMPLATE_STAGE_TREE_UPDATE"
    TEMPLATE_STAGE_UPDATE = "TEMPLATE_STAGE_UPDATE"
    TEMPLATE_STAGE_REORDER = "TEMPLATE_STAGE_REORDER"
    TEMPLATE_STAGE_DELETE = "TEMPLATE_STAGE_DELETE"

    INVENTORY_MANAGE = "INVENTORY_MANAGE"
    PROPERTY_LISTING_MANAGE = "PROPERTY_LISTING_MANAGE"
    PROPERTY_LISTING_PUBLISH = "PROPERTY_LISTING_PUBLISH"
    PROPERTY_WEB_LINK_CREATE = "PROPERTY_WEB_LINK_CREATE"
    PROPERTY_ASSIGN_BROKER_OR_CP = "PROPERTY_ASSIGN_BROKER_OR_CP"

    BILLING_ACCESS_STATUS = "BILLING_ACCESS_STATUS"
    BILLING_RUN_LIFECYCLE = "BILLING_RUN_LIFECYCLE"
    BILLING_REACTIVATE_AGENCY = "BILLING_REACTIVATE_AGENCY"

    STORAGE_CREATE_UPLOAD_URL = "STORAGE_CREATE_UPLOAD_URL"
    STORAGE_CREATE_MULTIPART_UPLOAD = "STORAGE_CREATE_MULTIPART_UPLOAD"
    STORAGE_GET_MULTIPART_PART_URL = "STORAGE_GET_MULTIPART_PART_URL"
    STORAGE_COMPLETE_MULTIPART_UPLOAD = "STORAGE_COMPLETE_MULTIPART_UPLOAD"
    STORAGE_ABORT_MULTIPART_UPLOAD = "STORAGE_ABORT_MULTIPART_UPLOAD"

    AUTOMATION_CREATE = "AUTOMATION_CREATE"
    AUTOMATION_UPDATE = "AUTOMATION_UPDATE"
    AUTOMATION_DELETE = "AUTOMATION_DELETE"
    AUTOMATION_RUN = "AUTOMATION_RUN"

    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"


class IntentClassifierResponse(BaseModel):
    intent: IntentEnum = Field(description="Broad classified user intent")
    operation: OperationEnum = Field(description="Specific business operation")
    confidence: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    requires_agency_id: bool
    requires_confirmation: bool
    requires_entity_resolution: bool
```

### Classifier Prompt

```text
You are the IMPACT assistant intent classifier.

Classify the user's latest message into:
1. A broad intent.
2. A specific operation.
3. Risk level.
4. Whether agency context is required.
5. Whether confirmation is required.
6. Whether entity resolution is required.

Do not execute the operation.
Do not call tools.
Do not invent missing IDs.
Do not assume ambiguous names refer to a unique entity.

Broad intent rules:
- ERP_OPERATION: user wants to perform or view business data in IMPACT.
- SUPPORT_OPERATION: user asks why something failed, how to fix access, billing, KYC, upload, or workflow issues.
- AUTOMATION_OPERATION: user wants an automatic workflow, scheduled action, trigger, or recurring process.
- GENERAL_QUERY: user asks general help, explanation, capabilities, or non-business questions.

Operation rules:
- Choose the most specific OperationEnum value.
- Use USER_SEARCH when the user's main goal is finding a user/member.
- Use BROKER_ASSIGN_ROLE when assigning a user to a built-in Broker role.
- Use ROLE_ASSIGN_TO_USER for non-broker role assignment.
- Use ROLE_PERMISSION_ENABLE or ROLE_PERMISSION_DISABLE when changing role permissions.
- Use ROLE_LIST when the user asks to view roles, categories, or permission states.
- Use UNKNOWN only when no listed operation reasonably applies.

Risk rules:
- READ: only reads or explains data.
- WRITE: creates, updates, assigns, moves, uploads, or changes state.
- DESTRUCTIVE: deletes, aborts, removes, disables access, or permanently changes availability.

Confirmation rules:
- Confirmation is required for destructive operations.
- Confirmation is required for assigning roles, changing permissions, moving leads, billing lifecycle actions, and broker assignment.

Entity resolution rules:
- Entity resolution is required when the user references a person, role, board, lead, template, property, or agency by name/text instead of ID.
- Entity resolution is required when multiple entities could match.

Agency rules:
- Agency context is required for roles, permissions, members, boards, templates, billing, leads, inventory, properties, storage, and broker workflows.
- Agency context is not required for auth session, last login, or general help.

Return only valid JSON matching IntentClassifierResponse.
```

### Current Assistant Execution Reality

The backend has many REST/use-case operations, but the assistant can only execute actions that have MCP tools.

Currently registered MCP tools:

| MCP Tool | Operation |
|---|---|
| `assistant.list_tools` | `LIST_AVAILABLE_TOOLS` |
| `users.search_user_details` | `USER_SEARCH` |
| `board.list_boards` | `BOARD_LIST` |
| `agency.list_agency_details` | `AGENCY_GET_DETAILS` |

For other operations, the classifier can still classify the request, but the planner should respond that an MCP tool must be added before the assistant can execute it directly.

### Confirmation Required Operations

Set `requires_confirmation = true` for:

- `ROLE_ASSIGN_TO_USER`
- `BROKER_ASSIGN_ROLE`
- `ROLE_PERMISSION_ENABLE`
- `ROLE_PERMISSION_DISABLE`
- `BOARD_DELETE`
- `BOARD_ASSIGN_TEMPLATE`
- `BOARD_ADD_MEMBER`
- `BOARD_ASSIGN_BROKER_TO_STAGE`
- `BOARD_ASSIGN_LEAD`
- `BOARD_MOVE_LEAD`
- `TEMPLATE_DELETE`
- `TEMPLATE_STAGE_TREE_UPDATE`
- `TEMPLATE_STAGE_UPDATE`
- `TEMPLATE_STAGE_REORDER`
- `TEMPLATE_STAGE_DELETE`
- `LEAD_EDIT`
- `LEAD_STATUS_MANAGE`
- `LEAD_CLOSURE_APPROVAL_SUBMIT`
- `LEAD_ASSIGN_OR_REMOVE_MEMBER`
- `BILLING_RUN_LIFECYCLE`
- `BILLING_REACTIVATE_AGENCY`
- `STORAGE_ABORT_MULTIPART_UPLOAD`

### Entity Resolution Required Operations

Set `requires_entity_resolution = true` when the user references entities by natural language.

Examples:

- "Assign Rahul as broker"
- "Disable edit lead for broker"
- "Delete the sales board"
- "Move John's lead to closed"
- "Rename the default template"

Entity resolution is usually needed for users/members, roles, permissions, boards, leads, templates, stages, agencies, properties, and inventory.

### Planner Handoff

After classification, the planner should:

1. Validate agency context if `requires_agency_id` is true.
2. Resolve entities if `requires_entity_resolution` is true.
3. Ask confirmation if `requires_confirmation` is true.
4. Call MCP only when a matching tool exists.
5. Never mutate data directly from LLM output.
6. Let NodeJS use cases enforce final permissions and business rules.

### Classifier Examples

List roles:

```json
{
  "intent": "ERP_OPERATION",
  "operation": "ROLE_LIST",
  "confidence": 0.96,
  "risk_level": "READ",
  "requires_agency_id": true,
  "requires_confirmation": false,
  "requires_entity_resolution": false
}
```

Assign broker:

```json
{
  "intent": "ERP_OPERATION",
  "operation": "BROKER_ASSIGN_ROLE",
  "confidence": 0.92,
  "risk_level": "WRITE",
  "requires_agency_id": true,
  "requires_confirmation": true,
  "requires_entity_resolution": true
}
```

Troubleshooting:

```json
{
  "intent": "SUPPORT_OPERATION",
  "operation": "BROKER_ASSIGN_ROLE",
  "confidence": 0.9,
  "risk_level": "READ",
  "requires_agency_id": true,
  "requires_confirmation": false,
  "requires_entity_resolution": true
}
```

Automation request:

```json
{
  "intent": "AUTOMATION_OPERATION",
  "operation": "AUTOMATION_CREATE",
  "confidence": 0.91,
  "risk_level": "WRITE",
  "requires_agency_id": true,
  "requires_confirmation": true,
  "requires_entity_resolution": false
}
```

Planner behavior for unsupported automation:

```text
Explain that automation intent is understood, but an automation module/MCP tool is required before this can be executed.
```

---

## 15. Contract Update Rules

When adding or changing an MCP tool:

1. Keep the public tool name stable unless Python is coordinated before deploy.
2. Update the tool input schema exposed through `tools/list`.
3. Keep validation, execution, permissions, and persistence behind the NodeJS MCP boundary.
4. Update this document with the tool input, success data, failure behavior, and permission requirement.
5. Add backward compatibility notes when a response field must remain temporarily for Python.

When changing gRPC fields:

1. Update the proto contract.
2. Update the NodeJS gRPC mapping.
3. Update this document.
4. Coordinate with Python before deploy because gRPC field changes cross service boundaries.
5. Prefer adding optional fields over changing or removing existing fields.
