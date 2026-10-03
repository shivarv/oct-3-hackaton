import { useState } from "react";
import type { User, View } from "../types";
import { Avatar, bannerStyle } from "../components/Avatar";
import { ConnectButton } from "../components/ConnectButton";

interface Props {
  me: User;
  users: User[];
  onNavigate: (v: View) => void;
}

export function MembersPage({ me, users, onNavigate }: Props) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const shown = q
    ? users.filter((u) =>
        [u.name, u.username ?? "", u.headline, u.location].some((f) => f.toLowerCase().includes(q)),
      )
    : users;

  return (
    <div className="layout one-col wide">
      <main className="feed">
        <section className="card section">
          <h2>All members</h2>
          <p className="muted small">
            {q ? `${shown.length} of ${users.length} members` : `${users.length} members`}
          </p>
          <label className="field members-search">
            <span className="field-label">Search</span>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name, username, headline or location"
            />
          </label>
          {shown.length ? (
            <div className="people-grid">
              {shown.map((u) => (
                <div key={u.id} className="person-tile">
                  <div className="banner" style={bannerStyle(u.id)} />
                  <button className="avatar-button" onClick={() => onNavigate({ page: "profile", userId: u.id })}>
                    <Avatar name={u.name} id={u.id} size={80} />
                  </button>
                  <button className="link name" onClick={() => onNavigate({ page: "profile", userId: u.id })}>
                    {u.name}
                    {u.id === me.id && " (you)"}
                  </button>
                  {u.username && <span className="muted xs">@{u.username}</span>}
                  <span className="muted xs clamp-2 tile-headline">{u.headline}</span>
                  <ConnectButton me={me} target={u} />
                </div>
              ))}
            </div>
          ) : (
            <p className="muted small">No members match "{query.trim()}".</p>
          )}
        </section>
      </main>
    </div>
  );
}
