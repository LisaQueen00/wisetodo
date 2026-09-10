"""Allowlisted UI explanations; never expose upstream response text."""


def tool_failure_message(reason: str) -> str:
    if reason in {"unknown_tool", "handler_unavailable"}:
        return "所需工具未启用或未注册，请检查工具配置；这不表示用户必须粘贴资料。"
    if reason == "rate_limited":
        return "资料服务限流，请稍后重试；本次未提交 Todo。"
    if reason in {"web_network_failed", "github_unavailable", "tool_timeout"}:
        return "资料服务连接失败或超时，请检查网络后重试。"
    if reason == "web_blocked":
        return "网页地址不符合公开网络访问规则，已阻止访问。"
    if reason in {"web_unsupported", "web_too_large", "web_redirect_limit", "web_unavailable"}:
        return "网页无法读取：可能需要登录、格式不支持、内容过大或重定向异常。"
    return "工具执行失败，请检查工具配置或服务；本次未提交 Todo。"
