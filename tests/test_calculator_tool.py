from report_building_agent.tools import ToolLogger, create_calculator_tool


def test_calculator_returns_number_string(tmp_path):
    logger = ToolLogger(logs_dir=str(tmp_path))
    tool = create_calculator_tool(logger)

    assert tool.invoke({"expression": "2 + 3"}) == "5"
    assert tool.invoke({"expression": "10 / 4"}) == "2.5"

