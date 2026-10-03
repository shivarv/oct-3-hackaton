import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { GENDER_LABELS, type Gender, type User, type UserUpdate } from "../types";
import { Avatar, bannerStyle } from "../components/Avatar";
import { CheckIcon, FileIcon, LockIcon, UserIcon } from "../components/Icons";
import { ResumeUpload } from "../components/ResumeUpload";

// These mirror the backend's validation rules.
const PHONE_PATTERN = /^(\+?[0-9 ()-]{7,20})?$/;
const USERNAME_PATTERN = /^[a-z0-9_.]{3,30}$/;

interface FormState {
  name: string;
  username: string;
  headline: string;
  location: string;
  about: string;
  phone: string;
  age: string;
  gender: Gender | "";
  date_of_birth: string;
}

function fromUser(u: User): FormState {
  return {
    name: u.name,
    username: u.username ?? "",
    headline: u.headline,
    location: u.location,
    about: u.about,
    phone: u.phone,
    age: u.age === null ? "" : String(u.age),
    gender: u.gender ?? "",
    date_of_birth: u.date_of_birth ?? "",
  };
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function ageFrom(dob: string): number | null {
  const birth = new Date(`${dob}T00:00:00`);
  if (Number.isNaN(birth.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const beforeBirthday =
    now.getMonth() < birth.getMonth() || (now.getMonth() === birth.getMonth() && now.getDate() < birth.getDate());
  if (beforeBirthday) age -= 1;
  return age;
}

function validate(f: FormState): Partial<Record<keyof FormState, string>> {
  const errors: Partial<Record<keyof FormState, string>> = {};
  if (!f.name.trim()) errors.name = "Name is required.";
  const username = f.username.trim().toLowerCase();
  if (!username) errors.username = "Username is required to sign in.";
  else if (!USERNAME_PATTERN.test(username)) {
    errors.username = "3–30 characters: letters, numbers, dots and underscores.";
  }
  if (!PHONE_PATTERN.test(f.phone.trim())) {
    errors.phone = "Use 7–20 digits; spaces, dashes, () and a leading + are allowed.";
  }
  if (f.age) {
    const n = Number(f.age);
    if (!Number.isInteger(n) || n < 13 || n > 120) errors.age = "Age must be a whole number from 13 to 120.";
  }
  if (f.date_of_birth && (f.date_of_birth > todayIso() || f.date_of_birth < "1900-01-01")) {
    errors.date_of_birth = "Enter a date between 1900 and today.";
  }
  return errors;
}

function toPayload(f: FormState): UserUpdate {
  return {
    name: f.name.trim(),
    username: f.username.trim().toLowerCase(),
    headline: f.headline.trim(),
    location: f.location.trim(),
    about: f.about.trim(),
    phone: f.phone.trim(),
    age: f.age ? Number(f.age) : null,
    gender: f.gender || null,
    date_of_birth: f.date_of_birth || null,
  };
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

function Section({ icon, title, subtitle, children }: { icon: ReactNode; title: string; subtitle: string; children: ReactNode }) {
  return (
    <section className="card settings-section">
      <header className="section-head">
        <span className="section-icon">{icon}</span>
        <div>
          <h2>{title}</h2>
          <p className="muted small">{subtitle}</p>
        </div>
      </header>
      {children}
    </section>
  );
}

export function SettingsPage({ me }: { me: User }) {
  const [form, setForm] = useState<FormState>(() => fromUser(me));
  const queryClient = useQueryClient();

  // Reset when the saved profile changes (after a save, or switching member).
  useEffect(() => setForm(fromUser(me)), [me]);

  const save = useMutation({
    mutationFn: () => api.updateMe(toPayload(form)),
    onSuccess: () => {
      // Names appear on posts and comments too, so refresh both.
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      void queryClient.invalidateQueries({ queryKey: ["posts"] });
    },
  });

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    save.reset();
    setForm((f) => ({ ...f, [key]: value }));
  };

  const onDobChange = (dob: string) => {
    save.reset();
    // Keep age in step with the birth date; it can still be edited afterwards.
    const age = dob ? ageFrom(dob) : null;
    setForm((f) => ({ ...f, date_of_birth: dob, age: age !== null && age >= 0 ? String(age) : f.age }));
  };

  const errors = validate(form);
  const valid = Object.keys(errors).length === 0;
  const dirty = JSON.stringify(toPayload(form)) !== JSON.stringify(toPayload(fromUser(me)));
  const dobAge = form.date_of_birth ? ageFrom(form.date_of_birth) : null;
  const ageMismatch = dobAge !== null && form.age !== "" && Number(form.age) !== dobAge;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (valid && dirty && !save.isPending) save.mutate();
  };

  return (
    <div className="settings-page">
      <section className="card settings-hero">
        <div className="banner" style={bannerStyle(me.id)} />
        <div className="settings-hero-body">
          <Avatar name={me.name} id={me.id} size={84} />
          <div>
            <h1>{me.name}</h1>
            <p className="muted">
              {me.username ? `@${me.username}` : "No username yet"}
              {me.headline && ` · ${me.headline}`}
            </p>
          </div>
        </div>
      </section>

      <form onSubmit={submit} className="settings-form">
        <Section icon={<UserIcon size={20} />} title="Profile" subtitle="How you appear to other members.">
          <div className="grid-2">
            <Field label="Full name" error={errors.name}>
              <input value={form.name} onChange={(e) => set("name", e.target.value)} maxLength={80} aria-invalid={!!errors.name} />
            </Field>
            <Field label="Username" error={errors.username} hint="Used to sign in. Letters, numbers, dots and underscores.">
              <div className="input-prefix">
                <span>@</span>
                <input
                  value={form.username}
                  onChange={(e) => set("username", e.target.value)}
                  maxLength={30}
                  placeholder="your.name"
                  autoCapitalize="none"
                  spellCheck={false}
                  aria-invalid={!!errors.username}
                />
              </div>
            </Field>
            <Field label="Headline">
              <input
                value={form.headline}
                onChange={(e) => set("headline", e.target.value)}
                maxLength={160}
                placeholder="e.g. Software Engineer at Acme"
              />
            </Field>
            <Field label="Location">
              <input
                value={form.location}
                onChange={(e) => set("location", e.target.value)}
                maxLength={160}
                placeholder="e.g. Boston, MA"
              />
            </Field>
          </div>
          <Field label="About" hint={`${form.about.length}/2000 · Also editable from your profile page.`}>
            <textarea
              value={form.about}
              onChange={(e) => set("about", e.target.value)}
              maxLength={2000}
              rows={4}
              placeholder="A short note about yourself, your work and what you're looking for."
            />
          </Field>
        </Section>

        <Section
          icon={<LockIcon size={20} />}
          title="Personal details"
          subtitle="Only shown on your own profile, never to other members."
        >
          <div className="grid-2">
            <Field label="Phone number" error={errors.phone}>
              <input
                type="tel"
                value={form.phone}
                onChange={(e) => set("phone", e.target.value)}
                placeholder="+1 555 123 4567"
                maxLength={20}
                aria-invalid={!!errors.phone}
              />
            </Field>
            <Field label="Gender">
              <select value={form.gender} onChange={(e) => set("gender", e.target.value as Gender | "")}>
                <option value="">Not specified</option>
                {Object.entries(GENDER_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Date of birth" error={errors.date_of_birth}>
              <input
                type="date"
                value={form.date_of_birth}
                onChange={(e) => onDobChange(e.target.value)}
                min="1900-01-01"
                max={todayIso()}
                aria-invalid={!!errors.date_of_birth}
              />
            </Field>
            <Field
              label="Age"
              error={errors.age}
              hint={ageMismatch ? `Your date of birth suggests ${dobAge}.` : "Filled in from your date of birth."}
            >
              <input
                type="number"
                value={form.age}
                onChange={(e) => set("age", e.target.value)}
                min={13}
                max={120}
                inputMode="numeric"
                aria-invalid={!!errors.age}
              />
            </Field>
          </div>
        </Section>

        <div className={`save-bar ${dirty ? "visible" : ""}`}>
          <span className="small">
            {save.isError ? (
              <span className="error">{save.error.message}</span>
            ) : save.isSuccess && !dirty ? (
              <span className="success">
                <CheckIcon size={14} /> Changes saved
              </span>
            ) : dirty ? (
              "You have unsaved changes"
            ) : (
              <span className="muted">All changes saved</span>
            )}
          </span>
          <div className="form-actions">
            <button type="button" className="btn ghost" onClick={() => setForm(fromUser(me))} disabled={!dirty || save.isPending}>
              Discard
            </button>
            <button className="btn primary" disabled={!valid || !dirty || save.isPending}>
              {save.isPending ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </form>

      <Section icon={<FileIcon size={20} />} title="Resume" subtitle="Upload a PDF. Anyone viewing your profile can open it.">
        <ResumeUpload me={me} />
      </Section>
    </div>
  );
}
