"""Stop the current agent run for a chat. Keeps context and history so the user can send a new message and continue the conversation."""

from python.helpers.api import ApiHandler, Request, Output
from python.helpers import persist_chat
from python.helpers.task_scheduler import TaskScheduler


class ChatStop(ApiHandler):
    async def process(self, input: dict, request: Request) -> Output:
        ctxid = input.get("context", "").strip() or input.get("ctxid", "").strip()
        if not ctxid:
            return {"error": "context or ctxid is required", "ok": False}

        context = self.use_context(ctxid)
        context.kill_process()
        TaskScheduler.get().cancel_tasks_by_context(ctxid, terminate_thread=True)
        persist_chat.save_tmp_chat(context)

        from python.helpers.state_monitor_integration import mark_dirty_all
        mark_dirty_all(reason="api.chat_stop.ChatStop")

        return {
            "message": "Run stopped. You can send a new message to continue.",
            "ok": True,
        }
