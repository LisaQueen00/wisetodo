use std::io::Write;

fn validate(content: &str) -> Result<(), String> {
    if content.len() > 65536 { return Err("主题文件不能超过 64 KiB。".into()); }
    let value: serde_json::Value = serde_json::from_str(content).map_err(|_| "主题 JSON 无效。")?;
    if !matches!(value.get("schemaVersion").and_then(|v| v.as_u64()), Some(1 | 2)) {
        return Err("主题版本无效。".into());
    }
    Ok(())
}

fn write_theme(path: &std::path::Path, content: &str) -> Result<(), String> {
    let mut file = std::fs::File::create(path).map_err(|_| "无法创建主题文件，请检查目录权限或文件占用。")?;
    file.write_all(content.as_bytes()).and_then(|_| file.sync_all())
        .map_err(|_| "主题文件写入失败，请检查磁盘空间和权限。".into())
}

#[tauri::command]
pub async fn theme_export(window: tauri::WebviewWindow, content: String) -> Result<Option<String>, String> {
    validate(&content)?;
    let selected = rfd::AsyncFileDialog::new().set_parent(&window)
        .set_title("导出主题 JSON").set_file_name("wisetodo-theme.json")
        .add_filter("JSON", &["json"]).save_file().await;
    let Some(selected) = selected else { return Ok(None); };
    let path = selected.path().to_path_buf();
    tauri::async_runtime::spawn_blocking(move || {
        write_theme(&path, &content)?;
        Ok(Some(path.to_string_lossy().into_owned()))
    }).await.map_err(|_| "主题导出任务异常结束。".to_owned())?
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_invalid_payload() {
        assert!(validate("bad").is_err());
        assert!(validate("{}").is_err());
        assert!(validate(&" ".repeat(65537)).is_err());
    }
    #[test]
    fn writes_readable_json_and_reports_failure() {
        let dir = std::env::temp_dir().join(format!("wisetodo-theme-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("theme.json");
        let content = "{\n  \"schemaVersion\": 1,\n  \"name\": \"主题\"\n}\n";
        validate(content).unwrap();
        write_theme(&path, content).unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), content);
        assert!(write_theme(&dir, content).is_err());
        std::fs::remove_file(path).unwrap();
        std::fs::remove_dir(dir).unwrap();
    }
}
