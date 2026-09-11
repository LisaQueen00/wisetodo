"""Reviewed built-in local definitions, without user data or external services."""

from wisetodo.tools.config import ToolConfig


def builtin_tools() -> tuple[ToolConfig, ...]:
    definitions = (
        (
            "read_url",
            "读取公开静态网页正文、标题和链接；不支持登录或动态渲染页面。",
            "url",
            {"type": "string", "maxLength": 2048},
        ),
        (
            "parse_pdf",
            "读取本次附件 PDF 的目录和有限正文；仅接受附件 file_ref，不接受路径。",
            "file_ref",
            {"type": "string"},
        ),
        (
            "read_github_project",
            "读取公开 GitHub 仓库 README、根目录及有限贡献资料，不执行代码。",
            "url",
            {"type": "string", "maxLength": 512},
        ),
        (
            "search_projects",
            "按用户偏好搜索最多三个公开 GitHub 项目候选，供选择一个。",
            "query",
            {"type": "string", "minLength": 1, "maxLength": 200},
        ),
    )
    return tuple(
        ToolConfig.model_validate(
            {
                "name": name,
                "description": description
                + (
                    " 可选 paths 按需读取最多四个仓库相对文件/目录；ref 指定分支。"
                    if name == "read_github_project"
                    else ""
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        argument: schema,
                        **(
                            {
                                "paths": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 4,
                                    "items": {"type": "string", "maxLength": 300},
                                },
                            "ref": {"type": "string", "minLength": 1, "maxLength": 200},
                            "offset": {"type": "integer", "minimum": 0, "maximum": 1048576},
                            }
                            if name == "read_github_project"
                            else {}
                        ),
                    },
                    "required": [argument],
                    "additionalProperties": False,
                },
                "transport": {"type": "local", "handler": name},
            }
        )
        for name, description, argument, schema in definitions
    )
