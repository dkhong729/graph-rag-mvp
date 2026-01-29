const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type AuthContext = {
  token?: string;
};

const buildHeaders = (auth?: AuthContext) => {
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };
  if (auth?.token) headers.Authorization = `Bearer ${auth.token}`;
  return headers;
};

const fetchJson = async <T>(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<T> => {
  const response = await fetch(input, init);
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      const text = await response.text();
      if (text) detail = text;
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
};

export const registerUser = (
  email: string,
  password: string,
  passwordConfirm?: string,
  displayName?: string,
  username?: string
) =>
  fetchJson<{
    user: { user_id: string; display_name: string };
    token: string;
    verification_required?: boolean;
    verification_token?: string;
  }>(`${apiBaseUrl}/api/auth/register`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({
      email,
      password,
      password_confirm: passwordConfirm,
      display_name: displayName,
      username
    }),
    cache: "no-store"
  });

export const loginUser = (email: string, password: string) =>
  fetchJson<{
    user: { user_id: string; display_name: string };
    token: string;
  }>(`${apiBaseUrl}/api/auth/login`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ email, password }),
    cache: "no-store"
  });

export const requestEmailVerification = (email: string) =>
  fetchJson<{ status: string; verification_token?: string }>(
    `${apiBaseUrl}/api/auth/verify/request`,
    {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify({ email }),
      cache: "no-store"
    }
  );

export const verifyEmailToken = (token: string) =>
  fetchJson<{ status: string }>(`${apiBaseUrl}/api/auth/verify`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ token }),
    cache: "no-store"
  });

export const requestPasswordReset = (email: string) =>
  fetchJson<{ status: string; reset_token?: string }>(
    `${apiBaseUrl}/api/auth/password/request`,
    {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify({ email }),
      cache: "no-store"
    }
  );

export const resetPassword = (
  token: string,
  newPassword: string,
  newPasswordConfirm?: string
) =>
  fetchJson<{ status: string }>(`${apiBaseUrl}/api/auth/password/reset`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({
      token,
      new_password: newPassword,
      new_password_confirm: newPasswordConfirm
    }),
    cache: "no-store"
  });

export const listDocuments = (auth?: AuthContext) =>
  fetchJson<{ documents: any[] }>(`${apiBaseUrl}/api/documents`, {
    headers: buildHeaders(auth),
    cache: "no-store"
  });

export const deleteDocuments = (auth: AuthContext, documentIds: string[]) =>
  fetchJson<{ status: string; count: number }>(`${apiBaseUrl}/api/documents/delete`, {
    method: "POST",
    headers: buildHeaders(auth),
    body: JSON.stringify({ document_ids: documentIds }),
    cache: "no-store"
  });

