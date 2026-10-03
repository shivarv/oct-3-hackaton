import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ME_KEY } from "./api";
import type { User, View } from "./types";
import { Navbar } from "./components/Navbar";
import { AuthPage } from "./pages/AuthPage";
import { FeedPage } from "./pages/FeedPage";
import { MembersPage } from "./pages/MembersPage";
import { NetworkPage } from "./pages/NetworkPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  const me = useQuery({ queryKey: ME_KEY, queryFn: api.me, staleTime: 60_000 });

  if (me.isPending) return <div className="splash"><span className="logo static">in</span></div>;
  if (me.isError) return <p className="error center">Could not reach the API: {me.error.message}</p>;
  if (!me.data) return <AuthPage />;
  // Keyed by member so navigation state resets when someone else logs in.
  return <Shell key={me.data.id} me={me.data} />;
}

function Shell({ me }: { me: User }) {
  const users = useQuery({ queryKey: ["users", "all"], queryFn: api.users });
  const [view, setView] = useState<View>({ page: "feed" });

  const navigate = (next: View) => {
    setView(next);
    window.scrollTo({ top: 0 });
  };

  return (
    <>
      <Navbar me={me} view={view} onNavigate={navigate} />
      {users.isPending && <p className="muted center">Loading…</p>}
      {users.isError && <p className="error center">{users.error.message}</p>}
      {users.data && (
        <>
          {view.page === "feed" && <FeedPage me={me} users={users.data} onNavigate={navigate} />}
          {view.page === "network" && <NetworkPage me={me} users={users.data} onNavigate={navigate} />}
          {view.page === "members" && <MembersPage me={me} users={users.data} onNavigate={navigate} />}
          {view.page === "settings" &&<SettingsPage me={me} />}
          {view.page === "profile" && (
            <ProfilePage me={me} users={users.data} userId={view.userId} onNavigate={navigate} />
          )}
        </>
      )}
    </>
  );
}
