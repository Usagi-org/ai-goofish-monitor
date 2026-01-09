// Based on the Pydantic model in the backend

export interface Task {
  id: number;
  task_name: string;
  enabled: boolean;
  keyword: string;
  description: string;
  max_pages: number;
  personal_only: boolean;
  min_price: string | null;
  max_price: string | null;
  cron: string | null;
  ai_prompt_base_file: string;
  ai_prompt_criteria_file: string;
  account_state_file?: string | null;
  is_running: boolean;
}

// For PATCH requests, all fields are optional
export type TaskUpdate = Partial<Omit<Task, 'id'>>;

// For AI-driven task creation
export interface TaskGenerateRequest {
  task_name: string;
  keyword: string;
  description: string;
  personal_only?: boolean;
  min_price?: string | null;
  max_price?: string | null;
  max_pages?: number;
  cron?: string | null;
  account_state_file?: string | null;
}
