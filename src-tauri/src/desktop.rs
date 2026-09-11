use std::{fs, path::PathBuf, sync::atomic::{AtomicBool, Ordering}};
use tauri::{AppHandle, Manager};
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_window_state::{AppHandleExt, StateFlags};

pub const WINDOW_FLAGS: StateFlags = StateFlags::SIZE.union(StateFlags::POSITION);

pub struct DesktopState {
    marker: PathBuf,
    pin_file: PathBuf,
    abnormal: AtomicBool,
    tray: AtomicBool,
}

#[derive(serde::Serialize)]
pub struct Status {
    pinned: bool,
    autostart: Option<bool>,
    abnormal_exit: bool,
    tray_available: bool,
}

pub fn reveal(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn initial_size(width: f64, height: f64) -> (f64, f64) {
    (400.0_f64.min(width), (height * 0.6).max(520.0).min(height))
}

fn mark_running(path: &std::path::Path) -> std::io::Result<bool> {
    let previous = path.exists();
    fs::write(path, b"running")?;
    Ok(previous)
}

pub fn setup(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let dir = app.path().app_data_dir()?;
    fs::create_dir_all(&dir)?;
    let marker = dir.join("desktop-running.marker");
    let abnormal = mark_running(&marker)?;
    let pin_file = dir.join("desktop-pin.json");
    let pinned = fs::read_to_string(&pin_file).ok()
        .and_then(|text| serde_json::from_str::<bool>(&text).ok()).unwrap_or(true);
    app.manage(DesktopState { marker, pin_file, abnormal: AtomicBool::new(abnormal), tray: AtomicBool::new(false) });
    let window = app.get_webview_window("main").ok_or("Missing main window")?;
    window.set_always_on_top(pinned)?;
    let layout_marker = dir.join("overlay-layout-v1.marker");
    if !layout_marker.exists() || !app.path().app_config_dir()?.join(tauri_plugin_window_state::DEFAULT_FILENAME).exists() {
        if let Some(monitor) = window.current_monitor()? {
            let area = monitor.work_area();
            let scale = monitor.scale_factor();
            let (width, height) = initial_size(area.size.width as f64 / scale, area.size.height as f64 / scale);
            window.set_size(tauri::LogicalSize::new(width, height))?;
            window.center()?;
            fs::write(&layout_marker, b"1")?;
        }
    }
    use tauri::{menu::{Menu, MenuItem}, tray::TrayIconBuilder};
    let show = MenuItem::with_id(app, "show", "显示 WiseTodo", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出 WiseTodo（停止后台任务）", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &quit])?;
    // Code-native small icon; no external bitmap or runtime file required.
    let mut rgba = vec![0; 32 * 32 * 4];
    for y in 3..29 { for x in 3..29 {
        let i = (y * 32 + x) * 4;
        rgba[i..i+4].copy_from_slice(&[154, 115, 232, 255]);
        if (x >= 8 && x <= 12 && y >= 13 && y <= 18) || (x >= 12 && x <= 24 && y == 30-x) {
            rgba[i..i+4].copy_from_slice(&[255, 255, 255, 255]);
        }
    }}
    let tray = TrayIconBuilder::with_id("main-tray")
        .icon(tauri::image::Image::new_owned(rgba, 32, 32))
        .tooltip("WiseTodo · 关闭窗口后仍在后台运行")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => reveal(app),
            "quit" => app.exit(0),
            _ => {}
        }).build(app);
    app.state::<DesktopState>().tray.store(tray.is_ok(), Ordering::Release);
    // Never hide an abnormal-start warning or make a tray-less app inaccessible.
    if !(std::env::args().any(|arg| arg == "--background") && tray.is_ok() && !abnormal) {
        window.show()?;
    }
    Ok(())
}

