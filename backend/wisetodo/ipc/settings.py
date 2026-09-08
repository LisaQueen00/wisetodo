from typing import Any

from wisetodo.errors import ErrorCode, WiseTodoError
from wisetodo.ipc.messages import IpcRequest
from wisetodo.model.connection import check_connection
from wisetodo.settings import SettingsService, SettingsUpdate, SettingsView
from wisetodo.settings.storage import SettingsStorageError

METHODS = frozenset({"settings.get", "user.settings.save", "user.settings.test"})


class SettingsRequestError(Exception):
    def __init__(self, error: WiseTodoError) -> None:
        self.error = error
        super().__init__(error.message)


async def dispatch_settings(request: IpcRequest, service: SettingsService) -> dict[str, Any]:
    writing = request.method == "user.settings.save"
    result: SettingsView | None
    try:
        if request.method == "user.settings.test":
            if request.params:
                raise ValueError("Unexpected parameters")
            return {"connection_test": await check_connection(service)}
        if writing:
            if set(request.params) != {"settings"}:
                raise ValueError("Unexpected parameters")
            result = service.save(SettingsUpdate.model_validate(request.params["settings"]))
        elif request.method == "settings.get":
            if request.params:
                raise ValueError("Unexpected parameters")
            result = service.get()
        else:
            raise ValueError("Unsupported settings method")
        return {"settings": None if result is None else result.model_dump(mode="json")}
    except ValueError:
        raise SettingsRequestError(
            WiseTodoError(
                code=ErrorCode.SETTINGS_VALIDATION_FAILED,
                message="Invalid model settings",
                user_message="请检查模型地址、名称与密钥操作；更换地址时须明确替换或清除已有密钥。",
            )
        ) from None
    except SettingsStorageError:
        raise SettingsRequestError(
            WiseTodoError(
                code=ErrorCode.SETTINGS_SAVE_FAILED if writing else ErrorCode.SETTINGS_READ_FAILED,
                message="Cannot save model settings" if writing else "Cannot read model settings",
                user_message=(
                    "设置未能保存，请检查本地存储和系统凭据库后重试。"
                    if writing
                    else "无法读取设置或密钥，请检查本地存储和系统凭据库。"
                ),
                retryable=True,
            )
        ) from None
