use std::{
    io::{BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{atomic::{AtomicBool, Ordering}, mpsc, Mutex},
    thread,
    time::{Duration, Instant},
};

use serde_json::{json, Value};

const RESPONSE_TIMEOUT: Duration = Duration::from_secs(30);
const MAX_RESPONSE_BYTES: u64 = 16 * 1024 * 1024;

// Only the Rust application owns this path and process. Neither is provided by the UI.
pub struct TodoBackend {
    database_path: PathBuf,
    process: Mutex<Option<Sidecar>>,
    stopping: AtomicBool,
}

impl TodoBackend {
    pub fn new(database_path: PathBuf) -> Self {
        Self {
            database_path,
            process: Mutex::new(None),
            stopping: AtomicBool::new(false),
        }
    }

    pub fn list(&self) -> Result<Value, String> {
        self.call("todos.list", json!({}))
    }

    pub fn settings_get(&self) -> Result<Value, String> {
        self.call("settings.get", json!({}))
    }

    pub fn settings_test(&self) -> Result<Value, String> {
        self.call("user.settings.test", json!({}))
    }

    pub fn settings_save(&self, settings: Value) -> Result<Value, String> {
        self.call("user.settings.save", json!({"settings": settings}))
    }

    pub fn sessions_list(&self) -> Result<Value, String> {
        self.call("sessions.list", json!({}))
    }

    pub fn sessions_get(&self, session_id: String) -> Result<Value, String> {
        self.call("sessions.get", json!({"session_id": session_id}))
    }

    pub fn sessions_create(&self, label: String) -> Result<Value, String> {
        self.call("user.sessions.create", json!({"label": label}))
    }

    pub fn sessions_delete(&self, session_id: String) -> Result<Value, String> {
        self.call("user.sessions.delete", json!({"session_id": session_id}))
    }

    pub fn sessions_retry(&self, session_id: String) -> Result<Value, String> {
        self.call("user.sessions.retry", json!({"session_id": session_id}))
    }

    pub fn sessions_send(&self, session_id: String, message: Value) -> Result<Value, String> {
        self.call("user.sessions.send", json!({"session_id": session_id, "message": message}))
    }

    pub fn create(&self, todo: Value) -> Result<Value, String> {
        self.call("user.todos.create", json!({"todo": todo}))
    }

    pub fn update(&self, todo_id: String, todo: Value) -> Result<Value, String> {
        self.call("user.todos.update", json!({"todo_id": todo_id, "todo": todo}))
    }

    pub fn set_item_completed(&self, todo_id: String, item_id: String, completed: bool) -> Result<Value, String> {
        self.call("user.todos.set_item_completed", json!({"todo_id": todo_id, "item_id": item_id, "completed": completed}))
    }

    pub fn move_todo(&self, todo_id: String, target_id: String) -> Result<Value, String> {
        self.call("user.todos.move", json!({"todo_id": todo_id, "target_id": target_id}))
    }

    pub fn delete(&self, todo_id: String) -> Result<Value, String> {
        self.call("user.todos.delete", json!({"todo_id": todo_id}))
    }

    fn call(&self, method: &str, params: Value) -> Result<Value, String> {
        let mut slot = self.process.lock().map_err(|_| "Todo 服务状态不可用")?;
        if self.stopping.load(Ordering::Acquire) {
            return Err("Todo 服务正在关闭".into());
        }
        if slot.is_none() {
            *slot = Some(Sidecar::start(&self.database_path)?);
        }
        let result = slot
            .as_mut()
            .expect("sidecar initialized")
            .request(method, params, &self.stopping);
        // A failed/timed-out connection must not be reused: its next line may be stale.
        if result.is_err() {
            slot.take();
        }
        result
    }

    pub fn shutdown(&self) {
        self.stopping.store(true, Ordering::Release);
        if let Ok(mut slot) = self.process.lock() {
            slot.take();
        }
    }
}

fn sidecar_command() -> Result<Command, String> {
    #[cfg(debug_assertions)]
    {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("project root");
        let python = if cfg!(windows) {
            root.join(".venv/Scripts/python.exe")
        } else {
            root.join(".venv/bin/python")
        };
        if !python.is_file() {
            return Err("未找到项目 .venv 中的 Python，请先完成开发环境安装".into());
        }
        let mut command = Command::new(python);
        command.args(["-u", "-m", "wisetodo.main"]);
        // Development builds only; release builds never consult this variable.
        if let Some(path) = std::env::var_os("WISETODO_DEV_MODEL_CONFIG") {
            if !Path::new(&path).is_absolute() {
                return Err("开发模型配置必须使用绝对路径".into());
            }
            command.arg("--dev-model-config").arg(path);
        }
        command.current_dir(root);
        Ok(command)
    }
    #[cfg(not(debug_assertions))]
    {
        let executable = std::env::current_exe().map_err(|_| "无法定位 Sidecar")?;
        let name = if cfg!(windows) {
            "wisetodo-sidecar.exe"
        } else {
            "wisetodo-sidecar"
        };
        let path = executable.parent().ok_or("无法定位 Sidecar")?.join(name);
        if !path.is_file() {
            return Err("安装包缺少 Python Sidecar；请使用完整安装包或开发环境运行".into());
        }
        Ok(Command::new(path))
    }
}

struct Sidecar {
    child: Child,
    input: ChildStdin,
    responses: mpsc::Receiver<Result<String, String>>,
    next_id: u64,
}

impl Sidecar {
    fn start(database_path: &Path) -> Result<Self, String> {
        let mut command = sidecar_command()?;
        command.arg("--database").arg(database_path);
        Self::spawn(command)
    }

    fn spawn(mut command: Command) -> Result<Self, String> {
        command.env("PYTHONIOENCODING", "utf-8");
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }
        let mut child = command.spawn().map_err(|_| "无法启动 Python Todo 服务")?;
        let input = child.stdin.take().expect("piped stdin");
        let output = child.stdout.take().expect("piped stdout");
        let (sender, responses) = mpsc::sync_channel(1);
        thread::spawn(move || {
            let mut reader = BufReader::new(output);
            loop {
                let mut bytes = Vec::new();
                let read = reader
                    .by_ref()
                    .take(MAX_RESPONSE_BYTES + 1)
                    .read_until(b'\n', &mut bytes);
                let response = match read {
                    Ok(0) => Err("Python Todo 服务已退出，请重试".into()),
                    Ok(_) if bytes.len() as u64 > MAX_RESPONSE_BYTES => {
                        Err("Todo 响应超过大小限制".into())
                    }
                    Ok(_) => String::from_utf8(bytes)
                        .map_err(|_| "Todo 服务返回了无效 UTF-8".into()),
                    Err(_) => Err("无法读取 Python Todo 服务响应".into()),
                };
                let failed = response.is_err();
                if sender.send(response).is_err() || failed {
                    break;
                }
            }
        });
        Ok(Self {
            child,
            input,
            responses,
            next_id: 0,
        })
    }

    fn request(&mut self, method: &str, params: Value, stopping: &AtomicBool) -> Result<Value, String> {
        self.next_id += 1;
        let request_id = format!("todo-{}", self.next_id);
        let request = json!({
            "type": "request", "requestId": request_id, "method": method, "params": params
        });
        writeln!(self.input, "{request}")
            .and_then(|_| self.input.flush())
            .map_err(|_| "无法发送 Todo 读取请求，请重试")?;
        let deadline = Instant::now() + RESPONSE_TIMEOUT;
        loop {
            if stopping.load(Ordering::Acquire) {
                return Err("Todo 服务正在关闭".into());
            }
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                return Err("Todo 服务响应超时，请重试".into());
            }
            match self.responses.recv_timeout(remaining.min(Duration::from_millis(100))) {
                Ok(response) => return decode_response(&response?, &request_id),
                Err(mpsc::RecvTimeoutError::Timeout) => continue,
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    return Err("Todo 服务已断开，请重试".into());
                }
            }
        }
    }
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn decode_response(line: &str, request_id: &str) -> Result<Value, String> {
    let response: Value = serde_json::from_str(line).map_err(|_| "Todo 服务返回了无效 JSON")?;
    if response["type"] != "response" || response["requestId"] != request_id {
        return Err("Todo 服务响应与请求不匹配".into());
    }
    if let Some(error) = response.get("error") {
        return Err(error["user_message"]
            .as_str()
            .unwrap_or("读取 Todo 失败，请重试")
            .to_owned());
    }
    let result = response.get("result").ok_or("Todo 服务响应缺少结果")?;
    if !(result["todos"].is_array() || result["todo"].is_object() || result["deleted"].is_boolean()
        || result["sessions"].is_array() || result["session"].is_object()
        || result.get("settings").is_some_and(|value| value.is_null() || value.is_object())
        || result["connection_test"].is_string()) {
        return Err("Todo 服务响应缺少结果数据".into());
    }
    Ok(result.clone())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decodes_success_and_errors_and_rejects_mismatched_ids() {
        assert_eq!(decode_response(r#"{"type":"response","requestId":"1","result":{"settings":null}}"#, "1").unwrap(), json!({"settings":null}));
        assert!(decode_response(r#"{"type":"response","requestId":"1","result":{"settings":[]}}"#, "1").is_err());
        assert_eq!(decode_response(r#"{"type":"response","requestId":"1","result":{"todos":[]}}"#, "1").unwrap(), json!({"todos":[]}));
        assert!(decode_response(r#"{"type":"response","requestId":"2","result":{"todos":[]}}"#, "1").is_err());
        assert_eq!(decode_response(r#"{"type":"response","requestId":"1","error":{"user_message":"读取失败"}}"#, "1").unwrap_err(), "读取失败");
        assert!(decode_response("not json", "1").is_err());
        assert!(decode_response(r#"{"type":"response","requestId":"1","result":{}}"#, "1").is_err());
    }

    // Uses the project .venv just as `tauri dev` does, without opening a desktop window.
    #[cfg(debug_assertions)]
    #[test]
    fn real_python_list_reuses_process_and_recovers_after_exit() {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
        let directory = std::env::temp_dir().join(format!("wisetodo-bridge-{}-{unique}", std::process::id()));
        std::fs::create_dir(&directory).unwrap();
        struct Cleanup(PathBuf);
        impl Drop for Cleanup {
            fn drop(&mut self) {
                for name in ["wisetodo.db", "wisetodo.db-wal", "wisetodo.db-shm", "wisetodo.db-journal"] {
                    let _ = std::fs::remove_file(self.0.join(name));
                }
                let _ = std::fs::remove_dir(&self.0);
            }
        }
        let _cleanup = Cleanup(directory.clone());
        let database = directory.join("wisetodo.db");
        let backend = TodoBackend::new(database.clone());
        assert_eq!(backend.list().unwrap(), json!({"todos": []}));
        let first_pid = backend.process.lock().unwrap().as_ref().unwrap().child.id();

        // Populate only this test's database through the real Todo Service.
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        let python = root.join(if cfg!(windows) { ".venv/Scripts/python.exe" } else { ".venv/bin/python" });
        let seed = r#"
import sys
from sqlalchemy import URL
from wisetodo.database import create_database
from wisetodo.todos import TodoInput, TodoService
database = create_database(URL.create('sqlite', database=sys.argv[1]).render_as_string(hide_password=False))
try:
    service = TodoService(database.sessions)
    service.create(TodoInput(topic='普通任务', items=['第一章', '第二章']))
    service.create(TodoInput(topic='优先任务', priority=1, items=['配置环境', '阅读入口']))
finally:
    database.dispose()
"#;
        let status = Command::new(python).args(["-c", seed]).arg(&database)
            .current_dir(root).status().unwrap();
        assert!(status.success());
        let listed = backend.list().unwrap();
        assert_eq!(backend.sessions_list().unwrap(), json!({"sessions":[]}));
        assert_eq!(backend.settings_get().unwrap(), json!({"settings":null}));
        let settings = backend.settings_save(json!({"base_url":"http://localhost:8000/v1","model":"local"})).unwrap();
        assert_eq!(settings["settings"]["has_api_key"], false);
        assert_eq!(backend.settings_get().unwrap(), settings);
        let history = backend.sessions_create("学习项目".to_owned()).unwrap();
        let session_id = history["session"]["id"].as_str().unwrap().to_owned();
        assert_eq!(backend.sessions_get(session_id.clone()).unwrap(), history);
        let message = json!({"message_id":"7c2d7815-6e80-43af-a36a-ec58526ab877", "content":"你好\n消息保存测试", "urls":["https://example.com/book"]});
        let saved = backend.sessions_send(session_id.clone(), message.clone()).unwrap();
        assert_eq!(saved["session"]["messages"][0]["content"], "你好\n消息保存测试");
        assert_eq!(saved["session"]["messages"][0]["attachments"], json!(["https://example.com/book"]));
        assert_eq!(backend.sessions_send(session_id.clone(), message).unwrap(), saved);
        assert_eq!(backend.sessions_get(session_id.clone()).unwrap(), saved);
        assert_eq!(backend.sessions_delete(session_id).unwrap(), json!({"deleted":true}));
        assert_eq!(backend.sessions_list().unwrap(), json!({"sessions":[]}));
        assert_eq!(listed["todos"].as_array().unwrap().len(), 2);
        assert_eq!(listed["todos"][0]["topic"], "优先任务");
        assert_eq!(listed["todos"][0]["progress"], 0.0);
        assert_eq!(listed["todos"][0]["items"][0]["topic"], "配置环境");
        assert_eq!(first_pid, backend.process.lock().unwrap().as_ref().unwrap().child.id());

        let created = backend.create(json!({"topic":"写入测试", "items":["子项一", "子项二"]})).unwrap();
        let id = created["todo"]["id"].as_str().unwrap().to_owned();
        let reordered = backend.move_todo(id.clone(), id.clone()).unwrap();
        assert_eq!(reordered, backend.list().unwrap());
        assert_eq!(reordered["todos"].as_array().unwrap().len(), 3);
        let item_id = created["todo"]["items"][0]["id"].as_str().unwrap().to_owned();
        let checked = backend.set_item_completed(id.clone(), item_id.clone(), true).unwrap();
        assert_eq!(checked["todo"]["progress"], json!(0.5));
        assert_eq!(checked["todo"]["items"][0]["completed"], json!(true));
        let unchecked = backend.set_item_completed(id.clone(), item_id, false).unwrap();
        assert_eq!(unchecked["todo"]["progress"], json!(0.0));
        let updated = backend.update(id.clone(), json!({
            "topic":"已修改", "priority":1,
            "items":[
                {"id":created["todo"]["items"][0]["id"], "topic":"子项一"},
                {"id":created["todo"]["items"][1]["id"], "topic":"改名子项"}
            ]
        })).unwrap();
        assert_eq!(updated["todo"]["topic"], "已修改");
        assert_eq!(updated["todo"]["items"][0]["id"], created["todo"]["items"][0]["id"]);
        assert_ne!(updated["todo"]["items"][1]["id"], created["todo"]["items"][1]["id"]);
        assert_eq!(backend.delete(id).unwrap(), json!({"deleted":true}));
        assert_eq!(backend.list().unwrap(), listed);

        // Simulate a crash. The failed connection is discarded and retry starts a fresh process.
        {
            let mut slot = backend.process.lock().unwrap();
            let child = &mut slot.as_mut().unwrap().child;
            child.kill().unwrap();
            child.wait().unwrap();
        }
        assert!(backend.list().is_err());
        assert_eq!(backend.list().unwrap(), listed);
        backend.shutdown();
        assert!(backend.process.lock().unwrap().is_none());
        assert!(backend.list().is_err());
        let backend = TodoBackend::new(database);
        assert_eq!(backend.list().unwrap(), listed);
        backend.shutdown();
    }

    #[test]
    #[cfg(debug_assertions)]
    fn shutdown_interrupts_an_unresponsive_child() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        let python = root.join(if cfg!(windows) { ".venv/Scripts/python.exe" } else { ".venv/bin/python" });
        let mut command = Command::new(python);
        command.args(["-c", "import time; time.sleep(60)"]);
        let backend = std::sync::Arc::new(TodoBackend::new(PathBuf::new()));
        *backend.process.lock().unwrap() = Some(Sidecar::spawn(command).unwrap());
        let worker_backend = backend.clone();
        let worker = thread::spawn(move || worker_backend.list());
        let deadline = Instant::now() + Duration::from_secs(5);
        while backend.process.try_lock().is_ok() && Instant::now() < deadline {
            thread::yield_now();
        }
        let start = Instant::now();
        backend.shutdown();
        assert!(worker.join().unwrap().is_err());
        assert!(start.elapsed() < Duration::from_secs(2));
        assert!(backend.process.lock().unwrap().is_none());
    }
}