export const createDocument = async (
  auth: AuthContext,
  payload: FormData
) => {
  const response = await fetch(`${apiBaseUrl}/api/documents`, {
    method: "POST",
    headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : undefined,
    body: payload
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as { document_id: string };
};

export const getDocument = (auth: AuthContext, documentId: string) =>
  fetchJson<any>(`${apiBaseUrl}/api/documents/${documentId}`, {
    headers: buildHeaders(auth),
    cache: "no-store"
  });

export const getDocumentIntelligence = (auth: AuthContext, documentId: string) =>
  fetchJson<{ document_id: string; current: any; previous: any }>(
    `${apiBaseUrl}/api/documents/${documentId}/intelligence`,
    { headers: buildHeaders(auth), cache: "no-store" }
  );

export const streamDocumentPage = async (
  auth: AuthContext,
  documentId: string,
  style: string,
  language: string,
  pageLimit: number
) => {
  const form = new FormData();
  form.append("style", style);
  form.append("language", language);
  form.append("page_limit", String(pageLimit));
  const response = await fetch(
    `${apiBaseUrl}/api/documents/${documentId}/generate`,
    {
      method: "POST",
      headers: auth?.token
        ? {
            Authorization: `Bearer ${auth.token}`,
            Accept: "text/event-stream"
          }
        : { Accept: "text/event-stream" },
      body: form
    }
  );
  if (!response.ok || !response.body) {
    throw new Error("Streaming failed");
  }
  return response;
};

export const renderDocumentPage = async (
  auth: AuthContext,
  documentId: string,
  style: string,
  language: string,
  pageLimit: number
) => {
  const form = new FormData();
  form.append("style", style);
  form.append("language", language);
  form.append("page_limit", String(pageLimit));
  const response = await fetch(
    `${apiBaseUrl}/api/documents/${documentId}/render`,
    {
      method: "POST",
      headers: auth?.token
        ? {
            Authorization: `Bearer ${auth.token}`,
            Accept: "text/event-stream"
          }
        : { Accept: "text/event-stream" },
      body: form
    }
  );
  if (!response.ok || !response.body) {
    throw new Error("Streaming failed");
  }
  return response;
};

export const finalizeDocumentPage = async (
  auth: AuthContext,
  documentId: string,
  html: string,
  style: string,
  language: string,
  pageLimit: number
) => {
  const form = new FormData();
  form.append("html", html);
  form.append("style", style);
  form.append("language", language);
  form.append("page_limit", String(pageLimit));
  const response = await fetch(
    `${apiBaseUrl}/api/documents/${documentId}/finalize`,
    {
      method: "POST",
      headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : undefined,
      body: form
    }
  );
  if (!response.ok) {
    throw new Error("Finalize failed");
  }
  return (await response.json()) as { page_id: string };
};

export const listDocumentPages = (auth: AuthContext, documentId: string) =>
  fetchJson<{ pages: any[] }>(
    `${apiBaseUrl}/api/documents/${documentId}/pages`,
    { headers: buildHeaders(auth), cache: "no-store" }
  );

export const createMeeting = async (
  auth: AuthContext,
  payload: FormData
) => {
  const response = await fetch(`${apiBaseUrl}/api/meetings`, {
    method: "POST",
    headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : undefined,
    body: payload
  });
  if (!response.ok) {
    throw new Error("Meeting upload failed");
  }
  return (await response.json()) as { meeting_id: string };
};

export const listMeetings = (auth: AuthContext) =>
  fetchJson<{ meetings: any[] }>(`${apiBaseUrl}/api/meetings`, {
    headers: buildHeaders(auth),
    cache: "no-store"
  });

export const getMeeting = (auth: AuthContext, meetingId: string) =>
  fetchJson<any>(`${apiBaseUrl}/api/meetings/${meetingId}`, {
    headers: buildHeaders(auth),
    cache: "no-store"
  });

export const listMeetingPages = (auth: AuthContext, meetingId: string) =>
  fetchJson<{ pages: any[] }>(`${apiBaseUrl}/api/meetings/${meetingId}/pages`, {
    headers: buildHeaders(auth),
    cache: "no-store"
  });

export const updateMeetingTranscript = async (
  auth: AuthContext,
  meetingId: string,
  transcript: string
) => {
  const form = new FormData();
  form.append("transcript", transcript);
  const response = await fetch(
    `${apiBaseUrl}/api/meetings/${meetingId}/transcript`,
    {
      method: "POST",
      headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : undefined,
      body: form
    }
  );
  if (!response.ok) {
    throw new Error("Transcript update failed");
  }
  return (await response.json()) as { status: string };
};

export const transcribeMeetingAudio = async (
  auth: AuthContext,
  meetingId: string,
  file: File,
  language?: string
) => {
  const form = new FormData();
  form.append("file", file);
  if (language) {
    form.append("language", language);
  }
  const response = await fetch(
    `${apiBaseUrl}/api/meetings/${meetingId}/audio`,
    {
      method: "POST",
      headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : undefined,
      body: form
    }
  );
  if (!response.ok) {
    throw new Error("Audio transcription failed");
  }
  return (await response.json()) as { transcript: string };
};

export const streamMeetingPage = async (
  auth: AuthContext,
  meetingId: string,
  style: string,
  language: string,
  pageLimit: number
) => {
  const form = new FormData();
  form.append("style", style);
  form.append("language", language);
  form.append("page_limit", String(pageLimit));
  const response = await fetch(
    `${apiBaseUrl}/api/meetings/${meetingId}/generate`,
    {
      method: "POST",
      headers: auth?.token
        ? {
            Authorization: `Bearer ${auth.token}`,
            Accept: "text/event-stream"
          }
        : { Accept: "text/event-stream" },
      body: form
    }
  );
  if (!response.ok || !response.body) {
    throw new Error("Streaming failed");
  }
  return response;
};

export const renderMeetingPage = async (
  auth: AuthContext,
  meetingId: string,
  style: string,
  language: string,
  pageLimit: number
) => {
  const form = new FormData();
  form.append("style", style);
  form.append("language", language);
  form.append("page_limit", String(pageLimit));
  const response = await fetch(
    `${apiBaseUrl}/api/meetings/${meetingId}/render`,
    {
      method: "POST",
      headers: auth?.token
        ? {
            Authorization: `Bearer ${auth.token}`,
            Accept: "text/event-stream"
          }
        : { Accept: "text/event-stream" },
      body: form
    }
  );
  if (!response.ok || !response.body) {
    throw new Error("Streaming failed");
  }
  return response;
};

export const finalizeMeetingPage = async (
  auth: AuthContext,
  meetingId: string,
  html: string,
  style: string,
  language: string,
  pageLimit: number
) => {
  const form = new FormData();
  form.append("html", html);
  form.append("style", style);
  form.append("language", language);
  form.append("page_limit", String(pageLimit));
  const response = await fetch(
    `${apiBaseUrl}/api/meetings/${meetingId}/finalize`,
    {
      method: "POST",
      headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : undefined,
      body: form
    }
  );
  if (!response.ok) {
    throw new Error("Finalize failed");
  }
  return (await response.json()) as { page_id: string };
};

export const getPage = (auth: AuthContext, pageId: string) =>
  fetchJson<any>(`${apiBaseUrl}/api/pages/${pageId}`, {
    headers: buildHeaders(auth),
    cache: "no-store"
  });

export const updatePage = (auth: AuthContext, pageId: string, html: string) =>
  fetchJson<{ status: string }>(`${apiBaseUrl}/api/pages/${pageId}`, {
    method: "PUT",
    headers: buildHeaders(auth),
    body: JSON.stringify({ html }),
    cache: "no-store"
  });

export const deletePage = (auth: AuthContext, pageId: string) =>
  fetchJson<{ status: string }>(`${apiBaseUrl}/api/pages/${pageId}`, {
    method: "DELETE",
    headers: buildHeaders(auth),
    cache: "no-store"
  });

export const askDecisionRag = (
  auth: AuthContext,
  payload: {
    query: string;
    owner_type: string;
    owner_id: string;
    target?: string;
    language?: "zh" | "en";
  }
) =>
  fetchJson<{ answer: string }>(`${apiBaseUrl}/api/rag/ask`, {
    method: "POST",
    headers: buildHeaders(auth),
    body: JSON.stringify(payload),
    cache: "no-store"
  });
