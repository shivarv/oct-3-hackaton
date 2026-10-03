import { api } from "../api";
import type { User, View } from "../types";
import { Avatar, bannerStyle } from "./Avatar";
import { FileIcon, MapPinIcon } from "./Icons";

export function ProfileCard({ user, onNavigate }: { user: User; onNavigate: (v: View) => void }) {
  const open = () => onNavigate({ page: "profile", userId: user.id });
  return (
    <aside className="card profile-card sticky">
      <div className="banner" style={bannerStyle(user.id)} />
      <div className="profile-card-body">
        <button className="avatar-button" onClick={open} aria-label="View profile">
          <Avatar name={user.name} id={user.id} size={72} />
        </button>
        <button className="link name lg" onClick={open}>
          {user.name}
        </button>
        {user.username && <span className="muted small">@{user.username}</span>}
        <p className="muted small">{user.headline}</p>
        {user.location && (
          <span className="meta-line small">
            <MapPinIcon size={14} /> {user.location}
          </span>
        )}
      </div>
      <div className="stat-row">
        <span>Connections</span>
        <strong>{user.connections.length}</strong>
      </div>
      <div className="stat-row">
        <span>Resume</span>
        {user.resume ? (
          <a className="accent icon-link" href={api.resumeUrl(user.id)} target="_blank" rel="noopener noreferrer">
            <FileIcon size={14} /> View
          </a>
        ) : (
          <span className="muted">—</span>
        )}
      </div>
    </aside>
  );
}
