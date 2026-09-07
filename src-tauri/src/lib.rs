mod sidecar;

use std::sync::Arc;
use tauri::Manager;

#[tauri::command]
async fn todos_list(
    backend: tauri::State<'_, Arc<sidecar::TodoBackend>>,
) -> Result<serde_json::Value, String> {
    let backend = Arc::clone(backend.inner());
    tauri::async_runtime::spawn_blocking(move || backend.list())
        .await
        .map_err(|_| "Todo 读取任务异常终止".to_owned())?
}

#[tauri::command]
async fn todos_create(
    backend: tauri::State<'_, Arc<sidecar::TodoBackend>>,
    todo: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let backend = Arc::clone(backend.inner());
    tauri::async_runtime::spawn_blocking(move || backend.create(todo))
        .await.map_err(|_| "Todo 保存任务异常终止".to_owned())?
}

#[tauri::command]
async fn todos_update(
    backend: tauri::State<'_, Arc<sidecar::TodoBackend>>,
    todo_id: String,
    todo: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let backend = Arc::clone(backend.inner());
    tauri::async_runtime::spawn_blocking(move || backend.update(todo_id, todo))
        .await.map_err(|_| "Todo 保存任务异常终止".to_owned())?
}

#[tauri::command]
async fn todos_delete(
    backend: tauri::State<'_, Arc<sidecar::TodoBackend>>,
    todo_id: String,
) -> Result<serde_json::Value, String> {
    let backend = Arc::clone(backend.inner());
    tauri::async_runtime::spawn_blocking(move || backend.delete(todo_id))
        .await.map_err(|_| "Todo 删除任务异常终止".to_owned())?
}

#[tauri::command]
fn health() -> &'static str {
    "ok"
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = tauri::Manager::get_webview_window(app, "main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_autostart::Builder::new().build())
        .setup(|app| {
            let database_path = app.path().app_data_dir()?.join("wisetodo.db");
            app.manage(Arc::new(sidecar::TodoBackend::new(database_path)));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![health, todos_list, todos_create, todos_update, todos_delete])
        .build(tauri::generate_context!())
        .expect("error while building WiseTodo")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                app.state::<Arc<sidecar::TodoBackend>>().shutdown();
            }
        });
}
