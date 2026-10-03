import type { User, View } from "../types";
import { Avatar } from "./Avatar";
import { ConnectButton } from "./ConnectButton";

interface Props {
  me: User;
  users: User[];
  onNavigate: (v: View) => void;
}

export function Suggestions({ me, users, onNavigate }: Props) {
  const suggestions = users.filter((u) => u.id !== me.id && !me.connections.includes(u.id)).slice(0, 4);

  return (
    <aside className="card side-list sticky">
      <h3>People you may know</h3>
      {suggestions.length === 0 && <p className="muted small">You're connected with everyone! 🎉</p>}
      {suggestions.map((u) => (
        <div key={u.id} className="suggestion">
          <button className="person-row" onClick={() => onNavigate({ page: "profile", userId: u.id })}>
            <Avatar name={u.name} id={u.id} size={44} />
            <span className="person-info">
              <span className="name">{u.name}</span>
              <span className="muted xs clamp-2">{u.headline}</span>
            </span>
          </button>
          <ConnectButton me={me} target={u} />
        </div>
      ))}
    </aside>
  );
}
