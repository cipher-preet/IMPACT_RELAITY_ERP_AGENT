# Assistant Intent Classifier

This document defines the intent classification prompt, enum design, response schema, and examples for the IMPACT assistant agent.

The classifier should not execute business logic. It should only classify the user message so the planner can decide whether to answer directly, ask a follow-up question, request confirmation, or call an MCP tool.

## Intent Model

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

## Prompt

Use this prompt for the intent classifier:

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

## Broad Intent Guidance

| Intent | Use When |
|---|---|
| `ERP_OPERATION` | User wants to read or mutate app/business data. |
| `SUPPORT_OPERATION` | User asks why something is not working or asks for troubleshooting. |
| `AUTOMATION_OPERATION` | User wants rules, triggers, scheduled jobs, or automated actions. |
| `GENERAL_QUERY` | User asks conceptual, help, or non-business questions. |

## Current Assistant Execution Reality

The backend has many REST/use-case operations, but the assistant can only execute actions that have MCP tools.

Currently registered MCP tools:

| MCP Tool | Operation |
|---|---|
| `assistant.list_tools` | `LIST_AVAILABLE_TOOLS` |
| `users.search_user_details` | `USER_SEARCH` |
| `board.list_boards` | `BOARD_LIST` |

For other operations, the classifier can still classify the request, but the planner should respond that an MCP tool must be added before the assistant can execute it directly.

## Role And Permission Rules

Default global categories:

- `Employee`
- `Cp`

Default global roles:

- `Employee -> Default`
- `Employee -> Super Admin`
- `Employee -> Broker`
- `Cp -> Broker`

Rules:

- Default categories and roles are system-defined and must not be deleted.
- Custom roles are agency-scoped.
- Role permission grants are agency-scoped.
- Agency owner can enable/disable permissions for roles inside their agency.
- Built-in Broker roles must always keep `kyc.enforce`.
- Assigning a user to a built-in Broker role requires verified broker KYC.

## Confirmation Required Operations

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

## Entity Resolution Required Operations

Set `requires_entity_resolution = true` when the user references entities by natural language.

Examples:

- "Assign Rahul as broker"
- "Disable edit lead for broker"
- "Delete the sales board"
- "Move John's lead to closed"
- "Rename the default template"

Entity resolution is usually needed for:

- Users/members
- Roles
- Permissions
- Boards
- Leads
- Templates
- Stages
- Agencies
- Properties/inventory

## Examples

### List roles

User:

```text
Show me all roles for this agency.
```

Response:

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

### Assign broker

User:

```text
Assign Rahul as broker.
```

Response:

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

### Disable role permission

User:

```text
Disable edit leads permission for broker.
```

Response:

```json
{
  "intent": "ERP_OPERATION",
  "operation": "ROLE_PERMISSION_DISABLE",
  "confidence": 0.94,
  "risk_level": "WRITE",
  "requires_agency_id": true,
  "requires_confirmation": true,
  "requires_entity_resolution": true
}
```

### Try to remove Broker KYC

User:

```text
Remove KYC requirement from broker.
```

Response:

```json
{
  "intent": "ERP_OPERATION",
  "operation": "ROLE_PERMISSION_DISABLE",
  "confidence": 0.95,
  "risk_level": "WRITE",
  "requires_agency_id": true,
  "requires_confirmation": false,
  "requires_entity_resolution": true
}
```

Planner behavior:

```text
Reject safely. Broker KYC is mandatory and cannot be disabled.
```

### Create custom role

User:

```text
Create a Sales Manager role under Employee.
```

Response:

```json
{
  "intent": "ERP_OPERATION",
  "operation": "ROLE_CREATE_CUSTOM",
  "confidence": 0.94,
  "risk_level": "WRITE",
  "requires_agency_id": true,
  "requires_confirmation": false,
  "requires_entity_resolution": true
}
```

### Troubleshooting

User:

```text
Why can't I assign Rahul as broker?
```

Response:

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

### Automation request

User:

```text
Automatically assign new leads to available brokers.
```

Response:

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

Planner behavior:

```text
Explain that automation intent is understood, but an automation module/MCP tool is required before this can be executed.
```

## Planner Handoff

After classification, the planner should:

1. Validate agency context if `requires_agency_id` is true.
2. Resolve entities if `requires_entity_resolution` is true.
3. Ask confirmation if `requires_confirmation` is true.
4. Call MCP only when a matching tool exists.
5. Never mutate data directly from LLM output.
6. Let NodeJS use cases enforce final permissions and business rules.

