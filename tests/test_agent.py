from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.tools import tool
from pydantic import Field
from rosa import RobotSystemPrompts

from rosa_turbopi.agent import RosbridgeROSA


class FakeToolModel(FakeListChatModel):
    bound_names: list[str] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.bound_names = [tool.name for tool in tools]
        return self


@tool
def fake_status() -> str:
    """Return a fake connection state."""
    return "connected"


def test_rosa_uses_only_explicit_tools_without_ros_installation():
    llm = FakeToolModel(responses=["接続状態を確認できます"])
    agent = RosbridgeROSA(
        ros_version=2,
        llm=llm,
        tools=[fake_status],
        prompts=RobotSystemPrompts(embodiment_and_persona="Read-only robot"),
        streaming=False,
    )
    assert llm.bound_names == ["fake_status"]
    assert agent.invoke("何ができますか") == "接続状態を確認できます"


def test_multiple_tools_need_an_iteration_for_final_answer():
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage

    class ScriptedModel(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    calls = [
        AIMessage(content="", tool_calls=[{"name": "fake_status", "args": {}, "id": str(i)}])
        for i in range(5)
    ]

    def make_agent(limit):
        return RosbridgeROSA(
            ros_version=2,
            llm=ScriptedModel(responses=[*calls, AIMessage(content="全操作の完了を確認しました")]),
            tools=[fake_status],
            streaming=False,
            max_iterations=limit,
        )

    assert "max iterations" in make_agent(5).invoke("複数操作")
    assert make_agent(15).invoke("複数操作") == "全操作の完了を確認しました"
