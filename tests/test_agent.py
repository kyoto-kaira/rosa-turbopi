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
