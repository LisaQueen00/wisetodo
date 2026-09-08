use std::{collections::HashMap, io::Write, process::ChildStdin,
    sync::{Arc, Mutex, mpsc, atomic::{AtomicBool, AtomicU64, Ordering}},
    time::{Duration, Instant}};
use serde_json::{json, Value};

pub type EventSink = Arc<dyn Fn(Value) + Send + Sync>;
type Pending = HashMap<String, mpsc::Sender<Result<String, String>>>;

pub struct Transport {
    input: Mutex<ChildStdin>,
    pending: Mutex<Pending>,
    next_id: AtomicU64,
    pub alive: AtomicBool,
    events: Option<EventSink>,
}

impl Transport {
    pub fn new(input: ChildStdin, events: Option<EventSink>) -> Self {
        Self { input: Mutex::new(input), pending: Mutex::new(HashMap::new()),
            next_id: AtomicU64::new(0), alive: AtomicBool::new(true), events }
    }

    pub fn fail(&self) {
        self.alive.store(false, Ordering::Release);
        if let Ok(mut pending) = self.pending.lock() {
            for (_, sender) in pending.drain() { let _ = sender.send(Err("后端已断开，请重试".into())); }
        }
    }

    pub fn deliver(&self, line: String) -> bool {
        let Ok(value) = serde_json::from_str::<Value>(&line) else { return false; };
        let Some(id) = value["requestId"].as_str() else { return false; };
        if value["type"] == "event" {
            if self.pending.lock().map(|p| p.contains_key(id)).unwrap_or(false)
                && matches!(value["event"].as_str(), Some("run.started" | "run.finished"))
                && value["session_id"].is_string() && value["run_id"].is_string() {
                if let Some(sink) = &self.events {
                    sink(json!({"requestId":id, "event":value["event"],
                        "session_id":value["session_id"], "run_id":value["run_id"]}));
                }
            }
            return true;
        }
        if value["type"] != "response" { return false; }
        if let Ok(mut pending) = self.pending.lock() {
            if let Some(sender) = pending.remove(id) { let _ = sender.send(Ok(line)); }
        }
        true // Late responses for a timed-out request are discarded by ID.
    }

    fn send(&self, value: Value) -> Result<(), String> {
        let mut input = self.input.lock().map_err(|_| "后端写入不可用")?;
        writeln!(input, "{value}").and_then(|_| input.flush()).map_err(|_| "无法发送后端请求".into())
    }

    pub fn request(&self, method: &str, params: Value, stopping: &AtomicBool) -> Result<String, String> {
        let id = format!("request-{}", self.next_id.fetch_add(1, Ordering::Relaxed));
        let (sender, receiver) = mpsc::channel();
        {
            let mut pending = self.pending.lock().map_err(|_| "后端状态不可用")?;
            if !self.alive.load(Ordering::Acquire) { return Err("后端已断开，请重试".into()); }
            pending.insert(id.clone(), sender);
        }
        let result = (|| {
            if let Err(error) = self.send(json!({"type":"request", "requestId":id, "method":method,"params":params})) {
                self.fail();
                return Err(error);
            }
            let start = Instant::now();
            loop {
                if stopping.load(Ordering::Acquire) { return Err("后端正在关闭".into()); }
                // A retry is a long model run, not a 30-second CRUD request.
                if method != "user.sessions.retry" && start.elapsed() >= Duration::from_secs(30) {
                    let _ = self.send(json!({"type":"cancel","requestId":id}));
                    return Err("后端响应超时，请重新读取状态".into());
                }
                match receiver.recv_timeout(Duration::from_millis(100)) {
                    Ok(value) => return value,
                    Err(mpsc::RecvTimeoutError::Timeout) => continue,
                    Err(_) => return Err("后端已断开，请重试".into()),
                }
            }
        })();
        if let Ok(mut pending) = self.pending.lock() { pending.remove(&id); }
        result
    }
}
