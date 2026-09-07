import type { LoadTodos } from "./types";

export const loadPreviewTodos: LoadTodos = async () => Array.from({ length: 24 }, (_, index) => ({
  id: `preview-${index}`,
  topic: ["阅读《示例书籍》", "学习开源项目的代码结构", "整理工作空间"][index % 3] + ` · ${index + 1}`,
  priority: index % 3 === 0 ? 1 : 0,
  position: index,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  items: ["第一部分", "第二部分"].map((topic, position) => ({
    id: `preview-${index}-${position}`, todo_id: `preview-${index}`,
    topic, position, completed: position < index % 3,
  })),
  progress: (index % 3) / 2,
  completed: index % 3 === 2,
}));
