export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type ApiError = {
  status: number;
  detail: string;
};

export type AnalysisIssue = {
  page: number;
  issue_type: string;
  severity: string;
  description: string;
  suggestion: string;
};

export type AnalysisResult = {
  summary: string;
  issues: AnalysisIssue[];
  overall_assessment: string;
  ready_for_mentor: boolean;
};

export type AnalysisTask = {
  id: number;
  status: string;
  result: AnalysisResult | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
};

export type DraftResponse = {
  thesis_id: number;
  version_id: number;
  task: AnalysisTask;
};

export type Notification = {
  id: number;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
};

export type UserRead = {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

async function parseError(response: Response): Promise<ApiError> {
  let detail = response.statusText;
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") {
      detail = data.detail;
    } else if (typeof data?.message === "string") {
      detail = data.message;
    }
  } catch {
    const text = await response.text();
    if (text) {
      detail = text;
    }
  }

  return { status: response.status, detail };
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function apiForm<T>(
  path: string,
  form: FormData
): Promise<T> {
  return apiFetch<T>(path, { method: "POST", body: form });
}
