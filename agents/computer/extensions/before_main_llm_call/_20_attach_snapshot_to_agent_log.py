"""
Attach the current turn's screenshot to this turn's agent log item.
The snapshot path is set by the screen inject (message_loop_prompts_after) in
loop_data.params_temporary['computer_snapshot_annotated']. We attach it to the
log item created by _10_log_for_stream for this turn, so the snapshot is not
shown on the previous round.
"""
from __future__ import annotations

from agent import LoopData
from python.helpers.extension import Extension


class AttachSnapshotToAgentLog(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs) -> None:
        if getattr(self.agent.config, "profile", "") != "computer":
            return
        snapshot_path = loop_data.params_temporary.pop("computer_snapshot_annotated", None)
        if not snapshot_path:
            return
        log_item = loop_data.params_temporary.get("log_item_generating")
        if log_item is None:
            return
        existing_kvps = dict(log_item.kvps) if getattr(log_item, "kvps", None) else {}
        existing_kvps["snapshot"] = snapshot_path
        log_item.update(kvps=existing_kvps)
