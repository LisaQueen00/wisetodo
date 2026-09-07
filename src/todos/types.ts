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

export interface TodoDraft {
  topic: string;
  priority: 0 | 1;
  items: { id?: string; topic: string }[];
}

export interface TodoMutations {
  setItemCompleted: (todoId: string, itemId: string, completed: boolean) => Promise<Todo>;
  create: (draft: TodoDraft) => Promise<Todo>;
  update: (todoId: string, draft: TodoDraft) => Promise<Todo>;
  delete: (todoId: string) => Promise<void>;
}

export interface TodoActions {
  mutations: TodoMutations;
  onSaved: (todo: Todo) => void;
  onDeleted: (todoId: string) => void;
}