#[tauri::command]
pub fn desktop_status(app: AppHandle) -> Result<Status, String> {
    let state = app.state::<DesktopState>();
    let window = app.get_webview_window("main").ok_or("窗口不可用")?;
    Ok(Status {
        pinned: window.is_always_on_top().map_err(|_| "无法读取置顶状态")?,
        autostart: app.autolaunch().is_enabled().ok(),
        abnormal_exit: state.abnormal.load(Ordering::Acquire),
        tray_available: state.tray.load(Ordering::Acquire),
    })
}

#[tauri::command]
pub fn desktop_pin(app: AppHandle, pinned: bool) -> Result<(), String> {
    let window = app.get_webview_window("main").ok_or("窗口不可用")?;
    let previous = window.is_always_on_top().map_err(|_| "无法读取置顶状态")?;
    window.set_always_on_top(pinned).map_err(|_| "无法修改置顶状态")?;
    if fs::write(&app.state::<DesktopState>().pin_file, if pinned { "true" } else { "false" }).is_err() {
        let _ = window.set_always_on_top(previous);
        return Err("无法保存置顶设置".into());
    }
    Ok(())
}

#[tauri::command]
pub fn desktop_autostart(app: AppHandle, enabled: bool) -> Result<(), String> {
    let launcher = app.autolaunch();
    (if enabled { launcher.enable() } else { launcher.disable() })
        .map_err(|_| "无法修改开机启动，请检查系统权限".into())
}

#[tauri::command]
pub fn desktop_acknowledge(app: AppHandle) {
    app.state::<DesktopState>().abnormal.store(false, Ordering::Release);
}

#[tauri::command]
pub fn desktop_restart(app: AppHandle) { app.restart(); }

pub fn window_event(window: &tauri::Window, event: &tauri::WindowEvent) {
    if window.label() != "main" { return; }
    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
        let app = window.app_handle();
        if app.try_state::<DesktopState>().is_some_and(|state| state.tray.load(Ordering::Acquire)) {
            // Save before hiding; visibility/minimized state is deliberately not restored.
            let _ = app.save_window_state(WINDOW_FLAGS);
            if window.hide().is_ok() { api.prevent_close(); }
        }
    }
}

pub fn clean_exit(app: &AppHandle) {
    let _ = app.save_window_state(WINDOW_FLAGS);
    if let Some(state) = app.try_state::<DesktopState>() {
        let _ = fs::remove_file(&state.marker);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn windows_transparency_preserves_base_window_options() {
        let base: serde_json::Value = serde_json::from_str(include_str!("../tauri.conf.json")).unwrap();
        let mut windows: serde_json::Value = serde_json::from_str(include_str!("../tauri.windows.conf.json")).unwrap();
        let window = windows["app"]["windows"][0].as_object_mut().unwrap();
        assert_eq!(window.remove("transparent"), Some(serde_json::json!(true)));
        assert_eq!(window.remove("backgroundColor"), Some(serde_json::json!([0, 0, 0, 0])));
        assert_eq!(windows["app"]["windows"], base["app"]["windows"]);
    }
    #[test]
    fn sensible_screen_defaults() {
        assert_eq!(initial_size(1920.0, 1080.0), (400.0, 648.0));
        assert_eq!(initial_size(3840.0, 2160.0), (400.0, 1296.0));
        assert_eq!(initial_size(1280.0, 720.0), (400.0, 520.0));
    }
    #[test]
    fn never_restore_hidden_or_minimized_state() {
        assert!(!WINDOW_FLAGS.contains(StateFlags::VISIBLE));
        assert!(!WINDOW_FLAGS.contains(StateFlags::MAXIMIZED));
    }
    #[test]
    fn marker_distinguishes_clean_and_interrupted_runs() {
        let path = std::env::temp_dir().join(format!("wisetodo-marker-{}-{}", std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
        assert!(!mark_running(&path).unwrap());
        assert!(mark_running(&path).unwrap());
        fs::remove_file(&path).unwrap();
        assert!(!mark_running(&path).unwrap());
        fs::remove_file(path).unwrap();
    }
}
