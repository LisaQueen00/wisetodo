// Matches the Python Todo Service serialization.
export interface TodoItem {
  id: string;
  todo_id: string;
  topic: string;
  completed: boolean;
  position: number;
}
export interface Todo {
  id: string;
  topic: string;
  priority: 0 | 1;
  position: number;
  created_at: string;
  updated_at: string;
  items: TodoItem[];
  progress: number;
  completed: boolean;
}
export type LoadTodos = () => Promise<Todo[]>;
