import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ME_KEY } from "../api";
import type { SignupInput, User } from "../types";
import { EyeIcon, LockIcon, UserIcon } from "../components/Icons";

type Mode = "login" | "signup";

const USERNAME_PATTERN = /^[a-z0-9_.]{3,30}$/;
const DEMO_USERS = ["ada", "grace", "linus", "margaret"];

function PasswordInput(props: {
  value: string;
  onChange: (v: string) => void;
  autoComplete: string;
  placeholder?: string;
  invalid?: boolean;
}) {
  const [shown, setShown] = useState(false);
  return (
    <div className="input-affix">
      <input
        type={shown ? "text" : "password"}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        autoComplete={props.autoComplete}
        placeholder={props.placeholder}
        maxLength={128}
        aria-invalid={props.invalid}
        required
      />
      <button
        type="button"
        className="icon-btn"
        onClick={() => setShown((s) => !s)}
        aria-label={shown ? "Hide password" : "Show password"}
        title={shown ? "Hide password" : "Show password"}
      >
        <EyeIcon size={18} />
      </button>
    </div>
  );
}

function Field({ label, error, hint, children }: { label: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {error ? <span className="field-error">{error}</span> : hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

function LoginForm({ onDone }: { onDone: (u: User) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const login = useMutation({ mutationFn: () => api.login(username.trim(), password), onSuccess: onDone });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (username.trim() && password) login.mutate();
  };

  return (
    <form className="auth-form" onSubmit={submit}>
      <Field label="Username">
        <div className="input-affix">
          <span className="affix-icon">
            <UserIcon size={18} />
          </span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="e.g. ada"
            maxLength={30}
            required
            autoFocus
          />
        </div>
      </Field>
      <Field label="Password">
        <PasswordInput value={password} onChange={setPassword} autoComplete="current-password" />
      </Field>
      {login.isError && <p className="form-alert">{login.error.message}</p>}
      <button className="btn primary block lg" disabled={!username.trim() || !password || login.isPending}>
        {login.isPending ? "Signing in…" : "Sign in"}
      </button>

      <div className="demo-box">
        <span className="muted xs">Demo accounts · password <code>test</code></span>
        <div className="demo-chips">
          {DEMO_USERS.map((u) => (
            <button
              key={u}
              type="button"
              className="demo-chip"
              onClick={() => {
                setUsername(u);
                setPassword("test");
                login.reset();
              }}
            >
              {u}
            </button>
          ))}
        </div>
      </div>
    </form>
  );
}

function SignupForm({ onDone }: { onDone: (u: User) => void }) {
  const [form, setForm] = useState<SignupInput>({ name: "", username: "", password: "", headline: "", location: "" });
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);
  const signup = useMutation({
    mutationFn: () => api.signup({ ...form, name: form.name.trim(), username: form.username.trim().toLowerCase() }),
    onSuccess: onDone,
  });

  const set = (key: keyof SignupInput) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const username = form.username.trim().toLowerCase();
  const errors = {
    name: !form.name.trim() ? "Enter your name." : undefined,
    username: !USERNAME_PATTERN.test(username) ? "3–30 characters: letters, numbers, dots, underscores." : undefined,
    password: form.password.length < 8 ? "Use at least 8 characters." : undefined,
    confirm: confirm !== form.password ? "Passwords don't match." : undefined,
  };
  const valid = !Object.values(errors).some(Boolean);
  const show = (key: keyof typeof errors) => (touched ? errors[key] : undefined);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (valid) signup.mutate();
  };

  return (
    <form className="auth-form" onSubmit={submit} noValidate>
      <Field label="Full name" error={show("name")}>
        <input value={form.name} onChange={(e) => set("name")(e.target.value)} autoComplete="name" maxLength={80} autoFocus />
      </Field>
      <Field label="Username" error={show("username")} hint="You'll use this to sign in.">
        <div className="input-affix">
          <span className="affix-icon">@</span>
          <input
            value={form.username}
            onChange={(e) => set("username")(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={30}
            aria-invalid={!!show("username")}
          />
        </div>
      </Field>
      <div className="grid-2 tight">
        <Field label="Password" error={show("password")}>
          <PasswordInput value={form.password} onChange={set("password")} autoComplete="new-password" invalid={!!show("password")} />
        </Field>
        <Field label="Confirm password" error={show("confirm")}>
          <PasswordInput value={confirm} onChange={setConfirm} autoComplete="new-password" invalid={!!show("confirm")} />
        </Field>
      </div>
      <Field label="Headline (optional)">
        <input value={form.headline} onChange={(e) => set("headline")(e.target.value)} maxLength={160} placeholder="e.g. Software Engineer at Acme" />
      </Field>
      <Field label="Location (optional)">
        <input value={form.location} onChange={(e) => set("location")(e.target.value)} maxLength={160} placeholder="e.g. Boston, MA" />
      </Field>
      {signup.isError && <p className="form-alert">{signup.error.message}</p>}
      <button className="btn primary block lg" disabled={signup.isPending}>
        {signup.isPending ? "Creating account…" : "Agree & join"}
      </button>
    </form>
  );
}

export function AuthPage() {
  const [mode, setMode] = useState<Mode>("login");
  const queryClient = useQueryClient();
  const onDone = (user: User) => queryClient.setQueryData(ME_KEY, user);

  return (
    <div className="auth-page">
      <section className="auth-hero">
        <div className="auth-brand">
          <span className="logo static">in</span>
          <span className="brand">LinkedOut</span>
        </div>
        <h1>
          Welcome to your <span className="gradient-text">professional community</span>
        </h1>
        <p className="muted">Share what you're working on, grow your network and showcase your resume.</p>
        <ul className="auth-points">
          <li>Post updates, like and comment</li>
          <li>Connect with people you know</li>
          <li>Upload your resume as a PDF</li>
        </ul>
      </section>

      <section className="card auth-card">
        <div className="auth-tabs" role="tablist">
          <button role="tab" aria-selected={mode === "login"} className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>
            Sign in
          </button>
          <button role="tab" aria-selected={mode === "signup"} className={mode === "signup" ? "active" : ""} onClick={() => setMode("signup")}>
            Join now
          </button>
        </div>
        <div className="auth-card-body">
          <h2>{mode === "login" ? "Sign in" : "Create your account"}</h2>
          <p className="muted small">
            {mode === "login" ? "Stay updated on your professional world." : "Make the most of your professional life."}
          </p>
          {mode === "login" ? <LoginForm onDone={onDone} /> : <SignupForm onDone={onDone} />}
          <p className="auth-switch small">
            {mode === "login" ? "New to LinkedOut? " : "Already on LinkedOut? "}
            <button className="link accent" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
              {mode === "login" ? "Join now" : "Sign in"}
            </button>
          </p>
          <p className="muted xs secure-note">
            <LockIcon size={12} /> Passwords are stored hashed, never in plain text.
          </p>
        </div>
      </section>
    </div>
  );
}
