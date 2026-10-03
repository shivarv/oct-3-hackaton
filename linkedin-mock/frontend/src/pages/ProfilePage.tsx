import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { GENDER_LABELS, type User, type View } from "../types";
import { Avatar, bannerStyle } from "../components/Avatar";
import { ConnectButton } from "../components/ConnectButton";
import {
  CalendarIcon,
  DownloadIcon,
  EditIcon,
  EyeIcon,
  FileIcon,
  LockIcon,
  MapPinIcon,
  PhoneIcon,
  SettingsIcon,
  UserIcon,
} from "../components/Icons";
import { PostCard } from "../components/PostCard";
import { formatBytes } from "../components/ResumeUpload";

interface Props {
  me: User;
  users: User[];
  userId: string;
  onNavigate: (v: View) => void;
}

function AboutCard({ user, editable }: { user: User; editable: boolean }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(user.about);
  const save = useMutation({
    mutationFn: () => api.updateMe({ about: draft.trim() }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      setEditing(false);
    },
  });

  if (!editable && !user.about) return null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };

  return (
    <section className="card section">
      <div className="section-title-row">
        <h2>About</h2>
        {editable && !editing && (
          <button
            className="icon-btn"
            onClick={() => {
              setDraft(user.about);
              save.reset();
              setEditing(true);
            }}
            title="Edit about"
            aria-label="Edit about"
          >
            <EditIcon size={18} />
          </button>
        )}
      </div>
      {editing ? (
        <form className="edit-box" onSubmit={submit}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={2000}
            rows={6}
            placeholder="Write a short note about yourself…"
            autoFocus
          />
          <div className="form-actions spread">
            <span className="muted xs">{draft.length}/2000</span>
            <div className="form-actions">
              <button type="button" className="btn ghost" onClick={() => setEditing(false)}>
                Cancel
              </button>
              <button className="btn primary" disabled={save.isPending}>
                {save.isPending ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
          {save.isError && <p className="error small">{save.error.message}</p>}
        </form>
      ) : user.about ? (
        <p className="pre-wrap">{user.about}</p>
      ) : (
        <button className="empty-cta" onClick={() => setEditing(true)}>
          <EditIcon size={16} /> Add a note about yourself
        </button>
      )}
    </section>
  );
}

export function ProfilePage({ me, users, userId, onNavigate }: Props) {
  const user = users.find((u) => u.id === userId);
  const posts = useQuery({ queryKey: ["posts", "author", userId], queryFn: () => api.posts(userId) });

  if (!user) return <p className="error center">Member not found.</p>;

  const isMe = user.id === me.id;
  const connections = users.filter((u) => user.connections.includes(u.id));

  return (
    <div className="layout two-col">
      <main className="feed">
        <section className="card profile-header">
          <div className="banner tall" style={bannerStyle(user.id)} />
          <div className="profile-header-body">
            <Avatar name={user.name} id={user.id} size={128} />
            <div className="profile-header-row">
              <div>
                <h1>{user.name}</h1>
                {user.username && <p className="muted">@{user.username}</p>}
                {user.headline && <p className="headline">{user.headline}</p>}
                <p className="meta-line small muted">
                  {user.location && (
                    <>
                      <MapPinIcon size={14} /> {user.location} ·
                    </>
                  )}
                  <span className="accent">{user.connections.length} connections</span>
                </p>
              </div>
              {isMe ? (
                <button className="btn outline" onClick={() => onNavigate({ page: "settings" })}>
                  <SettingsIcon size={16} /> Edit profile
                </button>
              ) : (
                <ConnectButton me={me} target={user} />
              )}
            </div>
          </div>
        </section>

        <AboutCard key={user.id} user={user} editable={isMe} />

        {isMe && (
          <section className="card section">
            <div className="section-title-row">
              <h2>Personal details</h2>
              <span className="chip muted">
                <LockIcon size={12} /> Only you
              </span>
            </div>
            <dl className="details">
              <div>
                <dt>
                  <PhoneIcon size={16} /> Phone
                </dt>
                <dd>{user.phone || "—"}</dd>
              </div>
              <div>
                <dt>
                  <UserIcon size={16} /> Gender
                </dt>
                <dd>{user.gender ? GENDER_LABELS[user.gender] : "—"}</dd>
              </div>
              <div>
                <dt>
                  <CalendarIcon size={16} /> Date of birth
                </dt>
                <dd>
                  {user.date_of_birth
                    ? new Date(`${user.date_of_birth}T00:00:00`).toLocaleDateString(undefined, { dateStyle: "long" })
                    : "—"}
                </dd>
              </div>
              <div>
                <dt>
                  <CalendarIcon size={16} /> Age
                </dt>
                <dd>{user.age ?? "—"}</dd>
              </div>
            </dl>
          </section>
        )}

        {(user.resume || isMe) && (
          <section className="card section">
            <h2>Resume</h2>
            {user.resume ? (
              <div className="file-tile">
                <div className="file-icon">
                  <FileIcon size={26} />
                  <span>PDF</span>
                </div>
                <div className="file-info">
                  <strong className="clamp-1">{user.resume.filename}</strong>
                  <span className="muted xs">{formatBytes(user.resume.size)}</span>
                </div>
                <div className="file-actions">
                  <a className="btn outline" href={api.resumeUrl(user.id)} target="_blank" rel="noopener noreferrer">
                    <EyeIcon size={16} /> View
                  </a>
                  <a className="icon-btn" href={api.resumeUrl(user.id, true)} title="Download">
                    <DownloadIcon size={18} />
                  </a>
                </div>
              </div>
            ) : (
              <button className="empty-cta" onClick={() => onNavigate({ page: "settings" })}>
                <FileIcon size={16} /> Upload your resume in Settings
              </button>
            )}
          </section>
        )}

        <section className="card section">
          <h2>Activity</h2>
          {posts.isPending && <p className="muted">Loading…</p>}
          {posts.data?.length === 0 && <p className="muted">No posts yet.</p>}
          {posts.data && posts.data.length > 0 && (
            <p className="muted small">
              {posts.data.length} {posts.data.length === 1 ? "post" : "posts"}
            </p>
          )}
        </section>
        {posts.data?.map((p) => <PostCard key={p.id} post={p} me={me} onNavigate={onNavigate} />)}
      </main>

      <aside className="card side-list sticky">
        <h3>Connections · {connections.length}</h3>
        {connections.length === 0 && <p className="muted small">No connections yet.</p>}
        {connections.map((c) => (
          <button key={c.id} className="person-row" onClick={() => onNavigate({ page: "profile", userId: c.id })}>
            <Avatar name={c.name} id={c.id} size={40} />
            <span className="person-info">
              <span className="name">{c.name}</span>
              <span className="muted xs clamp-1">{c.headline}</span>
            </span>
          </button>
        ))}
      </aside>
    </div>
  );
}
