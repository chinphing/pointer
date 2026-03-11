"""
ComputerUse: final response tool. Call when the task is complete; ends the agent run (break_loop=True).
"""
from python.helpers.tool import Tool, Response


class ResponseTool(Tool):
    """Return the final message to the user and end the current agent execution."""

    async def execute(self, **kwargs):
        text = self.args.get("text") or self.args.get("message") or ""
        return Response(message=text, break_loop=True)

    async def before_execution(self, **kwargs):
        self.agent.context.log.log(type="response", 
            heading=f"{self.agent.agent_name}: Responding", content=self.args.get("text", ""))
        

    async def after_execution(self, response, **kwargs):
        if self.loop_data and "log_item_response" in self.loop_data.params_temporary:
            log = self.loop_data.params_temporary["log_item_response"]
            log.update(finished=True)
