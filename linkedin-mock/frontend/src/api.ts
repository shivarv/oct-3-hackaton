import type { Post, SignupInput, User, UserUpdate } from "./types";

/** Thrown when the session is missing or expired (HTTP 401). */
export class AuthError extends Error {}

/** Query key for the logged-in member. Lives under ["users"] so invalidating users refreshes it too. */
export const ME_KEY = ["users", "me"] as const;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // FormData bodies must let the browser set the multipart Content-Type (with boundary).
  const headers =
    init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers };
  const res = await fetch(`/api${path}`, { ...init, headers, credentials: "same-origin" });
  if (!res.ok) {
    const body: unknown = await res.json().catch(() => null);
    const detail = (body as { detail?: unknown } | null)?.detail;
    let message = `Request failed (${res.status})`;
    if (typeof detail === "string") message = detail;
    else if (Array.isArray(detail) && typeof detail[0]?.msg === "string") message = detail[0].msg;
    else if (res.status === 413) message = "File is too large";
    throw res.status === 401 ? new AuthError(message) : new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const send = <T>(method: string, path: string, body?: unknown) =>
  request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

const enc = encodeURIComponent;

export const api = {
  // auth
  me: async (): Promise<User | null> => {
    try {
      return await request<User>("/auth/me");
    } catch (e) {
      if (e instanceof AuthError) return null;
      throw e;
    }
  },
  login: (username: string, password: string) => send<User>("POST", "/auth/login", { username, password }),
  signup: (body: SignupInput) => send<User>("POST", "/auth/signup", body),
  logout: () => send<void>("POST", "/auth/logout"),

  // members
  users: () => request<User[]>("/users"),
  updateMe: (body: UserUpdate) => send<User>("PATCH", "/users/me", body),
  connect: (targetId: string) => send<void>("POST", "/users/me/connections", { target_id: targetId }),
  disconnect: (targetId: string) => send<void>("DELETE", `/users/me/connections/${enc(targetId)}`),

  // resume
  uploadResume: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<User>("/users/me/resume", { method: "PUT", body: form });
  },
  deleteResume: () => send<User>("DELETE", "/users/me/resume"),
  resumeUrl: (userId: string, download = false) =>
    `/api/users/${enc(userId)}/resume${download ? "?download=true" : ""}`,

  // posts
  posts: (authorId?: string) => request<Post[]>(authorId ? `/posts?author_id=${enc(authorId)}` : "/posts"),
  createPost: (content: string) => send<Post>("POST", "/posts", { content }),
  updatePost: (postId: string, content: string) => send<Post>("PATCH", `/posts/${enc(postId)}`, { content }),
  deletePost: (postId: string) => send<void>("DELETE", `/posts/${enc(postId)}`),
  toggleLike: (postId: string) => send<Post>("POST", `/posts/${enc(postId)}/like`),
  addComment: (postId: string, text: string) => send<Post>("POST", `/posts/${enc(postId)}/comments`, { text }),
};
