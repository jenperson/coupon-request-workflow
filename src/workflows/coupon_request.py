"""Coupon code request workflow — triggered by a Tally form webhook.

Receives a Tally form submission payload, creates a row in the Notion
coupon-request database, and sends a Slack notification with a link to
the new page.
"""

from __future__ import annotations

import json
import os
from typing import Any

import mistralai.workflows as workflows
from mistralai.workflows import Depends
from mistralai.workflows.plugins.mistralai.connectors import (
    ToolCallClient,
    connector,
    uses_connectors,
)
from pydantic import BaseModel


notion_connector = connector("notion")
slack_connector = connector("slack")


# Tally field labels → Notion column names
FIELD_MAP = {
    "What's your first name?": "First name",
    "What's your last name?": "Last name",
    "What's the email you use with your Mistral account?": "Email",
    "What is the name of the event/activation you are requesting credits for?": "Event name",
    "Provide a link to the event, if available": "Event link",
    "When is the event? If there is no specific date, when do you need the credits by?": "Event date",
    "How many users will need access to the code?": "Number of users",
    "What is the monetary value of credits?": "Credit amount",
    "Is there a specific redemption deadline?": "Redemption deadline",
    "Is there a credit validity deadline?": "Credit expiration",
}

DATE_COLUMNS = {"Event date", "Redemption deadline", "Credit expiration"}
NUMBER_COLUMNS = {"Number of users", "Credit amount"}


class TallyField(BaseModel):
    key: str
    label: str
    type: str
    value: Any = None


class TallyData(BaseModel):
    responseId: str | None = None
    submissionId: str | None = None
    formId: str | None = None
    formName: str | None = None
    fields: list[TallyField] = []


class TallyWebhookPayload(BaseModel):
    eventId: str | None = None
    eventType: str | None = None
    createdAt: str | None = None
    data: TallyData


def _unwrap(response: Any) -> dict | list:
    """Decode the MCP-style content[0].text JSON from a connector response."""
    if isinstance(response, dict):
        content = response.get("content") or []
    else:
        content = getattr(response, "content", None) or []
    if not content:
        return {}
    first = content[0]
    text = first.get("text") if isinstance(first, dict) else getattr(first, "text", None)
    if text is None:
        return {}
    return json.loads(text)


def _build_notion_properties(fields: list[TallyField]) -> dict[str, Any]:
    """Map Tally form fields to Notion database properties."""
    props: dict[str, Any] = {}

    for field in fields:
        col = FIELD_MAP.get(field.label)
        if col is None or field.value is None or field.value == "":
            continue

        if col in DATE_COLUMNS:
            props[f"date:{col}:start"] = str(field.value)
            props[f"date:{col}:is_datetime"] = 0
        elif col in NUMBER_COLUMNS:
            try:
                props[col] = float(field.value) if "." in str(field.value) else int(field.value)
            except (ValueError, TypeError):
                props[col] = str(field.value)
        else:
            props[col] = str(field.value)

    return props


@workflows.activity()
async def create_notion_page(
    properties: dict[str, Any],
    notion: ToolCallClient = Depends(notion_connector),
) -> dict:
    """Create a page in the coupon-request Notion database.

    Returns the parsed response containing the new page URL.
    """
    database_id = os.environ.get("NOTION_DATABASE_ID", "")
    if not database_id:
        raise ValueError("NOTION_DATABASE_ID environment variable is not set")

    response = await notion.call_tool(
        tool_name="notion-create-pages",
        arguments={
            "parent": {
                "database_id": database_id,
            },
            "pages": [
                {
                    "properties": properties,
                }
            ],
            "allow_async": False,
        },
    )
    return _unwrap(response)


@workflows.activity()
async def send_slack_notification(
    first_name: str,
    last_name: str,
    event_name: str,
    page_url: str,
    slack: ToolCallClient = Depends(slack_connector),
) -> dict:
    """Post a notification to Slack about the new coupon request."""
    channel_id = os.environ.get("SLACK_CHANNEL_ID", "")
    if not channel_id:
        raise ValueError("SLACK_CHANNEL_ID environment variable is not set")

    message = (
        f"*New coupon code request*\n"
        f"*Requester:* {first_name} {last_name}\n"
        f"*Event:* {event_name}\n"
        f"*Notion page:* {page_url}"
    )

    response = await slack.call_tool(
        tool_name="slack_send_message",
        arguments={
            "channel_id": channel_id,
            "message": message,
        },
    )
    return _unwrap(response)


@workflows.workflow.define(
    name="coupon-code-request",
    workflow_display_name="Coupon Code Request",
    workflow_description=(
        "Receives a Tally form submission, creates a Notion database entry "
        "for the coupon code request, and notifies Slack."
    ),
)
@uses_connectors(notion_connector, slack_connector)
class CouponCodeRequestWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, payload: TallyWebhookPayload) -> str:
        properties = _build_notion_properties(payload.data.fields)

        notion_result = await create_notion_page(properties)

        page_url = ""
        if isinstance(notion_result, dict):
            page_url = notion_result.get("url", "")
            if not page_url:
                pages = notion_result.get("pages", [])
                if pages and isinstance(pages[0], dict):
                    page_url = pages[0].get("url", "")

        first_name = properties.get("First name", "")
        last_name = properties.get("Last name", "")
        event_name = properties.get("Event name", "")

        await send_slack_notification(first_name, last_name, event_name, page_url)

        return f"Coupon request created: {page_url}"
