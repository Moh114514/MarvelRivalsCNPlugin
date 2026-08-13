from __future__ import annotations

from .models import CardButton, InteractiveCard


def build_capability_test_card() -> InteractiveCard:
    return InteractiveCard(
        markdown=(
            "# 漫威争锋查询\n"
            "这是 QQ 官方机器人富消息能力测试。\n\n"
            "如果你能看到本段 Markdown 和下方两个按钮，说明原生富消息已启用。"
        ),
        rows=[[ 
            CardButton("查询战绩", "command", "/战绩 1287101468", "blue"),
            CardButton(
                "打开项目",
                "url",
                "https://github.com/Moh114514/MarvelRivalsCNPlugin",
            ),
        ]],
    )
