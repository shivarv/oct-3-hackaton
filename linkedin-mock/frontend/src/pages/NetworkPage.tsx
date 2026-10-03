import type { User, View } from "../types";
import { Avatar, bannerStyle } from "../components/Avatar";
import { ConnectButton } from "../components/ConnectButton";

interface Props {
  me: User;
  users: User[];
  onNavigate: (v: View) => void;
}

export function NetworkPage({ me, users, onNavigate }: Props) {
  const others = users.filter((u) => u.id !== me.id);
  const connected = others.filter((u) => me.connections.includes(u.id));
  const suggested = others.filter((u) => !me.connections.includes(u.id));

  const tiles = (list: User[]) => (
    <div className="people-grid">
      {list.map((u) => (
        <div key={u.id} className="person-tile">
          <div className="banner" style={bannerStyle(u.id)} />
          <button className="avatar-button" onClick={() => onNavigate({ page: "profile", userId: u.id })}>
            <Avatar name={u.name} id={u.id} size={80} />
          </button>
          <button className="link name" onClick={() => onNavigate({ page: "profile", userId: u.id })}>
            {u.name}
          </button>
          {u.username && <span className="muted xs">@{u.username}</span>}
          <span className="muted xs clamp-2 tile-headline">{u.headline}</span>
          <ConnectButton me={me} target={u} />
        </div>
      ))}
    </div>
  );

  return (
    <div className="layout one-col wide">
      <main className="feed">
        <section className="card section">
          <h2>People you may know</h2>
          <p className="muted small">{suggested.length} suggestions</p>
          {suggested.length ? tiles(suggested) : <p className="muted small">You're connected with everyone! 🎉</p>}
        </section>
        <section className="card section">
          <h2>Your connections</h2>
          <p className="muted small">{connected.length} connections</p>
          {connected.length ? tiles(connected) : <p className="muted small">No connections yet.</p>}
        </section>
      </main>
    </div>
  );
}
